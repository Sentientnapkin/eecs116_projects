"""Attitude parity: the kf_grid C++/Wasm guest's reported orientation vs the Python reference, frame by frame.

    python compare_kfgrid.py <wasm run dir> <python attitude npz dir or -> [--recompute]
--recompute runs attitude_bias.attitudes(arm="kf_grid") in this interpreter (use the OpenCV 4.12 venv to match the
wasm OpenCV). Angles are degrees of the relative rotation between body attitudes (world = first body frame).
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/dev/shm/sebastian-vio/viobench")
from common import Flight
from attitude_bias import attitudes, log_so3


def quat_to_R(q):
    x, y, z, w = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


run = Path(sys.argv[1])
rows = []
for score in json.loads((run / "scores.json").read_text())["rows"]:
    name = score["episode"]
    archive = next(Path("/data/backups/rganapa/Sebastian/tmp/viobench-public-replay").glob(f"*/{name}.zip"))
    flight = Flight(archive)
    R_bc = flight.T_bc[:3, :3]
    tum = np.loadtxt(next((run / name / "report" / "logs").glob("*/estimate.tum")))
    wasm = np.stack([R_bc @ quat_to_R(q) @ R_bc.T for q in tum[:, 4:8]])
    mine, count, _ = attitudes(flight, "kf_grid")
    truth = np.stack([flight.R[0].T @ r for r in flight.R])
    angle = lambda A, B: np.degrees([np.linalg.norm(log_so3(a.T @ b)) for a, b in zip(A, B)])
    d, ew, ep = angle(mine, wasm), angle(truth, wasm), angle(truth, mine)
    rows.append({"episode": name, "accepted_python": count["accepted"], "max_diff_deg": float(d.max()),
                 "diff_at_10s": float(d[200]), "end_err_wasm": float(ew[-1]), "end_err_python": float(ep[-1])})
    print(name[-4:], {k: round(v, 3) if isinstance(v, float) else v for k, v in rows[-1].items() if k != "episode"}, flush=True)
print("median max diff", np.median([r["max_diff_deg"] for r in rows]), "mean end err wasm/python",
      np.mean([r["end_err_wasm"] for r in rows]), np.mean([r["end_err_python"] for r in rows]))
