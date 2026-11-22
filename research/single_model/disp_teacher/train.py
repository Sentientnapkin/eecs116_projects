"""Train the displacement teacher on the per-flight cache (build_cache.py).

  vio_env/Scripts/python train.py --out runs/t1 --hours 2.5

Sampling: flight ~ usable frames; lag L (frames) ~ U{20,22,...,LMAX} so slow cached flights (mean 0.33 m/s) produce
the 1 s displacements of server-speed flights; mid frame at L/2; windows with a relative rotation > 45 deg are
re-drawn (the server's 1 s windows rotate at most ~37 deg). Rotation noise on the derotation and tilt noise on the
gravity input stand in for filter attitude error. Split: scene hash % 12 == 0 -> validation (never trained on).
"""
import argparse, hashlib, json, math, os, time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import IterableDataset, DataLoader

from model import Teacher, TeacherV3, warp

H, W = 96, 128
CX, CY = (W - 1) / 2, (H - 1) / 2


def scene_val(scene):
    return int(hashlib.sha256(str(scene).encode()).hexdigest()[:8], 16) % 12 == 0


def exp_so3(w):
    th = np.linalg.norm(w)
    K = np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])
    if th < 1e-12:
        return np.eye(3) + K
    return np.eye(3) + math.sin(th) / th * K + (1 - math.cos(th)) / th ** 2 * K @ K


def Kmat(fxw):
    fx = fxw * W
    return np.array([[fx, 0, CX], [0, fx, CY], [0, 0, 1.0]])


class Flights:
    def __init__(self, cache, recs):
        self.items = []
        for r in recs:
            key = r["file"][:20]
            pi, pm = Path(cache) / f"{key}.img.npy", Path(cache) / f"{key}.meta.npz"
            if pi.exists() and pm.exists():
                self.items.append((pi, pm, r["scene"]))
        self._img, self._meta = {}, {}

    def img(self, i):
        if i not in self._img:
            self._img[i] = np.load(self.items[i][0], mmap_mode="r")
        return self._img[i]

    def meta(self, i):
        if i not in self._meta:
            z = np.load(self.items[i][1]); self._meta[i] = {k: z[k] for k in z.files}
        return self._meta[i]


