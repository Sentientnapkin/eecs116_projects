"""Replace the embedded startup-net weights (#define LC_SIGSCALE ... LC_H2B array) of a B16-family source.

  python splice_lc.py --src b16s_snapshot.c --weights runs_lc/S1/lc_weights.h --out out/x.c [--sigscale 1.0]
"""
import argparse, re
from pathlib import Path


def block(text):
    i = text.index("#define LC_SIGSCALE")
    j = text.index("static const float LC_H2B[")
    j = text.index("};", j) + 2
    return i, j


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--src", required=True); ap.add_argument("--weights", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--sigscale", type=float, default=None)
    a = ap.parse_args()
    s = Path(a.src).read_text(); w = Path(a.weights).read_text()
    wi, wj = block(w); new = w[wi:wj]
    if a.sigscale is not None:
        new = re.sub(r"#define LC_SIGSCALE [0-9.eE+-]+f", f"#define LC_SIGSCALE {a.sigscale}f", new)
    i, j = block(s)
    Path(a.out).write_text(s[:i] + new + s[j:])
    print("spliced", a.weights, "->", a.out)


if __name__ == "__main__":
    main()
