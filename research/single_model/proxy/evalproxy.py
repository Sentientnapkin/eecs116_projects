"""Score a wasm on the new proxy flights (vio_data/proxy/*.zip), in parallel; rows -> work/evals/px_<name>/rows.json.

  vio_eval/Scripts/python -I evalproxy.py --wasm X.wasm --name b16 [--ref b16] [--workers 6] [--split test|train|all]
Rows carry speed setting, length, start type, scene; the report breaks results down by speed. --split: the roster's
scene-level split (proxy_split.json: 'test' scenes are never used for training or selection of trained models).
"""
import argparse, json, shutil, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "disp_teacher"))
from evalrun import run_one, paired, stats  # noqa: E402

DATA = Path("C:/Users/alexa/vio_data")
HERE = Path(__file__).parent


def episodes(split="all"):
    sp = json.load(open(HERE / "proxy_split.json")) if (HERE / "proxy_split.json").exists() else {}
    out = []
    for z in sorted((DATA / "proxy").glob("*.zip")):
        m = json.loads(z.with_suffix(".json").read_text())
        role = sp.get(m["scene"], "test")
        if split != "all" and role != split:
            continue
        out.append(dict(id=z.stem, scene=m["scene"], fold=-1, zip=str(z), start_offset_s=m["crop_start_s"],
                        speed=m["speed"], seconds=m["seconds"], travel=m.get("travel_m"), role=role))
    return out


def report(name, rows, ref=None):
    ok = [r for r in rows if r.get("ate") is not None]
    print(f"== px_{name}: {len(ok)}/{len(rows)} scored")
    print(f"  all    {stats([r['ate'] for r in ok])} | sim3 {np.mean([r['sim3'] for r in ok]):.3f}")
    for k in ("D", "M", "K", "K2", "K3"):
        s = [r for r in ok if r["speed"] == k]
        if s:
            print(f"  {k:6s} {stats([r['ate'] for r in s])}")
    for st in ("static", "mid"):
        s = [r for r in ok if r["start"] == st]
        if s:
            print(f"  {st:6s} {stats([r['ate'] for r in s])}")
    print(f"  peak fuel max {max(r['peak'] for r in ok) / 1e6:.1f} M")
    if ref:
        rr = {r["episode"]: r for r in json.load(open(DATA / f"work/evals/px_{ref}/rows.json")) if r.get("ate") is not None}
        c = [r for r in ok if r["episode"] in rr]
        if c:
            d, lo, hi = paired([rr[r["episode"]]["ate"] for r in c], [r["ate"] for r in c], [r["scene"] for r in c])
            print(f"  vs px_{ref} n={len(c)} d={d:+.3f} [{lo:+.3f},{hi:+.3f}] ref mean {np.mean([rr[r['episode']]['ate'] for r in c]):.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wasm", required=True); ap.add_argument("--name", required=True); ap.add_argument("--ref")
    ap.add_argument("--workers", type=int, default=6); ap.add_argument("--split", default="all")
    a = ap.parse_args()
    root = DATA / "work/evals" / f"px_{a.name}"; root.mkdir(parents=True, exist_ok=True)
    wasm = root / "solution.wasm"
    if wasm.exists() and Path(a.wasm).read_bytes() != wasm.read_bytes():
        raise SystemExit(f"{wasm} exists with different content: use a new --name")
    if not wasm.exists():
        shutil.copy(a.wasm, wasm)
    eps = episodes(a.split); t0 = time.time(); rows = []
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(run_one, wasm, e, root): e for e in eps}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result(); e = futs[f]
            r.update(speed=e["speed"], seconds=e["seconds"], travel=e["travel"], role=e["role"]); rows.append(r)
            if i % 20 == 0 or i == len(eps):
                print(f"{i}/{len(eps)} {time.time() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: r["episode"])
    old = {}
    if (root / "rows.json").exists():
        old = {r["episode"]: r for r in json.load(open(root / "rows.json"))}
    old.update({r["episode"]: r for r in rows})
    allrows = sorted(old.values(), key=lambda r: r["episode"])
    (root / "rows.json").write_text(json.dumps(allrows, indent=1))
    report(a.name, [r for r in allrows if a.split == "all" or r.get("role") == a.split], a.ref)


if __name__ == "__main__":
    main()
