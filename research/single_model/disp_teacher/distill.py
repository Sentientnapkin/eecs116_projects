"""Distil the displacement teacher into the student (model.student(), ~4x fewer MACs).

  vio_env/Scripts/python distill.py --teacher runs/t1/best.pt --out runs/s1 --hours 1.2

loss = Laplace NLL(student, truth)                                  (own calibrated uncertainty)
     + KD  * mean |mu_s - mu_t| / b_t                               (imitate the teacher where it is confident)
     + HINT * mse(proj(h_s), h_t)                                   (teacher fc2 features; proj is train-only)
Same sampler/augmentation/validation split as train.py; both nets see the identical augmented batch.
"""
import argparse, json, math, time
from pathlib import Path
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from model import Teacher, student
from train import Stream, fixed_val, prepare, loss_fn, evaluate, scene_val


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="C:/Users/alexa/vio_data")
    ap.add_argument("--teacher", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--hours", type=float, default=1.0); ap.add_argument("--bs", type=int, default=64)
    ap.add_argument("--lr", type=float, default=2e-3); ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--kd", type=float, default=0.5); ap.add_argument("--hint", type=float, default=0.1)
    ap.add_argument("--init", default=""); ap.add_argument("--eval_every", type=int, default=2000)
    ap.add_argument("--extra", default=""); ap.add_argument("--extra_frac", type=float, default=0.5)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    data = Path(a.data); cache = data / "work/cache"
    recs = json.load(open(data / "work/train_records.json"))
    tr = [r for r in recs if not scene_val(r["scene"])]; va = [r for r in recs if scene_val(r["scene"])]
    dev = "cuda"; torch.backends.cudnn.benchmark = True
    T = Teacher().to(dev); T.load_state_dict(torch.load(a.teacher, map_location=dev)["model"]); T.eval()
    for p in T.parameters(): p.requires_grad_(False)
    S = student().to(dev)
    if a.init:
        S.load_state_dict(torch.load(a.init, map_location=dev)["model"])
    proj = nn.Linear(S.fc2.out_features, T.fc2.out_features).to(dev)
    opt = torch.optim.AdamW(list(S.parameters()) + list(proj.parameters()), lr=a.lr, weight_decay=1e-4)
    scaler = torch.amp.GradScaler()
    val = fixed_val(cache, va)
    rT = evaluate(T, val, dev); print("TEACHER VAL", json.dumps(rT), flush=True)
    extra = json.load(open(a.extra)) if a.extra else None
    dl = DataLoader(Stream(cache, tr, 2, 20, 72, math.radians(0.4), math.radians(1.0), extra, a.extra_frac), batch_size=a.bs,
                    num_workers=a.workers, pin_memory=True, persistent_workers=True, prefetch_factor=4)
    t0 = time.time(); budget = a.hours * 3600; step = 0; best = 1e9; run = 0.0; log = open(out / "log.jsonl", "a")
    for ims, Hs, aux, tgt in dl:
        frac = min((time.time() - t0) / budget, 1.0)
        lr = a.lr * min(1.0, step / 500) * (0.5 * (1 + math.cos(math.pi * frac)) * 0.97 + 0.03)
        for g in opt.param_groups: g["lr"] = lr
        img, mask, aux, tgt = prepare(ims, Hs, aux, tgt, dev, True)
        with torch.autocast("cuda", dtype=torch.float16):
            with torch.no_grad():
                ot, ht = T(img, mask, aux, feats=True)
            os_, hs = S(img, mask, aux, feats=True)
        l_gt, mu_s, _ = loss_fn(os_, tgt)
        ot = ot.float()
        mu_t = torch.cat([ot[:, 0:3], ot[:, 6:9]], 1)
        b_t = torch.exp(torch.cat([ot[:, 3:6], ot[:, 9:12]], 1).clamp(-6, 3))
        l_kd = ((mu_s - mu_t).abs() / (b_t + 0.02)).mean()
        l_hint = (proj(hs.float()) - ht.float()).pow(2).mean()
        l = l_gt + a.kd * l_kd + a.hint * l_hint
        opt.zero_grad(set_to_none=True)
        scaler.scale(l).backward(); scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(S.parameters(), 5.0)
        scaler.step(opt); scaler.update()
        run = 0.98 * run + 0.02 * l_gt.item() if step else l_gt.item(); step += 1
        if step % 200 == 0:
            print(f"step {step} gt {run:.4f} kd {l_kd.item():.3f} hint {l_hint.item():.3f} lr {lr:.2e} {(time.time()-t0)/60:.1f} min", flush=True)
        done = frac >= 1.0
        if step % a.eval_every == 0 or done:
            r = evaluate(S, val, dev); r.update(step=step, minutes=(time.time() - t0) / 60)
            print("VAL", json.dumps(r), flush=True); log.write(json.dumps(r) + "\n"); log.flush()
            torch.save({"model": S.state_dict(), "step": step, "val": r}, out / "last.pt")
            if r["nll"] < best:
                best = r["nll"]; torch.save({"model": S.state_dict(), "step": step, "val": r}, out / "best.pt")
        if done:
            break
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
