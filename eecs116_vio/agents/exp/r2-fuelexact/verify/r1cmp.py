import glob, os, numpy as np
for d in ("twin120", "hard", "black", "blank", "dark"):
    r = []
    for f in sorted(glob.glob(os.path.expanduser(f"~/data/agents/r2v_{d}/*.npz"))):
        z2 = np.load(f); z1 = np.load(f.replace("r2v_", "vpar_"))
        r.append(((z2["fc"] / z1["fc"]).max(), z2["fc"].max() / z1["fc"].max()))
    r = np.array(r); print(d, len(r), "max per-frame r2/r1 %.4f  per-flight peak r2/r1 max %.4f median %.4f" % (r[:, 0].max(), r[:, 1].max(), np.median(r[:, 1])))
