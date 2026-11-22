"""Startup-velocity teacher/student on the local C-matched cache (prep_lc_local.py), GPU.

  python lc_local.py eval    --header ../learned_c/w_J/lc_weights.h --flights hf          # deployed lcJ, direct error
  python lc_local.py teacher --out runs_lc/T1 --epochs 40                                  # big net (res 128, width 2)
  python lc_local.py student --out runs_lc/S1 --teacher runs_lc/T1/best.pt --init_header ../learned_c/w_J/lc_weights.h
  python lc_local.py export  --ckpt runs_lc/S1/best.pt --out runs_lc/S1/lc_weights.h

Student = the deployed C architecture (learned/train.py Net nf=2 res 64 width 1, BN folded = conv+bias), so a trained
student drops into lc_core.h unchanged. Loss = Gaussian NLL vs truth + KD * (|mu_s-mu_t|^2/var_t + (lv_s-lv_t)^2)/2.
Flight lists (names = cache stems): 'hf' = the 171 server-calibrated flights, 'pxdev'/'pxtest' = proxy scene splits,
'train:<file.json>' = explicit list. Validation for checkpoint choice: a scene-hash split of the training flights.
"""
import argparse, glob, hashlib, json, math, re, sys, time
from pathlib import Path
import numpy as np
import torch, torch.nn as nn

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "learned"))
import train as T  # noqa: E402  (build_batch, flip, nll, Net)

CACHE = Path("C:/Users/alexa/vio_data/work/lc_cache")
DATA = Path("C:/Users/alexa/vio_data")
SBINS = [0, 0.3, 1.0, 1.5, 2.5, 99]


def scene_of(stem):
    m = json.load(open(DATA / "server-calibrated/manifest.json"))["episodes"]
    d = {e["id"]: e["scene"] for e in m}
    for f in glob.glob(str(DATA / "proxy/*.json")):
        j = json.load(open(f)); d[Path(f).stem] = j["scene"]
    return d.get(stem, stem)


def flight_list(spec):
    stems = sorted(Path(p).stem for p in glob.glob(str(CACHE / "*.npz")) if not p.endswith(".tmp.npz"))
    if spec == "hf" or spec.startswith("hf:"):
        eps = json.load(open(DATA / "server-calibrated/manifest.json"))["episodes"]
        fold = lambda e: int(hashlib.sha256((e["catalog"] + ":" + e["scene"]).encode()).hexdigest()[:8], 16) % 5
        keep = None if spec == "hf" else {int(x) for x in spec[3:].split("+")}
        ids = {e["id"] for e in eps if keep is None or fold(e) in keep}
        return [s for s in stems if s in ids]
    if spec in ("pxdev", "pxtest", "px"):
        sp = json.load(open(HERE / "proxy_split.json")); sc = {Path(f).stem: json.load(open(f))["scene"] for f in glob.glob(str(DATA / "proxy/*.json"))}
        return [s for s in stems if s in sc and (spec == "px" or sp.get(sc[s]) == spec[2:])]
    if spec.startswith("train:"):
        return json.load(open(spec[6:]))
    raise ValueError(spec)


class Data:
    """learned_c/train2.Data2 on local cache stems (each phase is its own sequence)."""

    def __init__(self, stems, dev, phases=(0, 2)):
        fr, Rc, Vi, fm, gm, vb, K, fx, fid, pos, ln = ([] for _ in range(11)); self.Tbc = None; self.stems = stems
        for i, s in enumerate(stems):
            d = np.load(CACHE / f"{s}.npz")
            if self.Tbc is None: self.Tbc = d["Tbc"]
            for p in phases:
                A = len(d[f"frames{p}"])
                fr.append(d[f"frames{p}"]); Rc.append(d[f"Rcum{p}"]); Vi.append(d[f"Vint{p}"]); fm.append(d[f"fmean{p}"]); gm.append(d[f"gmean{p}"])
                vb.append(d[f"vb{p}"]); K.append(np.tile(d["K"], (A, 1))); fx.append(np.full(A, float(d["fx320"])))
                fid.append(np.full(A, i)); pos.append(np.arange(A)); ln.append(np.full(A, A))
        c = lambda x: torch.from_numpy(np.concatenate(x)).to(dev).float()
        self.frames = torch.from_numpy(np.concatenate(fr)).to(dev)
        self.R, self.V, self.f, self.g, self.vb, self.K, self.fx = c(Rc), c(Vi), c(fm), c(gm), c(vb), c(K), c(fx)
        self.fid = torch.from_numpy(np.concatenate(fid)).to(dev); self.pos = torch.from_numpy(np.concatenate(pos)).to(dev)
        self.len = torch.from_numpy(np.concatenate(ln)).to(dev); self.N = len(self.pos)
        self.Rbc = torch.tensor(self.Tbc[:3, :3], dtype=torch.float32, device=dev)
        self.speed = self.vb.norm(dim=1)

    def valid_starts(self, nf=2, gap=1, first_only=False):
        m = self.pos + (nf - 1) * gap < self.len
        if first_only:
            m &= self.pos == 0
        return torch.nonzero(m).squeeze(1)


