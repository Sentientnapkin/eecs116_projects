"""Does a local test set behave like the server? Compare builds that were scored on both.

  python calib.py --set hf --map base=base G=G B16=b16 B17=s3_e1i3 [--filter 'fold>=2'] [--weights w.json]
--map SERVER_NAME=LOCAL_EVAL_DIR (server names from server_results.json). Reports, for each pair of builds, the server's
12-episode mean difference vs the local mean difference and the probability that a random 12-flight draw from the local
set has the same sign as the server (the server itself is one such draw if the set is faithful), plus per-episode
pattern counts (share of episodes where one build beats the other by > 0.5 m).
"""
import argparse, json, itertools
from pathlib import Path
import numpy as np

DATA = Path("C:/Users/alexa/vio_data/work")
HERE = Path(__file__).parent


def load(local, filt=None, set_name="hf"):
    rows = json.load(open(DATA / "evals" / local / "rows.json"))
    out = {}
    for r in rows:
        if r.get("ate") is None:
            continue
        if filt and not filt(r):
            continue
        out[r["episode"]] = r["ate"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", nargs="+", required=True); ap.add_argument("--filter", default="")
    ap.add_argument("--weights", default=""); ap.add_argument("--draws", type=int, default=20000)
    a = ap.parse_args()
    srv = json.load(open(HERE / "server_results.json"))["builds"]
    m = dict(kv.split("=") for kv in a.map)
    filt = (lambda r: eval(a.filter, {}, r)) if a.filter else None
    loc = {k: load(v, filt) for k, v in m.items()}
    common = sorted(set.intersection(*[set(d) for d in loc.values()]))
    w = np.ones(len(common))
    if a.weights:
        W = json.load(open(a.weights)); w = np.array([W.get(e, 0.0) for e in common])
    w = w / w.sum()
    X = {k: np.array([loc[k][e] for e in common]) for k in m}
    print(f"common flights: {len(common)}")
    print(f"{'build':8s} {'server':>8s} {'local':>8s} {'ratio':>6s}")
    for k in m:
        print(f"{k:8s} {srv[k]['mean']:8.3f} {np.dot(w, X[k]):8.3f} {np.dot(w, X[k]) / srv[k]['mean']:6.2f}")
    rng = np.random.default_rng(0)
    idx = rng.choice(len(common), size=(a.draws, 12), p=w)
    print(f"\n{'pair':14s} {'srv d':>7s} {'loc d':>7s} {'P(sign)':>8s} | srv/loc share A>B+0.5 | srv/loc share B>A+0.5")
    for A, B in itertools.combinations(m, 2):
        sd = srv[B]["mean"] - srv[A]["mean"]
        d = X[B] - X[A]
        ld = np.dot(w, d)
        dm = d[idx].mean(1)
        ps = float(np.mean(np.sign(dm) == np.sign(sd)))
        sa, sb = np.array(srv[A]["ate"]), np.array(srv[B]["ate"])
        print(f"{A + '->' + B:14s} {sd:+7.3f} {ld:+7.3f} {ps:8.2f} | {np.mean(sa > sb + .5):.2f}/{np.dot(w, X[A] > X[B] + .5):.2f}"
              f"            | {np.mean(sb > sa + .5):.2f}/{np.dot(w, X[B] > X[A] + .5):.2f}")
    for k in m:
        s = np.array(srv[k]["ate"])
        print(f"{k:8s} median srv {np.median(s):.2f} loc {np.median(X[k]):.2f} | >2 m srv {np.mean(s > 2):.2f} loc {np.dot(w, X[k] > 2):.2f}")


if __name__ == "__main__":
    main()