def make_sample(fl, i, rng, lmin, lmax, rot_noise, tilt_noise, fixed_L=None):
    m = fl.meta(i); n = len(m["R"])
    Rbc = m["T_bc"][:3, :3].astype(np.float64)
    for _ in range(20):
        L = fixed_L or int(rng.integers(lmin // 2, lmax // 2 + 1)) * 2
        if n <= L + 1:
            return None
        t = int(rng.integers(L, n))
        Rc = [m["R"][k].astype(np.float64) @ Rbc for k in (t, t - L // 2, t - L)]
        Rcc_far = Rc[0].T @ Rc[2]
        ang = math.degrees(math.acos(np.clip((np.trace(Rcc_far) - 1) / 2, -1, 1)))
        if ang <= 45:
            break
    else:
        return None
    K = Kmat(float(m["fxw"][t])); Ki = np.linalg.inv(K)
    Hs = []
    for j, k in ((1, t - L // 2), (2, t - L)):
        Rcc = Rc[0].T @ Rc[j]
        if rot_noise > 0:
            Rcc = exp_so3(rng.normal(0, rot_noise * (j / 2) ** 0.5, 3)) @ Rcc
        Hs.append(K @ Rcc.T @ Ki)
    P, Wv, T = m["P"], m["W"], m["times"]
    d_far = Rc[0].T @ (P[t] - P[t - L]); d_mid = Rc[0].T @ (P[t] - P[t - L // 2])
    a_far = Rc[0].T @ (P[t] - P[t - L] - Wv[t - L] * (T[t] - T[t - L]))
    a_mid = Rc[0].T @ (P[t] - P[t - L // 2] - Wv[t - L // 2] * (T[t] - T[t - L // 2]))
    g = Rc[0].T @ np.array([0, 0, -1.0])
    if tilt_noise > 0:
        tn = tilt_noise * float(rng.choice([0.5, 1.0, 1.0, 2.0]))
        g = exp_so3(rng.normal(0, tn, 3)) @ g
        # deployment IMU preintegration error over the real 1 s / 0.5 s windows: tilt -> gravity leak, accel bias, white
        b = rng.normal(0, 9.81 * tn, 3) + rng.normal(0, 0.05, 3)
        a_far = a_far + 0.5 * b * 1.0 + rng.normal(0, 0.012, 3)
        a_mid = a_mid + 0.5 * b * 0.25 + rng.normal(0, 0.004, 3)
    img = fl.img(i)
    ims = np.stack([img[t], img[t - L // 2], img[t - L]])
    aux = np.r_[g, m["fxw"][t], a_far, a_mid].astype(np.float32)
    return ims, np.stack(Hs).astype(np.float32), aux, np.r_[d_far, d_mid].astype(np.float32)


class Stream(IterableDataset):
    """teacher-data flights with lags lmin..lmax; optionally a fraction `extra_frac` of samples from `extra` flights
    (server-calibrated, true speed) at exactly 1 s (L = 20)."""
    def __init__(self, cache, recs, seed, lmin, lmax, rot_noise, tilt_noise, extra=None, extra_frac=0.0):
        self.cache, self.recs, self.seed = cache, recs, seed
        self.args = (lmin, lmax, rot_noise, tilt_noise)
        self.extra, self.extra_frac = extra or [], extra_frac

    def __iter__(self):
        wi = torch.utils.data.get_worker_info()
        rng = np.random.default_rng([self.seed, wi.id if wi else 0, int(time.time())])
        fl = Flights(self.cache, self.recs)
        lens = np.array([max(0, np.load(it[1])["R"].shape[0] - 20) for it in fl.items], float)
        p = lens / lens.sum()
        fx = Flights(self.cache, self.extra) if self.extra else None
        lmin, lmax, rn, tn = self.args
        while True:
            if fx is not None and rng.random() < self.extra_frac:
                s = make_sample(fx, int(rng.integers(len(fx.items))), rng, 20, 20, rn, tn)
            else:
                s = make_sample(fl, int(rng.choice(len(p), p=p)), rng, *self.args)
            if s is not None:
                yield s


def fixed_val(cache, recs, n=4096, seed=7):
    fl = Flights(cache, recs); rng = np.random.default_rng(seed); out = []
    lens = np.array([np.load(it[1])["R"].shape[0] for it in fl.items], float)
    p = lens / lens.sum()
    while len(out) < n:
        s = make_sample(fl, int(rng.choice(len(p), p=p)), rng, 20, 72, math.radians(0.4), math.radians(1.0))
        if s is not None:
            out.append(s)
    return [torch.from_numpy(np.stack([o[k] for o in out])) for k in range(4)]


def prepare(ims, Hs, aux, tgt, dev, train):
    ims = ims.to(dev, non_blocking=True).float() / 255.0
    Hs, aux, tgt = Hs.to(dev), aux.to(dev), tgt.to(dev)
    B = ims.shape[0]
    src = ims[:, 1:].reshape(B * 2, 1, H, W)
    wv, wm = warp(src, Hs.reshape(B * 2, 3, 3))
    img = torch.cat([ims[:, :1], wv.reshape(B, 2, H, W)], 1)
    mask = torch.cat([torch.ones_like(ims[:, :1]), wm.reshape(B, 2, H, W)], 1)
    img = img * mask
    if train:
        gain = torch.empty(B, 1, 1, 1, device=dev).uniform_(0.6, 1.4)
        per = torch.empty(B, 3, 1, 1, device=dev).uniform_(0.93, 1.07)
        img = (img * gain * per + torch.randn_like(img) * 0.01).clamp(0, 1) * mask
        flip = torch.rand(B, device=dev) < 0.5
        img = torch.where(flip[:, None, None, None], img.flip(3), img)
        mask = torch.where(flip[:, None, None, None], mask.flip(3), mask)
        sx = torch.where(flip, -1.0, 1.0)
        aux = aux.clone(); aux[:, 0] *= sx; aux[:, 4] *= sx; aux[:, 7] *= sx
        tgt = tgt.clone(); tgt[:, 0] *= sx; tgt[:, 3] *= sx
    return img, mask, aux, tgt


def loss_fn(out, tgt):
    out = out.float()
    mu = torch.cat([out[:, 0:3], out[:, 6:9]], 1)
    ls = torch.cat([out[:, 3:6], out[:, 9:12]], 1).clamp(-6, 3)
    nll = (tgt - mu).abs() * torch.exp(-ls) + ls + 0.5 * (tgt - mu).abs()
    w = torch.tensor([1, 1, 1, .5, .5, .5], device=out.device)
    return (nll * w).mean(), mu, ls


def evaluate(model, val, dev, bs=256):
    model.eval(); errs = []; nlls = []; mags = []; zs = []
    with torch.no_grad():
        for s in range(0, len(val[0]), bs):
            b = [v[s:s + bs] for v in val]
            img, mask, aux, tgt = prepare(*b, dev, False)
            with torch.autocast("cuda", dtype=torch.float16):
                out = model(img, mask, aux)
            l, mu, ls = loss_fn(out, tgt)
            e = (mu[:, :3] - tgt[:, :3]).norm(dim=1)
            errs.append(e.cpu()); nlls.append(l.item()); mags.append(tgt[:, :3].norm(dim=1).cpu())
            zs.append(((mu[:, :3] - tgt[:, :3]).abs() * torch.exp(-ls[:, :3])).mean(1).cpu())
    e = torch.cat(errs).numpy(); m = torch.cat(mags).numpy(); z = torch.cat(zs).numpy()
    res = {"nll": float(np.mean(nlls)), "err_mean": float(e.mean()), "err_med": float(np.median(e)),
           "rel_med": float(np.median(e / np.maximum(m, 0.1))), "zero_err_mean": float(m.mean()),
           "laplace_z_mean": float(z.mean())}
    for lo, hi in ((0, .3), (.3, 1), (1, 2), (2, 9)):
        s = (m >= lo) & (m < hi)
        if s.any():
            res[f"err_{lo}-{hi}"] = float(e[s].mean()); res[f"rel_{lo}-{hi}"] = float((e[s] / m[s]).mean() if lo > 0 else e[s].mean())
    model.train()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="C:/Users/alexa/vio_data")
    ap.add_argument("--out", required=True)
    ap.add_argument("--hours", type=float, default=2.0)
    ap.add_argument("--bs", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1.5e-3)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--lmax", type=int, default=72)
    ap.add_argument("--rot_noise", type=float, default=math.radians(0.4))
    ap.add_argument("--tilt_noise", type=float, default=math.radians(1.0))
    ap.add_argument("--eval_every", type=int, default=2000)
    ap.add_argument("--resume", default="")
    ap.add_argument("--arch", default="v1")
    ap.add_argument("--extra", default="", help="server records json (server_cache.py) mixed in at --extra_frac")
    ap.add_argument("--extra_frac", type=float, default=0.5)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    data = Path(a.data); cache = data / "work/cache"
    recs = json.load(open(data / "work/train_records.json"))
    tr = [r for r in recs if not scene_val(r["scene"])]; va = [r for r in recs if scene_val(r["scene"])]
    dev = "cuda"
    torch.backends.cudnn.benchmark = True
    model = (TeacherV3() if a.arch == "v3" else Teacher()).to(dev).to(memory_format=torch.channels_last)
    if a.resume:
        model.load_state_dict(torch.load(a.resume, map_location=dev)["model"])
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    scaler = torch.amp.GradScaler()
    val = fixed_val(cache, va)
    print("train flights", len(Flights(cache, tr).items), "val flights", len(Flights(cache, va).items), flush=True)
    extra = json.load(open(a.extra)) if a.extra else None
    dl = DataLoader(Stream(cache, tr, 1, 20, a.lmax, a.rot_noise, a.tilt_noise, extra, a.extra_frac), batch_size=a.bs,
                    num_workers=a.workers, pin_memory=True, persistent_workers=True, prefetch_factor=4)
    t0 = time.time(); budget = a.hours * 3600; step = 0; best = 1e9; log = open(out / "log.jsonl", "a")
    run = 0.0
    for ims, Hs, aux, tgt in dl:
        frac = min((time.time() - t0) / budget, 1.0)
        lr = a.lr * (min(1.0, step / 500)) * (0.5 * (1 + math.cos(math.pi * frac)) * 0.97 + 0.03)
        for g in opt.param_groups: g["lr"] = lr
        img, mask, aux, tgt = prepare(ims, Hs, aux, tgt, dev, True)
        with torch.autocast("cuda", dtype=torch.float16):
            o = model(img.contiguous(memory_format=torch.channels_last), mask, aux)
        l, _, _ = loss_fn(o, tgt)
        opt.zero_grad(set_to_none=True)
        scaler.scale(l).backward(); scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        scaler.step(opt); scaler.update()
        run = 0.98 * run + 0.02 * l.item() if step else l.item()
        step += 1
        if step % 200 == 0:
            print(f"step {step} loss {run:.4f} lr {lr:.2e} {(time.time()-t0)/60:.1f} min {step*a.bs/(time.time()-t0):.0f} samp/s", flush=True)
        done = frac >= 1.0
        if step % a.eval_every == 0 or done:
            r = evaluate(model, val, dev); r.update(step=step, minutes=(time.time() - t0) / 60, train_loss=run)
            print("VAL", json.dumps(r), flush=True); log.write(json.dumps(r) + "\n"); log.flush()
            torch.save({"model": model.state_dict(), "step": step, "val": r}, out / "last.pt")
            if r["nll"] < best:
                best = r["nll"]; torch.save({"model": model.state_dict(), "step": step, "val": r}, out / "best.pt")
        if done:
            break
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
