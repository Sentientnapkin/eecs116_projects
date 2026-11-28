"""Experiment (idea 2): a tiny learned temporal model on top of the cheap guest's linear velocity, trained end to end on
unaligned trajectory error.

  ~/.venv_gru/bin/python gru_fit.py            (needs ~/data/imucache/{hf,ho}; ~/data/pixcache/{hf,ho} for VIS=1)

v_cam[k] = Wlin @ X_lin[k]  +  head(h[k]),  h = GRU(inputs) or MLP(X_lin); Wlin starts at weights.npy (fit_cheap ridge),
the head starts at zero, so epoch 0 reproduces cheap_imu_v2 exactly. Position p = cumsum(DT * R_gyro[k] @ v[k]).
Loss = sum over flights of wt * mean squared position error (wt = 1/max(extent, 1), as in fit_cheap).
Split: hf -> 140 train / 31 val (early stopping), ho = test.
Env: MODEL=gru|mlp|lin  H=hidden  FULL=1 (all 171 hf, final weights)  VIS=1 (add 20x15 flow features)  EPOCHS  LR  WD  SEED
"""
import os, sys, time
import numpy as np
import torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit_cheap as fc

HOME = os.path.expanduser("~/data")
DT = fc.DT
ACT = os.environ.get("ACT", "tanh")


def prep_set(name, vis):
    cache = f"{HOME}/gru_prep_{name}{'_vis' if vis else ''}.npz"
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=True); return {k: z[k] for k in z.files}
    S = fc.load(f"{HOME}/imucache/{name}")
    if vis: S = [f for f in S if os.path.exists(f"{HOME}/pixcache/{name}/{f['name']}.npz")]
    T = max(len(f["imu"]) for f in S); B = len(S)
    R = np.zeros((B, T, 3, 3)); X = np.zeros((B, T, 10)); G = np.zeros((B, T, 3)); C = np.zeros((B, T + 1, 3))
    M = np.zeros((B, T + 1)); V = np.zeros((B, T, 5))
    for i, f in enumerate(S):
        Rs, Xf = fc.prep(f); n = len(Xf)
        R[i, :n] = Rs; X[i, :n] = Xf; G[i, :n] = f["imu"][:, fc.GROWS, 4:7].mean(1) @ f["Tbc"][:3, :3]
        C[i, :n + 1] = f["cam"][:n + 1]; M[i, :n + 1] = 1
        if vis:
            import vis_feats as vf
            V[i, :n] = vf.vis_raw(np.load(f"{HOME}/pixcache/{name}/{f['name']}.npz")["pix"], 16)[0][:n]
    d = dict(R=R, X=X, G=G, C=C, M=M, V=V, names=np.array([f["name"] for f in S]))
    np.savez(cache, **d); return d


class Net(torch.nn.Module):
    def __init__(self, model, H, nin, wlin):
        super().__init__()
        self.model = model
        self.Wlin = torch.nn.Parameter(torch.tensor(wlin.reshape(3, 10)))
        if model == "gru":
            self.rnn = torch.nn.GRU(nin, H, batch_first=True, dtype=torch.float64)
        elif model == "mlp":
            self.l1 = torch.nn.Linear(nin, H, dtype=torch.float64)
        if model != "lin":
            self.out = torch.nn.Linear(H, 3, dtype=torch.float64)
            torch.nn.init.zeros_(self.out.weight); torch.nn.init.zeros_(self.out.bias)

    def forward(self, X, U):
        v = X @ self.Wlin.T
        if self.model == "gru": v = v + self.out(self.rnn(U)[0])
        elif self.model == "mlp":
            z = self.l1(U)
            v = v + self.out(torch.tanh(z) if ACT == "tanh" else z / (1 + z.abs()) if ACT == "softsign" else torch.relu(z))
        return v


def traj_err(net, D, idx):
    v = net(D["X"][idx], D["U"][idx])
    dp = DT * torch.einsum("btij,btj->bti", D["R"][idx], v)
    p = torch.cat([torch.zeros_like(dp[:, :1]), torch.cumsum(dp, 1)], 1)
    se = ((p - D["C"][idx]) ** 2).sum(-1) * D["M"][idx]
    mse = se.sum(1) / D["M"][idx].sum(1)
    return mse


