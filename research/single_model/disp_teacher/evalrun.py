"""Windows-native scorer: `viobench evaluate` per episode in parallel on the server-calibrated set.

  python -I evalrun.py --wasm X.wasm --name b16 [--ref b16] [--slice visible|search|val] [--workers 14]

Slices follow run_variant.py: fold = sha256(catalog:scene)[:8] % 5; search = 0,1,2; val = 3; sealed = 4 (never scored
here). Rows -> <data>/work/evals/<name>/rows.json; a paired scene-bootstrap vs --ref is printed if given.
"""
import argparse, hashlib, json, os, shutil, subprocess, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np

DATA = Path("C:/Users/alexa/vio_data")
VIOBENCH = "C:/Users/alexa/vio_eval/Scripts/viobench.exe"


def fold(e):
    return int(hashlib.sha256((e["catalog"] + ":" + e["scene"]).encode()).hexdigest()[:8], 16) % 5


def episodes(sl):
    eps = json.load(open(DATA / "server-calibrated/manifest.json"))["episodes"]
    out = []
    for e in eps:
        f = fold(e)
        if f == 4 and sl != "f34":
            continue  # fold 4 is only opened by the explicit 'f34' slice (2026-11-21: HF folds 3-4 = held-out test of the startup students)
        if sl == "f34" and f not in (3, 4): continue
        if sl == "search" and f > 2: continue
        if sl == "val" and f != 3: continue
        if sl == "f23" and f not in (2, 3): continue
        z = DATA / "server-calibrated" / e["file"]
        if z.exists():
            out.append(dict(e, fold=f, zip=str(z)))
    return out


def run_one(wasm, ep, root):
    work = root / ep["id"]
    rep = work / "row.json"
    if rep.exists():
        return json.loads(rep.read_text())
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    p = subprocess.run([VIOBENCH, "evaluate", str(wasm), ep["zip"]], cwd=work, capture_output=True, text=True)
    reps = list(work.glob("report-*/report.json"))
    row = dict(episode=ep["id"], scene=ep["scene"], fold=ep["fold"], start="mid" if ep.get("start_offset_s", 0) > 0 else "static")
    if not reps:
        row["error"] = (p.stdout[-500:] + p.stderr[-500:]); return row
    e = json.loads(reps[0].read_text())["episodes"][0]
    m = e.get("metrics") or {}
    row.update(ate=m.get("ate_rmse"), sim3=m.get("sim3_ate_rmse"), completed=e["completed"], filled=m.get("filled_frames"),
               peak=e["fuel_per_frame_max"], median_fuel=e["fuel_per_frame_median"], stderr=e.get("stderr_tail", "")[-300:])
    tum = list(work.glob("report-*/logs/*/estimate.tum"))
    if tum:
        shutil.copy(tum[0], work / "estimate.tum")
    for d in work.glob("report-*"):
        shutil.rmtree(d, ignore_errors=True)
    rep.write_text(json.dumps(row))
    return row


def stats(v):
    v = np.asarray(v, float)
    return f"n={len(v):3d} mean {v.mean():.3f} median {np.median(v):.3f} p90 {np.percentile(v, 90):.2f} >3m {(v > 3).sum():2d} >5m {(v > 5).sum():2d} max {v.max():.2f}"


def paired(a, b, scenes, n=4000, seed=1):
    rng = np.random.default_rng(seed); d = np.asarray(b) - np.asarray(a)
    u = sorted(set(scenes)); idx = {s: [i for i, x in enumerate(scenes) if x == s] for s in u}
    bs = [d[[i for p in rng.integers(0, len(u), len(u)) for i in idx[u[p]]]].mean() for _ in range(n)]
    return d.mean(), *np.percentile(bs, [2.5, 97.5])


def report(name, rows, ref=None):
    ok = [r for r in rows if r.get("ate") is not None]
    print(f"== {name}: {len(ok)}/{len(rows)} scored; errors {len(rows) - len(ok)}")
    for sl, sel in (("all", ok), ("search", [r for r in ok if r["fold"] <= 2]), ("val", [r for r in ok if r["fold"] == 3]),
                    ("static", [r for r in ok if r["start"] == "static"]), ("mid", [r for r in ok if r["start"] == "mid"])):
        if sel:
            print(f"  {sl:6s} {stats([r['ate'] for r in sel])} | sim3 {np.mean([r['sim3'] for r in sel]):.3f}")
    print(f"  peak fuel max {max(r['peak'] for r in ok)/1e6:.1f} M, median-frame {np.median([r['median_fuel'] for r in ok])/1e6:.1f} M")
    if ref:
        rr = {r["episode"]: r for r in json.load(open(DATA / f"work/evals/{ref}/rows.json")) if r.get("ate") is not None}
        for sl, f in (("all", lambda r: True), ("search", lambda r: r["fold"] <= 2), ("val", lambda r: r["fold"] == 3),
                      ("f23", lambda r: r["fold"] in (2, 3)), ("f01", lambda r: r["fold"] in (0, 1))):
            common = [r for r in ok if r["episode"] in rr and f(r)]
            if common:
                d, lo, hi = paired([rr[r["episode"]]["ate"] for r in common], [r["ate"] for r in common], [r["scene"] for r in common])
                print(f"  vs {ref} [{sl}] n={len(common)} d={d:+.3f} [{lo:+.3f},{hi:+.3f}]  ref mean {np.mean([rr[r['episode']]['ate'] for r in common]):.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wasm", required=True); ap.add_argument("--name", required=True)
    ap.add_argument("--ref"); ap.add_argument("--slice", default="visible"); ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    root = DATA / "work/evals" / a.name; root.mkdir(parents=True, exist_ok=True)
    wasm = root / "solution.wasm"
    if not wasm.exists() or Path(a.wasm).read_bytes() != wasm.read_bytes():
        if wasm.exists():
            raise SystemExit(f"{wasm} exists with different content: use a new --name")
        shutil.copy(a.wasm, wasm)
    eps = episodes(a.slice)
    if a.limit:
        eps = eps[:a.limit]
    t0 = time.time(); rows = []
    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(run_one, wasm, e, root) for e in eps]
        for i, f in enumerate(as_completed(futs), 1):
            rows.append(f.result())
            if i % 20 == 0 or i == len(eps):
                print(f"{i}/{len(eps)} {time.time() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: r["episode"])
    (root / "rows.json").write_text(json.dumps(rows, indent=1))
    report(a.name, rows, a.ref)


if __name__ == "__main__":
    main()
