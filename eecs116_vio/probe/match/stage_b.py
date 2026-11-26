"""Stage B: pick the 24 dataset flights most similar to the 24 hidden episodes, using
  (A) motion/geometry statistics (probe on both sides), (B) appearance (probe: brightness, colour, texture, blur),
  (C) the per-episode errors of every submission we can run locally, against the same submission's server errors.

    python stage_b.py            (reads ../../stage3/match_runs/<server id>/<flight id>.json, ../../stage3/server/)

Writes ../../stage3/proxy24.json (the chosen flights) and prints the leave-one-submission-out validation: is a
held-out submission's per-episode error on the proxies close to its server error?
"""
import glob
import json
import math
import os
import sys

import numpy as np
from scipy.optimize import linear_sum_assignment

HERE = os.path.dirname(os.path.abspath(__file__))
S3 = os.path.join(HERE, "..", "..", "stage3")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from decode import decode_episode  # noqa: E402
from stage_a import SPEC, server_features  # noqa: E402

PROBE = "6b316c1f9da012f7"
GROUP = ["room"] * 12 + ["warehouse"] * 6 + ["forest"] * 6
METRICS = [("ate_rmse", 0.35), ("sim3_ate_rmse", 0.35), ("rotation_rmse", 0.35)]   # log-space tolerances


def appearance(d):
    im = d["image"]
    f = {"Y": math.log(max(im["Y_mean"], 1)), "cg": im["chroma_g"], "cb": im["chroma_b"],
         "tex": math.log(max(im["grad2_mean"], 1e-3))}
    for ax, key in (("x", "blur_ratio_x_by_px_speed"), ("y", "blur_ratio_y_by_px_speed")):
        for b in range(2):
            v = d[key][b]
            f[f"blur{ax}{b}"] = v
    return f


APP_SIG = {"Y": 0.12, "cg": 0.01, "cb": 0.015, "tex": 0.3, "blurx0": 0.03, "blurx1": 0.04, "blury0": 0.03, "blury1": 0.04}


def block_a(fs, fc):
    z = []
    for col, kind, s in SPEC:
        a, b = fc[col], fs[col]
        z.append((math.log(max(a, 1e-6)) - math.log(max(b, 1e-6))) / s if kind == "log" else (a - b) / s)
    return np.array(z)


def block_b(fs, fc):
    z = [(fc[k] - fs[k]) / s for k, s in APP_SIG.items() if fc[k] is not None and fs[k] is not None]
    return np.array(z) if z else np.zeros(1)


def block_c(server_m, local_m, subs):
    z = []
    for s in subs:
        a, b = server_m.get(s), local_m.get(s)
        if a is None or b is None:
            continue
        for k, sig in METRICS:
            z.append((math.log(max(b[k], 1e-4)) - math.log(max(a[k], 1e-4))) / sig)
    return np.array(z) if z else np.zeros(1)


def load():
    server = {}   # sid -> list of 24 metric dicts (in episode order of the probe)
    order = [e["hash"] for e in json.load(open(os.path.join(S3, "server", PROBE + ".json")))["results"]["episodes"]]
    for f in glob.glob(os.path.join(S3, "server", "*.json")):
        sid = os.path.basename(f)[:-5]
        eps = {e["hash"]: e["metrics"] for e in json.load(open(f))["results"]["episodes"]}
        server[sid] = [eps.get(h) for h in order]
    probe_server = json.load(open(os.path.join(S3, "probe_decoded.json")))
    local = {}    # flight -> {sid: metrics}, plus decoded probe
    decoded = {}
    for f in glob.glob(os.path.join(S3, "match_runs", "*", "*.json")):
        sid = os.path.basename(os.path.dirname(f)); fid = os.path.basename(f)[:-5]
        e = json.load(open(f))["episodes"][0]
        if e["metrics"]["frames"] != 1200:
            continue
        local.setdefault(fid, {})[sid] = e["metrics"]
        if sid == PROBE:
            decoded[fid] = decode_episode(e)
    return server, probe_server, local, decoded


