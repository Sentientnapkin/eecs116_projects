"""Error-over-time decomposition from saved estimate.tum files (camera k in camera-0 frame).

  python errcurve.py --builds b16 G [--gt epdump|proxy]
Per flight: |err| at 3/5/10 s, final RMS (= unaligned ATE), and 'startup share' = err(5 s)^2 / mean err^2.
Truth from work/epdump/<ep>.npz (R, p body in world, T_bc) or, for proxy flights, work/proxydump/<ep>.npz (same keys).
"""
import argparse, glob, json
from pathlib import Path
import numpy as np

DATA = Path("C:/Users/alexa/vio_data/work")


def gt_cam(z):
    R, p, T = z["R"], z["p"], z["T_bc"]
    Rc = R @ T[:3, :3]; pc = p + R @ T[:3, 3]
    return np.einsum("ji,nj->ni", Rc[0], pc - pc[0])  # camera positions in camera-0 frame


def curve(tum, z):
    a = np.loadtxt(tum)
    g = gt_cam(z)
    n = min(len(a), len(g))
    return np.linalg.norm(a[:n, 1:4] - g[:n], axis=1)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--builds", nargs="+", required=True)
    ap.add_argument("--gt", default="epdump"); ap.add_argument("--out", default="")
    a = ap.parse_args()
    res = {}
    for f in sorted(glob.glob(str(DATA / a.gt / "*.npz"))):
        ep = Path(f).stem; z = np.load(f); row = {}
        for b in a.builds:
            t = DATA / "evals" / b / ep / "estimate.tum"
            if not t.exists():
                continue
            e = curve(t, z)
            row[b] = dict(e3=float(e[60]), e5=float(e[100]), e10=float(e[200]), ate=float(np.sqrt((e ** 2).mean())),
                          share5=float(e[100] ** 2 / max((e ** 2).mean(), 1e-9)))
        if row:
            res[ep] = row
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1))
    for b in a.builds:
        r = [v[b] for v in res.values() if b in v]
        if r:
            print(f"{b:10s} n={len(r)} ATE {np.mean([x['ate'] for x in r]):.3f} | err@3s {np.mean([x['e3'] for x in r]):.3f} @5s {np.mean([x['e5'] for x in r]):.3f} @10s {np.mean([x['e10'] for x in r]):.3f}")
    if len(a.builds) == 2:
        b0, b1 = a.builds
        both = [(k, v) for k, v in res.items() if b0 in v and b1 in v]
        worse = sorted(both, key=lambda kv: kv[1][b1]["ate"] - kv[1][b0]["ate"])[-10:]
        print(f"flights where {b1} is worst vs {b0}: ep | ATE {b0}->{b1} | err@5s {b0}->{b1} | err@10s")
        for k, v in worse[::-1]:
            print(f"  {k[:34]:34s} {v[b0]['ate']:.2f}->{v[b1]['ate']:.2f} | {v[b0]['e5']:.2f}->{v[b1]['e5']:.2f} | {v[b0]['e10']:.2f}->{v[b1]['e10']:.2f}")


if __name__ == "__main__":
    main()
