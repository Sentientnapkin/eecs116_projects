"""Train the cheap guest's MLP residual on many local sets (cheap_mlp.c layout), validate on held-out scenes.

  GROWS=27 ~/.venv_gru/bin/python mlp_fit.py
Env: TRAIN / VAL / TEST  comma-separated ~/data/imucache/<name> sets
       (default train hf + tuning dev folders, val = tuning conf folders, test = ho)
     H (16)  ACT (relu)  EPOCHS (3000)  LR (3e-3)  WD (1e-4)  SEED  TH (threads)  GROWS (gyro rows, as fit_cheap)
     HARDW  extra loss weight on the training flights flagged server-like (see hard_mask), default 1 = none
v = Wlin x + W2 act(W1 x[1:] + B1); Wlin starts at the ridge fit on the training sets (fit_cheap's trajectory least
squares), the MLP output layer at zero. Early stopping on VAL mean ATE. Saves ~/data/mlpfit_<tag>.pt for export_mlp.py.
"""
import os, sys, time
import numpy as np
import torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit_cheap as fc

HOME = os.path.expanduser("~/data")
DT = fc.DT
GTAG = "".join(map(str, fc.GROWS))
FEAT = os.environ.get("FEAT", "")          # "" = fit_cheap gabs2 (10 features); "s3b" = s3feat.py (20 features)
if FEAT == "s3b":
    import s3feat
    PREP, NFEAT = s3feat.prep, s3feat.NF
else:
    PREP, NFEAT = fc.prep, 10


def prep_set(name):
    cache = f"{HOME}/mlpfit_prep_{name}_g{GTAG}{'_' + FEAT if FEAT else ''}.npz"
    if os.path.exists(cache):
        z = np.load(cache); return {k: z[k] for k in z.files}
    S = fc.load(f"{HOME}/imucache/{name}")
    T = max(len(f["imu"]) for f in S); B = len(S)
    R = np.zeros((B, T, 3, 3), np.float32); X = np.zeros((B, T, NFEAT), np.float32)
    C = np.zeros((B, T + 1, 3), np.float32); M = np.zeros((B, T + 1), np.float32)
    for i, f in enumerate(S):
        Rs, Xf = PREP(f); n = len(Xf)
        R[i, :n] = Rs; X[i, :n] = Xf; C[i, :n + 1] = f["cam"][:n + 1]; M[i, :n + 1] = 1
    d = dict(R=R, X=X, C=C, M=M)
    np.savez(cache, **d); return d


def scene_of(name):
    return name.split("-", 1)[1].rsplit("-", 1)[0]


def load_sets(names, drop_scenes=(), drop_names=()):
    """drop_scenes / drop_names: flights to leave out (proxy flights and every flight of their scenes)."""
    import glob
    parts = []; set_names = names; names = []
    for n in set_names:
        if not n: continue
        p = prep_set(n)
        fl = [os.path.basename(f)[:-4] for f in sorted(glob.glob(f"{HOME}/imucache/{n}/*.npz"))]
        assert len(fl) == len(p["X"]), (n, len(fl), len(p["X"]))
        keep = np.array([f not in drop_names and scene_of(f) not in drop_scenes for f in fl])
        names += [f for f, k in zip(fl, keep) if k]
        parts.append({k: v[keep] for k, v in p.items()})
        if not keep.all(): print(f"  {n}: dropped {int((~keep).sum())} of {len(fl)}", flush=True)
    T = max(p["X"].shape[1] for p in parts)
    pad = lambda a, t: np.pad(a, [(0, 0), (0, t - a.shape[1])] + [(0, 0)] * (a.ndim - 2))
    out = {k: torch.tensor(np.concatenate([pad(p[k], T + (k in "CM")) for p in parts]), dtype=torch.float64) for k in "RXCM"}
    ext = torch.sqrt((out["C"] ** 2).sum(-1).sum(1) / out["M"].sum(1))
    out["zero"] = ext; out["wt"] = 1 / torch.clamp(ext, min=1)
    out["dist"] = (torch.linalg.norm(out["C"][:, 1:] - out["C"][:, :-1], dim=-1) * out["M"][:, 1:]).sum(1)
    out["names"] = names
    return out


def ridge_init(D, lam=10.0):
    nf = D["X"].shape[-1]; m = 3 * nf
    A = torch.zeros(m, m, dtype=torch.float64); b = torch.zeros(m, dtype=torch.float64)
    for i in range(len(D["X"])):
        n = int(D["M"][i].sum()) - 1
        Z = torch.cumsum(torch.einsum("kdm,kn->kdmn", D["R"][i, :n], D["X"][i, :n]).reshape(n, 3, m) * DT, 0).reshape(-1, m)
        y = D["C"][i, 1:n + 1].reshape(-1); A += D["wt"][i] * Z.T @ Z; b += D["wt"][i] * Z.T @ y
    return torch.linalg.solve(A + lam * torch.eye(m, dtype=torch.float64), b).reshape(3, nf)


class Net(torch.nn.Module):
    def __init__(self, H, wlin, mu, sd, act):
        super().__init__()
        self.Wlin = torch.nn.Parameter(wlin.clone()); self.act = act
        self.l1 = torch.nn.Linear(wlin.shape[1] - 1, H, dtype=torch.float64); self.out = torch.nn.Linear(H, 3, dtype=torch.float64)
        torch.nn.init.zeros_(self.out.weight); torch.nn.init.zeros_(self.out.bias)
        self.register_buffer("mu", mu); self.register_buffer("sd", sd)

    def forward(self, X):
        z = self.l1((X[..., 1:] - self.mu) / self.sd)
        z = torch.relu(z) if self.act == "relu" else torch.tanh(z) if self.act == "tanh" else z / (1 + z.abs())
        return X @ self.Wlin.T + self.out(z)