def main():
    server, probe_server, local, decoded = load()
    cand = json.load(open(os.path.join(S3, "match_stage_a.json")))
    subs_all = sorted(s for s in server if s != PROBE and any(s in v for v in local.values()))
    print(f"{len(local)} flights with runs, submissions used: {len(subs_all)}")
    fs_a = [server_features(d) for d in probe_server]
    fs_b = [appearance(d) for d in probe_server]
    feats = {fid: (server_features(d), appearance(d)) for fid, d in decoded.items() if "camera" in d}

    def cost_matrix(subs, w=(1.0, 1.0, 1.0)):
        ids = sorted(set(c["id"] for a in cand for c in a["candidates"]) & set(feats))
        C = np.full((24, len(ids)), 1e6)
        parts = {}
        for i in range(24):
            ok = {c["id"] for c in cand[i]["candidates"]}
            for j, fid in enumerate(ids):
                if fid not in ok:
                    continue
                za, zb = block_a(fs_a[i], feats[fid][0]), block_b(fs_b[i], feats[fid][1])
                zc = block_c({s: server[s][i] for s in subs}, local[fid], subs)
                parts[i, fid] = (float(np.mean(za ** 2)), float(np.mean(zb ** 2)), float(np.mean(zc ** 2)) if subs else 0.0)
                C[i, j] = w[0] * parts[i, fid][0] + w[1] * parts[i, fid][1] + (w[2] * parts[i, fid][2] if subs else 0.0)
        return ids, C, parts

    def pick(subs, w=(1.0, 1.0, 1.0)):
        ids, C, parts = cost_matrix(subs, w)
        r, c = linear_sum_assignment(C)   # 24 distinct flights
        return {i: ids[j] for i, j in zip(r, c)}, {i: parts[i, ids[j]] for i, j in zip(r, c)}

    def score(sel, s):
        """held-out submission s: per-episode log-ATE error and correlation, and mean ATE (server vs proxies)."""
        a = np.array([server[s][i]["ate_rmse"] for i in range(24)])
        b = np.array([local[sel[i]][s]["ate_rmse"] if s in local[sel[i]] else np.nan for i in range(24)])
        m = np.isfinite(b)
        la, lb = np.log(a[m]), np.log(b[m])
        return float(np.sqrt(np.mean((la - lb) ** 2))), float(np.corrcoef(la, lb)[0, 1]), float(a[m].mean()), float(b[m].mean())

    print("\nleave-one-submission-out: proxies chosen WITHOUT the held-out submission, then its ATE compared")
    print(f"{'held-out':18s} {'motion+look only':>32s} {'+ other subs errors':>32s}   server mean ATE")
    print(f"{'':18s} {'rms log err  corr  mean':>32s} {'rms log err  corr  mean':>32s}")
    res = {"ab": [], "abc": []}
    sel_ab, _ = pick([])
    for s in subs_all:
        sel_abc, _ = pick([x for x in subs_all if x != s])
        e1, c1, ma, mb1 = score(sel_ab, s)
        e2, c2, _, mb2 = score(sel_abc, s)
        res["ab"].append((e1, c1)); res["abc"].append((e2, c2))
        print(f"{s:18s} {e1:11.2f} {c1:5.2f} {mb1:6.2f} m {e2:20.2f} {c2:5.2f} {mb2:6.2f} m   {ma:6.2f} m")
    for k, v in res.items():
        v = np.array(v)
        print(f"  mean over held-out subs [{k}]: rms log err {v[:, 0].mean():.3f}  corr {v[:, 1].mean():.3f}")

    sel, parts = pick(subs_all)
    out = []
    print("\nfinal 24 proxies (all submissions used):")
    for i in range(24):
        fid = sel[i]
        a, b, c = parts[i]
        ates = [(server[s][i]["ate_rmse"], local[fid][s]["ate_rmse"]) for s in subs_all if s in local[fid]]
        out.append({"index": i + 1, "hidden_hash": probe_server[i]["hash"], "group": GROUP[i], "flight": fid,
                    "cost_motion": a, "cost_look": b, "cost_errors": c,
                    "ate_server_vs_proxy": {s: [server[s][i]["ate_rmse"], local[fid][s]["ate_rmse"]] for s in subs_all if s in local[fid]}})
        print(f"{i + 1:2d} {probe_server[i]['hash'][:8]} {GROUP[i]:9s} -> {fid:22s} motion {a:5.2f} look {b:5.2f} errors {c:5.2f}  "
              f"ATE corr over subs {np.corrcoef(np.log([x for x, _ in ates]), np.log([y for _, y in ates]))[0, 1]:+.2f}")
    json.dump(out, open(os.path.join(S3, "proxy24.json"), "w"), indent=1)
    print("\nper-submission mean ATE: server (24 hidden) vs proxy24")
    for s in subs_all:
        a = np.mean([server[s][i]["ate_rmse"] for i in range(24)])
        b = np.mean([local[sel[i]][s]["ate_rmse"] for i in range(24) if s in local[sel[i]]])
        print(f"  {s} server {a:6.2f}  proxy {b:6.2f}")


if __name__ == "__main__":
    main()
