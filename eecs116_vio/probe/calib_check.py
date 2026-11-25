"""Check the fuel channel on the local calibration runs (calib_run.sh): constant base fuel, exact decoding."""
import glob, json, os, re, sys
import numpy as np

OUT = os.path.expanduser("~/probe_calib")
G = dict(G1=(590, 1130), G2=(1130, 1185), G3=(1185, 1198), G4=(1199, 1200))
N = dict(G1=1 << 16, G2=1 << 23, G3=1 << 26, G4=1 << 29)
rows = []
for i in range(len(open(f"{OUT}/list").read().split())):
    rel = json.load(open(glob.glob(f"{OUT}/release_{i}/report-*/report.json")[0]))["episodes"][0]
    fuel = np.load(glob.glob(f"{OUT}/release_{i}/report-*/logs/*/fuel.npy")[0])
    err = open(glob.glob(f"{OUT}/debug_{i}/report-*/logs/*/stderr.txt")[0]).read()
    if "PROBEX" not in err:
        print(i, len(fuel), "frames: no payload (short episode)"); continue
    X = [int(v) for v in re.search(r"PROBEX (.*)", err).group(1).split()]
    raw = re.search(r"PROBER (.*)", err).group(1)
    rows.append((rel, fuel, X, raw))
    print(i, len(fuel), "frames; X =", X)

for rel, fuel, X, raw in rows:
    if len(fuel) != 1200:
        print("skip (frames != 1200)", len(fuel)); continue
    XI, X1, X2, X3, X4, X0 = X
    n = np.zeros(1200, np.int64)
    n[590:1130] = N["G1"] + (X1 << 2); n[1130:1185] = N["G2"] + (X2 << 2); n[1185:1199] = N["G3"] + (X3 << 2)
    n[1198] += X0 << 2; n[1199] = N["G4"] + (X4 << 2)
    # base fuel W + c n per frame; fit c from the burn frames against G0's mode
    base0 = np.bincount(fuel[1:589].astype(np.int64) - int(fuel[1:589].min())).argmax() + int(fuel[1:589].min())
    c = (fuel[1199] - base0) / n[1199]
    resid = fuel - base0 - c * n
    print(f"base {base0}  c {c:.6f}  resid by frame: unique {np.unique(np.round(resid)).size}  "
          f"nonzero frames {np.flatnonzero(np.round(resid) != 0).tolist()[:12]}  init {rel['fuel_init']}")

print("\nper-episode residuals at the payload frames and init (must be the same in every episode):")
for rel, fuel, X, raw in rows:
    if len(fuel) != 1200: continue
    XI, X1, X2, X3, X4, X0 = X
    n = np.zeros(1200, np.int64)
    n[590:1130] = N["G1"] + (X1 << 2); n[1130:1185] = N["G2"] + (X2 << 2); n[1185:1199] = N["G3"] + (X3 << 2)
    n[1198] += X0 << 2; n[1199] = N["G4"] + (X4 << 2)
    r = fuel.astype(np.int64) - 4496894 - 11 * n
    init_r = rel["fuel_init"] - 11 * ((1 << 12) + (XI << 10))
    print(f"r589 {r[589]}  r1129 {r[1129]}  r0 {r[0]}  init_resid {init_r}  total_resid {int(r.sum())}  "
          f"max {rel['fuel_per_frame_max']} median {rel['fuel_per_frame_median']} p95 {rel['fuel_per_frame_p95']} p99 {rel['fuel_per_frame_p99']}")
