"""Export a gru_fit.py MLP checkpoint to mlp_weights.h for cheap_mlp.c, and check it.

  ~/.venv_gru/bin/python export_mlp.py CKPT.pt [EV_DIR]
Folds the input normalisation into W1/B1 and the output bias into Wv[:, 0]. Prints the numpy-model ATE on
~/data/imucache/ho; with EV_DIR (build.sh eval output) also compares it with the wasm per episode.
"""
import json, os, sys
import numpy as np
import torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit_cheap as fc

HERE = os.path.dirname(os.path.abspath(__file__))


def load(ck):
    c = torch.load(ck, weights_only=False); s = {k: v.numpy() for k, v in c["state"].items()}
    mu, sd = c["mu"], c["sd"]
    W1 = s["l1.weight"] / sd; B1 = s["l1.bias"] - W1 @ mu
    Wv = s["Wlin"].copy(); Wv[:, 0] += s["out.bias"]
    return dict(Wv=Wv, W1=W1, B1=B1, W2=s["out.weight"], act=c.get("act", os.environ.get("ACT", "tanh")))


def act(z, a):
    return np.tanh(z) if a == "tanh" else z / (1 + np.abs(z)) if a == "softsign" else np.maximum(z, 0)


def ate(f, m):
    R, X = fc.prep(f)
    v = X @ m["Wv"].T + act(X[:, 1:] @ m["W1"].T + m["B1"], m["act"]) @ m["W2"].T
    p = np.vstack([np.zeros(3), np.cumsum(fc.DT * np.einsum("kij,kj->ki", R, v), 0)])
    return float(np.sqrt(((p - f["cam"]) ** 2).sum(1).mean()))


def main():
    m = load(sys.argv[1]); H = len(m["B1"])
    fmt = lambda r: "{" + ", ".join(f"{x:.12g}" for x in r) + "}"
    with open(os.path.join(HERE, "mlp_weights.h"), "w") as fh:
        fh.write(f"/* export_mlp.py from {os.path.basename(sys.argv[1])}: act={m['act']}, H={H}, GROWS={fc.GROWS} */\n")
        fh.write(f"#define GROW_A {fc.GROWS[0]}\n#define GROW_B {fc.GROWS[1]}\n#define NF 10\n#define MH {H}\n")
        fh.write(f"#define ACT_{m['act'].upper()} 1\n")
        fh.write("static const double Wv[3][NF] = {\n" + ",\n".join("  " + fmt(r) for r in m["Wv"]) + "};\n")
        fh.write("static const double W1[MH][9] = {\n" + ",\n".join("  " + fmt(r) for r in m["W1"]) + "};\n")
        fh.write("static const double B1[MH] = " + fmt(m["B1"]) + ";\n")
        fh.write("static const double W2[3][MH] = {\n" + ",\n".join("  " + fmt(r) for r in m["W2"]) + "};\n")
    ho = fc.load("~/data/imucache/ho")
    r = {f["name"]: ate(f, m) for f in ho}
    print(f"wrote mlp_weights.h (H={H}, {m['act']}); numpy model ho n={len(r)} ATE mean {np.mean(list(r.values())):.4f}")
    if len(sys.argv) > 2:
        eps = json.load(open(os.path.join(sys.argv[2], "episodes.json")))
        d = np.array([(e["metrics"]["ate_rmse"], r[e["name"]]) for e in eps if e["name"] in r])
        print(f"parity n={len(d)} wasm {d[:,0].mean():.4f} python {d[:,1].mean():.4f} max |diff| {np.abs(d[:,0]-d[:,1]).max():.2e}")


if __name__ == "__main__":
    main()
