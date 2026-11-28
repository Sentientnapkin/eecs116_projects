"""Upper bound for a scene-type switch: one velocity scale per scene type (true labels) on top of an MLP checkpoint.

    ~/.venv_gru/bin/python s3cls.py CKPT.pt
Fits alpha_class by trajectory least squares on s3tr, scores s3va and the 236 neighbours (s3nb), against alpha = global.
"""
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import export_mlp as em  # noqa: E402
import fit_cheap as fc  # noqa: E402

DT = fc.DT
CLS = {r["id"]: r["setting_class"] for r in csv.DictReader(open(os.path.join(HERE, "..", "stage3", "manifest.csv"), newline=""))}


def column(f, m):
    R, X = fc.prep(f)
    v = X @ m["Wv"].T + em.act(X[:, 1:] @ m["W1"].T + m["B1"], m["act"]) @ m["W2"].T
    return np.vstack([np.zeros(3), np.cumsum(DT * np.einsum("kij,kj->ki", R, v), 0)])   # p for alpha = 1


def main():
    m = em.load(sys.argv[1])
    ex = {x.strip() for x in open(os.path.join(HERE, "..", "stage3", "ids_s3nb.txt"))}
    sets = {n: fc.load(f"~/data/imucache/{n}") for n in ("s3tr", "s3va", "s3nb")}
    sets["s3tr"] = [f for f in sets["s3tr"] if f["name"] not in ex]
    P = {n: [(column(f, m), f["cam"], CLS[f["name"]]) for f in S] for n, S in sets.items()}
    def fit(rows, key):
        num, den = {}, {}
        for p, c, k in rows:
            g = key(k); w = 1 / max(np.sqrt((c ** 2).sum(1).mean()), 1)
            num[g] = num.get(g, 0) + w * (p * c[:len(p)]).sum(); den[g] = den.get(g, 0) + w * (p * p).sum()
        return {g: num[g] / den[g] for g in num}
    def score(rows, a, key):
        return np.mean([np.sqrt(((a[key(k)] * p - c[:len(p)]) ** 2).sum(1).mean()) for p, c, k in rows])
    for name, key in (("one scale", lambda k: "all"), ("per scene type", lambda k: k)):
        a = fit(P["s3tr"], key)
        print(f"{name:15s} alpha {dict((k, round(v, 3)) for k, v in a.items())}  val {score(P['s3va'], a, key):.3f}  nbr {score(P['s3nb'], a, key):.3f}")
    print(f"{'zero':15s} val {np.mean([np.sqrt((c ** 2).sum(1).mean()) for _, c, _ in P['s3va']]):.3f}  "
          f"nbr {np.mean([np.sqrt((c ** 2).sum(1).mean()) for _, c, _ in P['s3nb']]):.3f}")


if __name__ == "__main__":
    main()