class Folded(nn.Module):
    """The deployed C net: 4 conv(3x3, s2)+bias+ReLU at 64x48 -> 3x4, IMU embedding 19->32, head 608->128->12."""

    def __init__(self, chs=(16, 24, 32, 48), cin=5):
        super().__init__()
        L = []; c = cin
        for co in chs:
            L += [nn.Conv2d(c, co, 3, 2, 1), nn.ReLU(inplace=True)]; c = co
        self.cnn = nn.Sequential(*L)
        self.fv = nn.Sequential(nn.Linear(19, 32), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(c * 12 + 32, 128), nn.ReLU(), nn.Linear(128, 12))
        self.res, self.C = 64, c

    def forward(self, img, vec):
        o = self.head(torch.cat([self.cnn(img).flatten(1), self.fv(vec)], 1)).view(-1, 2, 6)
        return o[..., :3], o[..., 3:].clamp(-7, 4)


def parse_header(path):
    s = Path(path).read_text(); out = {}
    for m in re.finditer(r"static const float (\w+)\[(\d+)\] = \{([^}]*)\}", s):
        out[m.group(1)] = np.array([float(x) for x in m.group(3).replace("\n", "").split(",") if x.strip()], np.float32)
    chs = [int(re.search(rf"#define LC_C{i} (\d+)", s).group(1)) for i in range(4)]
    return out, chs


def load_header(path):
    A, chs = parse_header(path); net = Folded(tuple(chs)); cin = 5; convs = [m for m in net.cnn if isinstance(m, nn.Conv2d)]
    for i, conv in enumerate(convs):
        co, ci = conv.out_channels, conv.in_channels
        conv.weight.data = torch.from_numpy(A[f"LC_W{i}"].reshape(3, 3, ci, co)).permute(3, 2, 0, 1).contiguous()
        conv.bias.data = torch.from_numpy(A[f"LC_B{i}"])
    net.fv[0].weight.data = torch.from_numpy(A["LC_FW0"].reshape(19, 32)).t().contiguous(); net.fv[0].bias.data = torch.from_numpy(A["LC_FB0"])
    C = chs[-1]; H1 = torch.from_numpy(A["LC_H1W"].reshape(12 * C + 32, 128)).t()  # (128, 12C+32), cnn part in h,w,c order
    cnn = H1[:, :12 * C].reshape(128, 3, 4, C).permute(0, 3, 1, 2).reshape(128, 12 * C)
    net.head[0].weight.data = torch.cat([cnn, H1[:, 12 * C:]], 1).contiguous(); net.head[0].bias.data = torch.from_numpy(A["LC_H1B"])
    net.head[2].weight.data = torch.from_numpy(A["LC_H2W"].reshape(128, 12)).t().contiguous(); net.head[2].bias.data = torch.from_numpy(A["LC_H2B"])
    return net


