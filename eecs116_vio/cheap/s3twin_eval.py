"""Score cheap-guest checkpoints on the friend's server-twin sets (HF viobench-stage3 twin/): twin24 (one flight per
hidden episode) and twin120 (5 per episode, per-episode mean), next to the server's per-episode ATE where known.

    ~/.venv_gru/bin/python s3twin_eval.py [CKPT.pt ...]        (GROWS env as for the checkpoint)
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import export_mlp as em  # noqa: E402
import fit_cheap as fc  # noqa: E402
from s3eval import SUBMITTED  # noqa: E402

S3 = os.path.join(HERE, "..", "stage3")


def rows(name):
    return [l.split("\t")[:2] for l in open(os.path.join(S3, "twin", name)).read().split("\n") if l.strip()]


def main():
    F = {f["name"]: f for f in fc.load("~/data/imucache/twin")}
    t24, t120 = rows("twin24.txt"), rows("twin120.txt")
    models = {"zero": None} | {k: em.load(v) for k, v in SUBMITTED.items()} | {os.path.basename(p): em.load(p) for p in sys.argv[1:]}
    server = {sid: np.array([e["metrics"]["ate_rmse"] for e in json.load(open(os.path.join(S3, "server", sid + ".json")))["results"]["episodes"]])
              for sid in list(SUBMITTED) + ["6b316c1f9da012f7"]}
    server["zero"] = server.pop("6b316c1f9da012f7")
    print(f"{'model':36s} {'twin24':>7s} {'corr':>5s} {'twin120':>8s} {'corr':>5s} {'server':>7s}")
    for k, m in models.items():
        a = {n: (em.ate(f, m) if m else float(np.sqrt((f["cam"] ** 2).sum(1).mean()))) for n, f in F.items()}
        e24 = np.array([a[n] for _, n in t24])
        e120 = np.array([np.mean([a[n] for i, n in t120 if int(i) == ep]) for ep in range(1, 25)])
        sv = server.get(k)
        c = lambda e: f"{np.corrcoef(np.log(e), np.log(sv))[0, 1]:+.2f}" if sv is not None else "    "
        print(f"{k:36s} {e24.mean():7.3f} {c(e24):>5s} {e120.mean():8.3f} {c(e120):>5s} {sv.mean() if sv is not None else float('nan'):7.3f}")


if __name__ == "__main__":
    main()
