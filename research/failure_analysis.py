"""Failure-mode analysis of guests on the server-benchmark pool.

    python failure_analysis.py --scores <bench-eval out dir> [--raw gen/raw-bench] [--weights calibration.json]

Reads the per-guest scores.json written by bench_eval.py and the per-flight audit files written by the generator,
and reports, for every guest: the score distribution; how often it is worse than outputting nothing (ATE above the
flight's zero-motion ATE, i.e. the identity pose); the heavy tail (what share of the total error the worst 10% of
flights carry); which truth-side flight properties predict its error relative to the flight's extent (Spearman rank
correlation, no model assumption); initialization time for the VIO guests; and which flights fail for several guests.
Every statistic is mean unaligned ATE or a rank statistic over it.
"""
import argparse
import glob
import json
from pathlib import Path

import numpy as np


def ranks(x):
    order = np.argsort(x, kind="mergesort")
    r = np.empty(len(x)); r[order] = np.arange(len(x))
    for value in np.unique(x):  # average ranks over ties
        m = x == value
        if m.sum() > 1: r[m] = r[m].mean()
    return r


def spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 8 or np.ptp(a[ok]) == 0 or np.ptp(b[ok]) == 0: return np.nan
    return float(np.corrcoef(ranks(a[ok]), ranks(b[ok]))[0, 1])


