"""Score cheap-guest models on stage-3 sets, and check that the local sets reproduce the server's verdicts.

    ~/.venv_gru/bin/python s3eval.py [CKPT.pt ...]
Sets: ~/data/imucache/s3va, s3te (dataset val/test), s3nb (the 236 downloaded neighbours: top-10 per hidden episode).
For s3nb it also builds a per-hidden-episode estimate (mean ATE over that episode's neighbours) and compares it with
the server's per-episode ATE, for the models that were submitted.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import export_mlp as em  # noqa: E402
import fit_cheap as fc  # noqa: E402

S3 = os.path.join(HERE, "..", "stage3")
SUBMITTED = {  # server id -> checkpoint
    "fbd48a479fe639a2": os.path.expanduser("~/data/gru_mlprelu_H16_full_s2.pt"),
    "049eb610e7b78afc": os.path.expanduser("~/data/mlpfit_g27_H16relu_hw1_px_s0.pt"),
}


def model_ate(sets, m):
    return {n: np.array([em.ate(f, m) if m else float(np.sqrt((f["cam"] ** 2).sum(1).mean())) for f in S]) for n, S in sets.items()}


def main():
    sets = {n: fc.load(f"~/data/imucache/{n}") for n in ("s3va", "s3te", "s3nb")}
    print({n: len(S) for n, S in sets.items()})
    models = {"zero": None} | {k: em.load(v) for k, v in SUBMITTED.items()} | {os.path.basename(p): em.load(p) for p in sys.argv[1:]}
    res = {k: model_ate(sets, m) for k, m in models.items()}
    server = {sid: [e["metrics"]["ate_rmse"] for e in json.load(open(os.path.join(S3, "server", sid + ".json")))["results"]["episodes"]]
              for sid in list(SUBMITTED) + ["6b316c1f9da012f7"]}
    server["zero"] = server.pop("6b316c1f9da012f7")
    A = json.load(open(os.path.join(S3, "match_stage_a.json")))
    names = [f["name"] for f in sets["s3nb"]]
    print(f"{'model':28s} {'val':>7s} {'test':>7s} {'nbr-est':>8s} {'server':>7s}  corr(nbr-est, server per episode)")
    for k, r in res.items():
        nb = dict(zip(names, r["s3nb"]))
        est = np.array([np.mean([nb[c["id"]] for c in a["candidates"][:10] if c["id"] in nb]) for a in A])
        sv = np.array(server[k]) if k in server else None
        corr = f"{np.corrcoef(np.log(est), np.log(sv))[0, 1]:+.2f}" if sv is not None else ""
        mean = lambda a: a.mean() if len(a) else float("nan")
        print(f"{k:28s} {mean(r['s3va']):7.3f} {mean(r['s3te']):7.3f} {est.mean():8.3f} "
              f"{sv.mean() if sv is not None else float('nan'):7.3f}  {corr}")


if __name__ == "__main__":
    main()