def export_header(net, path, note=""):
    arrs = {}; convs = [m for m in net.cnn if isinstance(m, nn.Conv2d)]; chs = []
    for i, conv in enumerate(convs):
        arrs[f"LC_W{i}"] = conv.weight.detach().cpu().permute(2, 3, 1, 0).numpy(); arrs[f"LC_B{i}"] = conv.bias.detach().cpu().numpy(); chs.append(conv.out_channels)
    arrs["LC_FW0"] = net.fv[0].weight.detach().cpu().t().numpy(); arrs["LC_FB0"] = net.fv[0].bias.detach().cpu().numpy()
    C = chs[-1]; W1 = net.head[0].weight.detach().cpu()
    cnn = W1[:, :C * 12].reshape(128, C, 3, 4).permute(0, 2, 3, 1).reshape(128, 12 * C)
    arrs["LC_H1W"] = torch.cat([cnn, W1[:, C * 12:]], 1).t().numpy(); arrs["LC_H1B"] = net.head[0].bias.detach().cpu().numpy()
    arrs["LC_H2W"] = net.head[2].weight.detach().cpu().t().numpy(); arrs["LC_H2B"] = net.head[2].bias.detach().cpu().numpy()
    lines = [f"/* generated by proxy/lc_local.py {note}: conv+bias (BN-free), float32 */", "#define LC_SIGSCALE 1.0f",
             "#define LC_C0 %d\n#define LC_C1 %d\n#define LC_C2 %d\n#define LC_C3 %d" % tuple(chs)]
    for k, a in arrs.items():
        a = np.ascontiguousarray(a, dtype=np.float32).ravel()
        lines.append(f"static const float {k}[{a.size}] = {{")
        for i in range(0, a.size, 8): lines.append(",".join(f"{x:.9g}" for x in a[i:i + 8]) + ",")
        lines.append("};")
    Path(path).write_text("\n".join(lines) + "\n")


def big_teacher():
    return T.Net(128, 2.0, 2, 19)  # 5 conv layers (32..128 ch) at 128x96, BN


@torch.no_grad()
def predict(net, D, starts, res, bs=1024):
    net.eval(); M, L, Y = [], [], []
    for i in range(0, len(starts), bs):
        g = starts[i:i + bs]; img, vec, t, _ = T.build_batch(D, g, 2, 1, res, False)
        mu, lv = net(img, vec); M.append(mu); L.append(lv); Y.append(t)
    return torch.cat(M), torch.cat(L), torch.cat(Y)


def report(mu, lv, y, label=""):
    e = (mu[:, 1] - y[:, 1]).norm(dim=1); sp = y[:, 1].norm(dim=1); z = (mu[:, 1] - y[:, 1]) / torch.exp(0.5 * lv[:, 1])
    out = {"all": dict(n=len(e), err=float(e.mean()), cov1=float((z.abs() < 1).float().mean()), zrms=float(z.pow(2).mean().sqrt()))}
    for i in range(len(SBINS) - 1):
        m = (sp >= SBINS[i]) & (sp < SBINS[i + 1])
        if m.sum() > 20:
            out[f"spd{SBINS[i]}-{SBINS[i + 1]}"] = dict(n=int(m.sum()), err=float(e[m].mean()), zrms=float(z[m].pow(2).mean().sqrt()))
    if label:
        print(label, " | ".join(f"{k} n={v['n']} err {v['err']:.3f} zrms {v['zrms']:.2f}" for k, v in out.items()), flush=True)
    return out


def split_val(stems):
    va = [s for s in stems if int(hashlib.sha256(scene_of(s).encode()).hexdigest()[:8], 16) % 6 == 0]
    return [s for s in stems if s not in va], va