def load(scores_dir, raw):
    flights = {}
    for path in glob.glob(f"{raw}/bench/*.json"):
        d = json.loads(Path(path).read_text()); a = d["audit"]
        flights[d["id"]] = {"id": d["id"], "group": d["group"], "catalog": d["catalog"], "scene": d["scene"],
                            "zero": a["zero_motion_ate_m"], "travel": a["travel_m"], "speed_p50": a["speed_p10_p50_p90"][1],
                            "speed_p90": a["speed_p10_p50_p90"][2], "hover": a["hover_fraction"], "turning": a["turning_fraction"],
                            "lateral": a["lateral_fraction"], "vertical": a["vertical_fraction"], "dark": a["dark_fraction"],
                            "flat": a["flat_fraction"], "start_offset": float(d.get("crop_start_s", 0) or 0)}
    guests = {}
    for path in sorted(glob.glob(f"{scores_dir}/*/scores.json")):
        d = json.loads(Path(path).read_text()); name = d["guest"]["name"]
        guests[name] = {r["episode"]: r for r in d["rows"] if r.get("ate_full") is not None}
    return flights, guests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", required=True)
    parser.add_argument("--raw", default="/data/backups/rganapa/Sebastian/gen/raw-bench")
    parser.add_argument("--only", help="JSON file with {'selected': [ids]} (e.g. calibration.json): restrict to these flights")
    parser.add_argument("--output")
    args = parser.parse_args()
    flights, guests = load(args.scores, args.raw)
    names = sorted(flights)
    if args.only:
        keep = set(json.loads(Path(args.only).read_text())["selected"]); names = [n for n in names if n in keep]
    features = ["zero", "travel", "speed_p50", "speed_p90", "hover", "turning", "lateral", "vertical", "dark", "flat", "start_offset"]
    F = {k: np.array([flights[n][k] for n in names], float) for k in features}
    zero = F["zero"]
    report = {"flights": len(names), "guests": {}}
    print(f"{len(names)} flights; zero-motion ATE (the identity pose) mean {zero.mean():.3f}\n")
    worse = {}
    for guest, rows in guests.items():
        ate = np.array([rows[n]["ate_full"] if n in rows else np.nan for n in names])
        ok = np.isfinite(ate)
        if ok.sum() < 8: continue
        a, z = ate[ok], zero[ok]
        order = np.sort(a)[::-1]; tail = order[:max(1, len(a)//10)].sum()/a.sum()
        ratio = a/z
        worse[guest] = np.where(ok, ate > zero, False)
        inits = np.array([rows[n].get("initialized_at_s") if n in rows and rows[n].get("initialized_at_s") is not None else np.nan for n in names])
        entry = {"n": int(ok.sum()), "mean": float(a.mean()), "median": float(np.median(a)), "p90": float(np.percentile(a, 90)), "max": float(a.max()),
                 "mean_over_zero": float(a.mean()/z.mean()), "median_flight_ratio": float(np.median(ratio)),
                 "worse_than_identity": float(np.mean(a > z)), "ate_over_3m": float(np.mean(a > 3)),
                 "top10pct_share_of_total_error": float(tail), "mean_without_worst_5pct": float(np.sort(a)[:int(.95*len(a))].mean())}
        print(f"{guest:16s} n={ok.sum():4d} mean {a.mean():7.3f} median {np.median(a):6.3f} p90 {np.percentile(a, 90):7.3f} max {a.max():8.2f} | "
              f"worse than identity {100*np.mean(a > z):4.1f}%  >3 m {100*np.mean(a > 3):4.1f}%  worst-10% carry {100*tail:4.1f}% of error  "
              f"trimmed(95%) mean {entry['mean_without_worst_5pct']:.3f}")
        if np.isfinite(inits).sum() > 5:
            late = np.isfinite(inits) & (inits > 3)
            entry["init_median_s"] = float(np.nanmedian(inits)); entry["never_initialized"] = float(np.mean(~np.isfinite(inits[ok])))
            print(f"{'':16s} initialized: median {np.nanmedian(inits):.1f}s, p90 {np.nanpercentile(inits, 90):.1f}s, never {100*np.mean(~np.isfinite(inits[ok])):.1f}%; "
                  f"mean ATE if init <=3 s {np.nanmean(ate[np.isfinite(inits) & (inits <= 3)]):.3f} vs later {np.nanmean(ate[late]) if late.any() else float('nan'):.3f}")
        entry["spearman_ratio_vs_feature"] = {k: spearman(ratio, F[k][ok]) for k in features if k != "zero"}
        entry["spearman_ate_vs_zero"] = spearman(a, z)
        report["guests"][guest] = entry
    print("\nSpearman(ATE/zero-ATE, flight property): which properties make a guest relatively worse")
    cols = [k for k in features if k != "zero"]
    print(f"{'':16s}" + "".join(f"{c:>10s}" for c in cols) + f"{'ATE~zero':>10s}")
    for guest, e in report["guests"].items():
        print(f"{guest:16s}" + "".join(f"{e['spearman_ratio_vs_feature'][c]:10.2f}" for c in cols) + f"{e['spearman_ate_vs_zero']:10.2f}")
    print("\nBy flight extent (zero-motion ATE terciles): mean ATE per guest")
    cuts = np.percentile(zero, [33, 67]); bins = np.digitize(zero, cuts)
    print(f"{'':16s}" + "".join(f"{'extent ' + lab:>16s}" for lab in ("low", "mid", "high")))
    for guest, rows in guests.items():
        ate = np.array([rows[n]["ate_full"] if n in rows else np.nan for n in names])
        if np.isfinite(ate).sum() < 8: continue
        print(f"{guest:16s}" + "".join(f"{np.nanmean(ate[bins == b]):16.3f}" for b in range(3)))
    print("\nBy catalog / group: mean ATE per guest")
    for key in ("catalog", "group"):
        labels = sorted({flights[n][key] for n in names})
        print(f"{key:16s}" + "".join(f"{l:>14s}" for l in labels))
        for guest, rows in guests.items():
            ate = np.array([rows[n]["ate_full"] if n in rows else np.nan for n in names])
            if np.isfinite(ate).sum() < 8: continue
            print(f"{guest:16s}" + "".join(f"{np.nanmean(ate[np.array([flights[n][key] == l for n in names])]):14.3f}" for l in labels))
    vio = [g for g in ("openvins", "vins_mono") if g in worse]
    learned = [g for g in ("b_d0", "n2_kfgrid", "n2_kfinputs") if g in worse]
    if len(vio) == 2:
        both = np.mean([(guests[vio[0]].get(n, {}).get("ate_full", 0) > 3) and (guests[vio[1]].get(n, {}).get("ate_full", 0) > 3) for n in names])
        print(f"\nflights where both OpenVINS and VINS-Mono exceed 3 m: {100*both:.1f}%")
        report["both_vio_over_3m"] = float(both)
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main()