def main():
    model = os.environ.get("MODEL", "gru"); H = int(os.environ.get("H", 8)); vis = bool(int(os.environ.get("VIS", 0)))
    epochs = int(os.environ.get("EPOCHS", 1500)); lr = float(os.environ.get("LR", 3e-3)); wd = float(os.environ.get("WD", 1e-4))
    seed = int(os.environ.get("SEED", 0)); torch.manual_seed(seed); torch.set_num_threads(int(os.environ.get("TH", 8)))
    hf, ho = prep_set("hf", vis), prep_set("ho", vis)

    def inputs(d):
        if model == "mlp": U = d["X"][..., 1:]  # the 9 gyro EMA features
        else: U = d["G"]
        return np.concatenate([U, d["V"]], -1) if vis else U
    Uh, Uo = inputs(hf), inputs(ho)
    mu = Uh.reshape(-1, Uh.shape[-1]).mean(0); sd = Uh.reshape(-1, Uh.shape[-1]).std(0) + 1e-9
    T = lambda a: torch.tensor(a, dtype=torch.float64)
    Dh = {k: T(hf[k]) for k in "RXCM"} | {"U": T((Uh - mu) / sd)}
    Do = {k: T(ho[k]) for k in "RXCM"} | {"U": T((Uo - mu) / sd)}
    for D in (Dh, Do):
        ext = torch.sqrt((D["C"] ** 2).sum(-1).sum(1) / D["M"].sum(1)); D["wt"] = 1 / torch.clamp(ext, min=1); D["zero"] = ext

    perm = np.random.RandomState(0).permutation(len(hf["X"])); va = perm[:31]; tr = perm[31:]
    full = bool(int(os.environ.get("FULL", 0)))  # FULL=1: train on all hf, fixed epochs, keep the final weights
    if full: tr = perm
    wlin = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights.npy"))
    net = Net(model, H, Dh["U"].shape[-1], wlin)
    nparam = sum(p.numel() for p in net.parameters()) - 30
    opt = torch.optim.AdamW([p for n, p in net.named_parameters() if n != "Wlin"] + [net.Wlin], lr=lr, weight_decay=wd)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    ate = lambda D, idx: torch.sqrt(traj_err(net, D, idx)).mean().item()
    ia = np.arange(len(ho["X"]))
    best = (1e9, None, -1); t0 = time.time()
    print(f"{model} H={H} vis={vis} params(+30 lin)={nparam} | train {len(tr)} val {len(va)} test {len(ia)} | "
          f"zero ho {Do['zero'].mean():.3f}", flush=True)
    for ep in range(epochs + 1):
        with torch.no_grad():
            if ep % 50 == 0 or ep == epochs:
                a_tr, a_va, a_ho = ate(Dh, tr), ate(Dh, va), ate(Do, ia)
                if a_va < best[0]: best = (a_va, {k: v.clone() for k, v in net.state_dict().items()}, ep, a_ho)
                print(f"  ep {ep:5d}  train {a_tr:.3f}  val {a_va:.3f}  ho {a_ho:.3f}   ({time.time()-t0:.0f}s)", flush=True)
        if ep == epochs: break
        opt.zero_grad()
        loss = (Dh["wt"][tr] * traj_err(net, Dh, tr)).sum() / len(tr)
        loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step(); sched.step()
    if full:
        best = (a_va, {k: v.clone() for k, v in net.state_dict().items()}, epochs, a_ho)
        print(f"FULL final ep {epochs} -> ho {a_ho:.3f}", flush=True)
    else:
        print(f"BEST val {best[0]:.3f} at ep {best[2]} -> ho {best[3]:.3f}", flush=True)
    tag = f"{model}{ACT}_H{H}{'_vis' if vis else ''}{'_full' if full else ''}_s{seed}"
    torch.save({"state": best[1], "mu": mu, "sd": sd, "model": model, "H": H, "vis": vis, "act": ACT},
               f"{HOME}/gru_{tag}.pt")


if __name__ == "__main__":
    main()