def traj_mse(net, D, idx):
    v = net(D["X"][idx])
    dp = DT * torch.einsum("btij,btj->bti", D["R"][idx], v)
    p = torch.cat([torch.zeros_like(dp[:, :1]), torch.cumsum(dp, 1)], 1)
    se = ((p - D["C"][idx]) ** 2).sum(-1) * D["M"][idx]
    return se.sum(1) / D["M"][idx].sum(1)


def main():
    env = os.environ.get
    train = env("TRAIN", "hf,tune_fdev,tune_st1dev,tune_st2dev,tune_st3").split(",")
    val = env("VAL", "tune_fconf,tune_st1conf,tune_st2conf").split(","); test = env("TEST", "ho").split(",")
    H = int(env("H", 16)); act = env("ACT", "relu"); epochs = int(env("EPOCHS", 3000)); lr = float(env("LR", 3e-3))
    wd = float(env("WD", 1e-4)); seed = int(env("SEED", 0)); hardw = float(env("HARDW", 1))
    torch.manual_seed(seed); torch.set_num_threads(int(env("TH", 8)))
    drop_s, drop_n = set(), set()
    if env("PROXY"):  # keep the proxy flights (and their scenes) out of training, and the proxies out of early stopping
        import json
        px = [r["name"] for r in json.load(open(os.path.expanduser(env("PROXY"))))]
        drop_n = set(px); drop_s = {scene_of(n) for n in px}
        print(f"PROXY: {len(px)} flights, {len(drop_s)} scenes held out", flush=True)
    if env("EXCLUDE"):  # file of flight ids to keep out of training and validation (e.g. the stage-3 neighbour set)
        ex = {x.strip() for x in open(os.path.expanduser(env("EXCLUDE"))) if x.strip()}
        drop_n = drop_n | ex
        print(f"EXCLUDE: {len(ex)} flight ids", flush=True)
    Dt, Dv, Ds = load_sets(train, drop_s, drop_n), load_sets(val, (), drop_n), load_sets(test)
    wlin = ridge_init(Dt)
    Xf = Dt["X"][..., 1:][Dt["M"][:, 1:] > 0]; mu, sd = Xf.mean(0), Xf.std(0) + 1e-9
    net = Net(H, wlin, mu, sd, act)
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=wd); sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    it, iv, isx = (torch.arange(len(D["X"])) for D in (Dt, Dv, Ds))
    hard_v = (Dv["dist"] > 35) & (Dv["zero"] > 1.5)           # server-like: normal-length flights that do leave the start
    w = Dt["wt"].clone()
    fw = torch.ones(len(Dt["X"]), dtype=torch.float64)   # FLIGHTW: json {flight id: weight} for the rms loss
    if env("FLIGHTW"):
        import json
        fwd = json.load(open(os.path.expanduser(env("FLIGHTW"))))
        fw = torch.tensor([fwd.get(n, 1.0) for n in Dt["names"]], dtype=torch.float64)
        print(f"FLIGHTW: mean weight {fw.mean():.3f}", flush=True)
    if hardw != 1: w = w * torch.where(Dt["dist"] < 50, hardw, 1.0)  # short-path flights are where it fails locally
    def report(ep, t0):
        with torch.no_grad():
            a = {k: torch.sqrt(traj_mse(net, D, i)) for k, D, i in (("tr", Dt, it), ("va", Dv, iv), ("te", Ds, isx))}
        wz = (a["va"] > Dv["zero"]).double().mean().item()
        print(f"  ep {ep:5d}  train {a['tr'].mean():.3f}  val {a['va'].mean():.3f} (worse-than-zero {wz:.1%}, normal-length "
              f"{a['va'][hard_v].mean():.3f})  test {a['te'].mean():.3f} ({time.time()-t0:.0f}s)", flush=True)
        return a["va"].mean().item(), a["te"].mean().item()
    print(f"GROWS={fc.GROWS} H={H} {act} | train {len(it)} {train} | val {len(iv)} | test {len(isx)} | zero: val {Dv['zero'].mean():.3f} test {Ds['zero'].mean():.3f}", flush=True)
    t0 = time.time(); best = (1e9, None, -1, None)
    for ep in range(epochs + 1):
        if ep % 100 == 0 or ep == epochs:
            va, te = report(ep, t0)
            if va < best[0]: best = (va, {k: v.clone() for k, v in net.state_dict().items()}, ep, te)
        if ep == epochs: break
        opt.zero_grad()
        if env("LOSS") == "rms":  # the server metric: mean over flights of per-flight RMS position error
            loss = (fw * torch.sqrt(traj_mse(net, Dt, it) + 1e-6)).sum() / fw.sum()
        else:
            loss = (w * traj_mse(net, Dt, it)).sum() / len(it)
        loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step(); sched.step()
    print(f"BEST val {best[0]:.3f} at ep {best[2]} -> test {best[3]:.3f}", flush=True)
    s = best[1]
    tag = f"{env('TAG', '')}{FEAT}g{GTAG}_H{H}{act}_hw{hardw:g}{'_px' if env('PROXY') else ''}_s{seed}"  # TAG: keeps old checkpoints
    torch.save({"state": {"Wlin": s["Wlin"], "l1.weight": s["l1.weight"], "l1.bias": s["l1.bias"], "out.weight": s["out.weight"],
                          "out.bias": s["out.bias"]}, "mu": s["mu"].numpy(), "sd": s["sd"].numpy(), "act": act, "grows": fc.GROWS},
               f"{HOME}/mlpfit_{tag}.pt")


if __name__ == "__main__":
    main()
