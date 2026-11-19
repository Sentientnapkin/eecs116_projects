"""Fresh actual-Wasm public reproduction of the strongest cross-roster existing guest."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

import numpy as np
import wasm_eval as we

PIN = "9b1b07906aff5a3e6f00155e7aecf967d90aa960"
REFERENCE = Path("/data/backups/rganapa/Sebastian/baselines/runs/public-n2-218-ungated")
EXPECTED = "089559dbb11ccc4ff5b912930497b725ddc39d2344b794521db9d19cfd849915"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--score-existing", action="store_true", help="Re-score this fresh replay's saved reports without new inference")
    args = parser.parse_args()
    args.out = args.out.resolve()
    assert subprocess.check_output(["git", "-C", str(we.SRC), "rev-parse", "HEAD"], text=True).strip() == PIN
    assert not subprocess.check_output(["git", "-C", str(we.SRC), "diff", "HEAD", "--"], text=True)
    guest = json.loads((REFERENCE / "guest.json").read_text())
    assert we.sha256(guest["wasm"]) == guest["sha256"] == EXPECTED
    assert len(guest["archives"]) == len(set(guest["archives"])) == 10
    hashes = {a: we.sha256(a) for a in guest["archives"]}
    if args.score_existing:
        saved = json.loads((args.out / "guest.json").read_text())
        assert saved["sha256"] == EXPECTED and saved["archives"] == guest["archives"]
        assert saved["archive_sha256"] == hashes and saved["evaluator_commit"] == PIN
        guest = saved
    else:
        args.out.mkdir(parents=True, exist_ok=False)
        guest.update(evaluator_commit=PIN, archive_sha256=hashes,
                     label="N2 seed218 historical kf_grid; original rolling model inputs", fresh_inference=True,
                     scope="local official VIOBench evaluator on public only; no server submission")
        (args.out / "guest.json").write_text(json.dumps(guest, indent=2) + "\n")
        with ThreadPoolExecutor(10) as pool:
            for report in pool.map(lambda a: we.run_one(guest["wasm"], a, args.out), guest["archives"]):
                print("finished", report, report.exists(), flush=True)
    rows = [we.score_one(a, args.out / Path(a).stem) for a in guest["archives"]]
    (args.out / "scores.json").write_text(json.dumps({"guest": guest, "rows": rows}, indent=2) + "\n")
    if any("ate_full" not in row for row in rows):
        raise RuntimeError("Missing score; preserved all reports instead of excluding failed flights")
    assert we.sha256(guest["wasm"]) == EXPECTED
    for a, digest in guest["archive_sha256"].items():
        assert we.sha256(a) == digest
    summary = {"guest": guest, "metric": "equal-flight mean unaligned trajectory RMSE", "episodes": len(rows),
               "completed": sum(r["completed"] for r in rows), "frames": sum(r["frames"] for r in rows),
               "filled_frames": sum(r["filled_full"] for r in rows),
               "mean_ate_m": float(np.mean([r["ate_full"] for r in rows])),
               "mean_30s_ate_m": float(np.mean([r["ate_30s"] for r in rows])),
               "peak_whole_guest_fuel_per_frame": max(r["peak_fuel_per_frame"] for r in rows),
               "rows": rows, "qualification": "Historical visual path has documented Python/native/Wasm parity limitations"}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("guest", "rows")}, indent=2), flush=True)


if __name__ == "__main__":
    main()
