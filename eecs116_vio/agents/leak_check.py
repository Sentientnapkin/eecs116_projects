"""Check that a training set does not contain any of the 120 twin (proxy test) flights.

    python leak_check.py SOURCE [SOURCE ...] [--exclude IDS.txt ...]

Each SOURCE is an ids .txt file (one flight name per line, first token), a directory of flights (*.zip / *.npz,
e.g. ~/data/imucache/s3nbtr), or a single flight file. Exits 1 if any twin flight is found, 0 if clean.
--exclude removes flights the trainer drops itself (mlp_fit.py EXCLUDE=...), so the check is on the set actually
trained on. The usual exclusion list is ../stage3/ids_excl_nb_twin.txt (twins plus their neighbours).
Note: the raw ids_s3nbtr.txt / ids_s3va.txt lists DO contain twins; they are only clean after the exclusion.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
TWIN = {l.split("\t")[1].strip() for l in (HERE.parent / "stage3" / "twin" / "twin120.txt").read_text().splitlines() if l.strip()}


def names(src):
    p = pathlib.Path(os.path.expanduser(src))
    if p.is_dir():
        return {f.name.split(".")[0] for f in p.iterdir() if f.suffix in (".zip", ".npz")}
    if p.suffix == ".txt":
        return {l.split()[0] for l in p.read_text().splitlines() if l.strip()}
    return {p.name.split(".")[0]}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    args, excl = sys.argv[1:], set()
    while "--exclude" in args:
        i = args.index("--exclude")
        excl |= names(args[i + 1])
        del args[i:i + 2]
    bad = False
    for src in args:
        n = names(src) - excl
        hit = sorted(n & TWIN)
        print(f"{src}: {len(n)} flights, {len(hit)} twin flights" + (f"  LEAK: {', '.join(hit[:8])}{' ...' if len(hit) > 8 else ''}" if hit else "  clean"))
        bad |= bool(hit)
    sys.exit(1 if bad else 0)
