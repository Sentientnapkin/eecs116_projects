"""Server-matched local set by fingerprint: each server episode is described by its ATE under several builds that were
scored both on the server and locally; the local flights with the nearest fingerprints stand in for that episode.

  python fingerprint.py --fp base=base G=G B16=b16 best_5977=srv_ms_m7 lowfuel_try=srv_lowfuel_try \
                        --test B17=s3_e1i3 [--k 3] [--filter 'fold>=2'] [--write matched.json]
--fp builds define the fingerprint (log ATE); --test builds are NOT used for matching and are predicted: for each server
episode, the mean of the test build's ATE over its k nearest local flights; prediction = mean over the 12 episodes.
Leave-one-out check: the prediction for a --test build is honest only if that build is absent from --fp.
--extra NAME=LOCAL: builds without server scores, reported on the same matched set (candidates).
"""
import argparse, json
from pathlib import Path
import numpy as np

DATA = Path("C:/Users/alexa/vio_data/work")
HERE = Path(__file__).parent


def rows(local, filt=None):
    d = {}
    for r in json.load(open(DATA / "evals" / local / "rows.json")):
        if r.get("ate") is None or (filt and not filt(r)):
            continue
        d[r["episode"]] = r
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fp", nargs="+", required=True); ap.add_argument("--test", nargs="*", default=[])
    ap.add_argument("--extra", nargs="*", default=[]); ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--filter", default=""); ap.add_argument("--write", default="")
    a = ap.parse_args()
    srv = json.load(open(HERE / "server_results.json"))
    filt = (lambda r: eval(a.filter, {}, r)) if a.filter else None
    fp = dict(x.split("=") for x in a.fp); te = dict(x.split("=") for x in a.test); ex = dict(x.split("=") for x in a.extra)
    loc = {k: rows(v, filt) for k, v in {**fp, **te, **ex}.items()}
    common = sorted(set.intersection(*[set(d) for d in loc.values()]))
    F = np.log(np.array([[loc[b][e]["ate"] for b in fp] for e in common]))
    S = np.log(np.array([srv["builds"][b]["ate"] for b in fp])).T  # (12, nb)
    mu, sd = F.mean(0), F.std(0) + 1e-6
    Fz, Sz = (F - mu) / sd, (S - mu) / sd
    D = ((Sz[:, None, :] - Fz[None]) ** 2).sum(-1)  # (12, n)
    nn = np.argsort(D, 1)[:, :a.k]
    w = np.zeros(len(common))
    for i in range(12):
        w[nn[i]] += 1.0 / (12 * a.k)
    print(f"local flights {len(common)}; matched {int((w > 0).sum())} distinct; mean fingerprint distance "
          f"{np.mean(np.take_along_axis(D, nn, 1)) ** .5:.2f} (z units, {len(fp)} builds)")
    print(f"{'build':12s} {'server':>7s} {'matched':>8s} {'all-local':>9s}")
    for b in list(fp) + list(te):
        x = np.array([loc[b][e]["ate"] for e in common])
        tag = "" if b in fp else "  <- not used for matching"
        print(f"{b:12s} {srv['builds'][b]['mean']:7.3f} {np.dot(w, x):8.3f} {x.mean():9.3f}{tag}")
    for b in ex:
        x = np.array([loc[b][e]["ate"] for e in common])
        print(f"{b:12s} {'-':>7s} {np.dot(w, x):8.3f} {x.mean():9.3f}  (candidate)")
    for b in te:
        x = np.array([loc[b][e]["ate"] for e in common])
        for r in fp:
            y = np.array([loc[r][e]["ate"] for e in common])
            sd_ = srv["builds"][b]["mean"] - srv["builds"][r]["mean"]
            print(f"  {r}->{b}: server {sd_:+.3f} matched {np.dot(w, x - y):+.3f} all-local {np.mean(x - y):+.3f}")
    if a.write:
        Path(a.write).write_text(json.dumps({e: float(v) for e, v in zip(common, w) if v > 0}, indent=1))


if __name__ == "__main__":
    main()
