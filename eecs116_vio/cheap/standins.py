"""Pick local stand-ins for the 12 hidden server episodes by matching the submitted cheap model's metric fingerprint.

  python standins.py FP.json SERVER_RESULTS.json OUT.json [K]
FP.json: fingerprint.py output for the SUBMITTED model; SERVER_RESULTS.json: its /submissions/<id> result.
Only pools listed in ELIGIBLE (never used for training) are matched. For each server episode the K nearest local flights
(standardised log metrics) are kept; prints how well the stand-in set reproduces the server numbers.
"""
import json, sys
import numpy as np

ELIGIBLE = {"ho", "tune_fconf", "tune_st1conf", "tune_st2conf"}
FEATS = [("distance_travelled", True), ("ate_rmse", True), ("sim3_scale", True), ("sim3_ate_rmse", True), ("velocity_rmse", True),
         ("angular_velocity_rmse", True), ("rotation_rmse", True), ("rpe_translation_rmse", True), ("final_drift", True)]


def vec(m):
    return np.array([np.log(max(m[k], 1e-3)) if lg else m[k] for k, lg in FEATS])


def main():
    fp = [r for r in json.load(open(sys.argv[1])) if "metrics" in r and r["pool"] in ELIGIBLE]
    srv = [e for e in json.load(open(sys.argv[2]))["results"]["episodes"] if e.get("metrics")]
    K = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    L = np.array([vec(r["metrics"]) for r in fp]); mu, sd = L.mean(0), L.std(0)
    Z = (L - mu) / sd
    chosen = {}
    print(f"pool {len(fp)} eligible flights; K={K}")
    print(f"{'server ep':10s} {'dist':>5s} {'ATE':>6s} {'scale':>5s} | stand-ins: {'dist':>5s} {'ATE':>6s} {'scale':>5s} {'zero':>5s}  nearest z-dist")
    for e in srv:
        z = (vec(e["metrics"]) - mu) / sd; d = np.sqrt(((Z - z) ** 2).sum(1)); idx = np.argsort(d)[:K]
        chosen[e["hash"][:6]] = [fp[i]["name"] for i in idx]
        s = [fp[i]["metrics"] for i in idx]
        print(f"{e['hash'][:6]:10s} {e['metrics']['distance_travelled']:5.1f} {e['metrics']['ate_rmse']:6.2f} {e['metrics']['sim3_scale']:5.2f} |"
              f"            {np.mean([m['distance_travelled'] for m in s]):5.1f} {np.mean([m['ate_rmse'] for m in s]):6.2f} "
              f"{np.mean([m['sim3_scale'] for m in s]):5.2f} {np.mean([m['zero_ate'] for m in s]):5.2f}  {d[idx[0]]:.2f}-{d[idx[-1]]:.2f}"
              f"  ({', '.join(sorted(set(fp[i]['pool'] for i in idx)))})")
    names = sorted({n for v in chosen.values() for n in v}); by = {r["name"]: r["metrics"] for r in fp}
    sm = lambda k: np.mean([by[n][k] for n in names])
    print(f"\nstand-in set ({len(names)} unique): submitted model ATE {sm('ate_rmse'):.2f} vs zero {sm('zero_ate'):.2f}  (server: 7.79 vs 4.69)")
    for k in ["sim3_scale", "velocity_rmse", "angular_velocity_rmse", "rpe_translation_rmse"]:
        print(f"   {k:22s} stand-ins {np.median([by[n][k] for n in names]):.3f}   server {np.median([e['metrics'][k] for e in srv]):.3f}")
    print(f"   {'rotation deg':22s} stand-ins {np.degrees(np.median([by[n]['rotation_rmse'] for n in names])):.1f}   server {np.degrees(np.median([e['metrics']['rotation_rmse'] for e in srv])):.1f}")
    json.dump({"per_episode": chosen, "names": names, "pools": {r["name"]: r["pool"] for r in fp if r["name"] in names}},
              open(sys.argv[3], "w"), indent=1)


if __name__ == "__main__":
    main()
