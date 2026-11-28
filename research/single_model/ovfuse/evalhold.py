"""Score a wasm ONCE on the downloaded holdout flights (vio_data/holdout240/flights/*.zip; one-shot final check).

  vio_eval/Scripts/python -I evalhold.py --wasm X.wasm --name NAME [--workers 12] [--parity]
Rows -> work/evals/ho_<NAME>/rows.json. Refuses a NAME that was already scored (holdout rule: nothing here is tuned).
Compares with the other workflow's per-flight holdout tables (eval/tables/table_*.json) on the same flights.
--parity: allowed to rerun builds that already have a table (B16, T4uB, HFG), to check that local scoring matches.
"""
import argparse, json, shutil, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "disp_teacher"))
from evalrun import run_one, paired, stats  # noqa: E402

DATA = Path("C:/Users/alexa/vio_data")
HO = DATA / "holdout240"
LEDGER = Path(__file__).parent / "holdout_ledger.txt"


def episodes():
    tags = json.loads((HO / "eval/tags.json").read_text())
    out = []
    for z in sorted((HO / "flights").glob("*.zip")):
        t = tags.get(z.stem, {})
        out.append(dict(id=z.stem, scene=str(t.get("scene", z.stem)), fold=-1, zip=str(z), start_offset_s=0,
                        start_type=t.get("start", "mid" if z.stem.startswith("fastmid") else "static")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wasm", required=True); ap.add_argument("--name", required=True)
    ap.add_argument("--workers", type=int, default=12); ap.add_argument("--parity", action="store_true")
    a = ap.parse_args()
    root = DATA / "work/evals" / f"ho_{a.name}"
    done = LEDGER.read_text().split() if LEDGER.exists() else []
    if a.name in done and not (root / "rows.json").exists():
        raise SystemExit(f"holdout rule: {a.name} already scored")
    root.mkdir(parents=True, exist_ok=True)
    wasm = root / "solution.wasm"
    if wasm.exists() and Path(a.wasm).read_bytes() != wasm.read_bytes():
        raise SystemExit(f"{wasm} exists with different content: holdout is one-shot, use a new --name only for a new build")
    if not wasm.exists():
        shutil.copy(a.wasm, wasm)
    if a.name not in done:
        with open(LEDGER, "a") as f:
            f.write(a.name + "\n")
    eps = episodes(); t0 = time.time(); rows = []
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(run_one, wasm, e, root): e for e in eps}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result(); r["start"] = futs[f]["start_type"]; rows.append(r)
            if i % 10 == 0 or i == len(eps):
                print(f"{i}/{len(eps)} {time.time() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: r["episode"])
    (root / "rows.json").write_text(json.dumps(rows, indent=1))
    ok = [r for r in rows if r.get("ate") is not None]
    print(f"== ho_{a.name}: {len(ok)}/{len(rows)} scored")
    print(f"  all    {stats([r['ate'] for r in ok])}")
    for st in ("static", "mid"):
        s = [r for r in ok if r["start"] == st]
        if s:
            print(f"  {st:6s} {stats([r['ate'] for r in s])}")
    print(f"  peak fuel max {max(r['peak'] for r in ok) / 1e6:.1f} M")
    mine = {r["episode"]: r for r in ok}
    for t in sorted((HO / "eval/tables").glob("table_*.json")):
        ref = {r["episode"]: r["ate"] for r in json.loads(t.read_text()) if r.get("ate") is not None}
        c = [e for e in mine if e in ref]
        if len(c) >= 10:
            d, lo, hi = paired([ref[e] for e in c], [mine[e]["ate"] for e in c], [mine[e]["scene"] for e in c])
            print(f"  vs {t.stem[6:]:8s} n={len(c)} ref {np.mean([ref[e] for e in c]):.3f} d={d:+.3f} [{lo:+.3f},{hi:+.3f}]")


if __name__ == "__main__":
    main()