def train(a, kind):
    dev = "cuda"; torch.manual_seed(a.seed)
    stems = sum((flight_list(s) for s in a.flights.split(",")), [])
    tr, va = split_val(stems)
    Dt, Dv = Data(tr, dev), Data(va, dev, phases=(0,))
    trs, vas = Dt.valid_starts(), Dv.valid_starts()
    # speed-balanced sampling (fast starts are rare but they are where the deployed net fails)
    sb = torch.bucketize(Dt.speed[trs], torch.tensor(SBINS[1:-1], device=dev))
    cnt = torch.bincount(sb, minlength=len(SBINS) - 1).float().clamp(min=1); w = (1.0 / cnt[sb]) ** a.alpha
    print(kind, "train flights", len(tr), "anchors", len(trs), "val flights", len(va), "anchors", len(vas), flush=True)
    if kind == "teacher":
        net = big_teacher().to(dev); res = 128; Tn = None
    else:
        net = (load_header(a.init_header) if a.init_header else Folded()).to(dev); res = 64
        if a.teacher.endswith(".h"):  # the deployed net as teacher (64x48 input)
            Tn = load_header(a.teacher).to(dev); t_res = 64
        else:
            Tn = big_teacher().to(dev); Tn.load_state_dict(torch.load(a.teacher, map_location=dev)); t_res = 128
        Tn.eval()
        for p in Tn.parameters(): p.requires_grad_(False)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    report(*predict(net, Dv, vas, res), label="init val")
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-4)
    total = a.epochs * a.steps
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=total, pct_start=0.1 if not a.init_header else 0.02)
    best = 1e9
    for ep in range(a.epochs):
        net.train(); tl = 0
        for _ in range(a.steps):
            g = trs[torch.multinomial(w, a.bs, replacement=True)]
            img, vec, tgt, _ = T.build_batch(Dt, g, 2, 1, 128, True)
            fl = torch.rand(a.bs, device=dev) < 0.5
            if fl.any():
                i2, v2, t2 = T.flip(img[fl], vec[fl], tgt[fl], 2)
                img = img.clone(); vec = vec.clone(); tgt = tgt.clone(); img[fl], vec[fl], tgt[fl] = i2, v2, t2
            img_s = img if res == 128 else torch.nn.functional.avg_pool2d(img, 2)
            mu, lv = net(img_s, vec)
            loss = T.nll(mu, lv, tgt).mean() * 3 if (ep >= 1 or a.init_header) else (0.5 * (mu - tgt) ** 2).mean() * 3
            if Tn is not None:
                with torch.no_grad():
                    mt, lt = Tn(img if t_res == 128 else torch.nn.functional.avg_pool2d(img, 2), vec)
                loss = loss + a.kd * (0.5 * ((mu - mt) ** 2 * torch.exp(-lt)).mean() + 0.5 * ((lv - lt) ** 2).mean())
            opt.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0); opt.step(); sched.step()
            tl += loss.item()
        r = report(*predict(net, Dv, vas, res))
        crit = float(np.mean([v["err"] for k, v in r.items() if k.startswith("spd")]))  # speed-balanced error
        print(f"ep {ep} loss {tl / a.steps:.3f} val err {r['all']['err']:.3f} balanced {crit:.3f} zrms {r['all']['zrms']:.2f}", flush=True)
        if crit < best:
            best = crit; torch.save(net.state_dict(), out / "best.pt")
    net.load_state_dict(torch.load(out / "best.pt"))
    r = report(*predict(net, Dv, vas, res), label="best val")
    json.dump(dict(args=vars(a), val=r, train=tr, valf=va), open(out / "result.json", "w"), indent=1)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd")
    ap.add_argument("--header", default=""); ap.add_argument("--ckpt", default=""); ap.add_argument("--flights", default="hf")
    ap.add_argument("--out", default=""); ap.add_argument("--teacher", default=""); ap.add_argument("--init_header", default="")
    ap.add_argument("--epochs", type=int, default=30); ap.add_argument("--steps", type=int, default=300); ap.add_argument("--bs", type=int, default=256)
    ap.add_argument("--lr", type=float, default=2e-3); ap.add_argument("--kd", type=float, default=1.0); ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--first_only", action="store_true")
    a = ap.parse_args()
    if a.cmd == "eval":
        dev = "cuda"
        if a.header:
            net = load_header(a.header).to(dev); res = 64
        else:
            sd = torch.load(a.ckpt, map_location=dev); res = 128 if any("cnn.12" in k for k in sd) else 64
            net = (big_teacher() if res == 128 else Folded()).to(dev); net.load_state_dict(sd)
        for spec in a.flights.split(","):
            D = Data(flight_list(spec), dev, phases=(0,))
            report(*predict(net, D, D.valid_starts(first_only=a.first_only), res), label=f"{spec} {'first' if a.first_only else 'all'} anchors:")
    elif a.cmd in ("teacher", "student"):
        train(a, a.cmd)
    elif a.cmd == "export":
        net = Folded(); net.load_state_dict(torch.load(a.ckpt, map_location="cpu")); export_header(net, a.out, note=a.ckpt)
        print("wrote", a.out)


if __name__ == "__main__":
    main()
