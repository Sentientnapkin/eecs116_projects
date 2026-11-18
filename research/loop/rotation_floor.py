"""Oracle: true body velocity integrated with the estimated attitude. The remaining error is
what attitude (gyro) errors alone cost, i.e. the floor for any velocity-only teacher."""
import json, sys
import numpy as np
sys.path.insert(0, ".")
from odometry_store import open_store
from odometry_data import load_row
from odometry_train import sim3_ate
store = open_store("hf:teacher-full", "data/hub-cache", 20)
manifest = json.loads(store.manifest_path().read_text())
rows = []
for r in manifest["datasets"]["development"]:
    row = load_row(store, r)
    v = row["v"].astype(np.float64)
    world = (row["R"] @ v[..., None]).squeeze(-1)
    p = np.zeros_like(world)
    p[1:] = np.cumsum(.5*(world[1:]+world[:-1])*np.diff(row["times"])[:, None], axis=0)
    arm, rot = row["T_bc"][:3, 3], row["T_bc"][:3, :3]
    p = (p+row["R"]@arm-arm)@rot
    ate = float(np.sqrt(np.mean(np.sum((p-row["cam_gt"])**2, axis=1))))
    rows.append((r["scene"], r["crop_s"], ate, sim3_ate(p, row["cam_gt"])))
    print("%-20s crop %d  unaligned %.3f  sim3 %.3f" % rows[-1])
print("mean unaligned %.3f  mean sim3 %.3f" % (np.mean([x[2] for x in rows]), np.mean([x[3] for x in rows])))
