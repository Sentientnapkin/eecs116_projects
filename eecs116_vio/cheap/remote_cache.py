"""Build cache_imu.py caches for viobench-stage3 flights straight from Hugging Face, reading only the small zip members
(IMU, ground truth, metadata: ~2.5 MB of a ~550 MB zip) with HTTP range requests.

    python3 remote_cache.py OUT_DIR MANIFEST.csv IDS_FILE [JOBS]
    python3 remote_cache.py --check LOCAL_ZIP          # stub-zip cache == full-zip cache (bit-exact)?

Same npz layout as cache_imu.py (t, imu, cam, Rc0c, Tbc, Rwb0), so fit_cheap.load / mlp_fit.prep_set read it.
"""
import csv
import io
import os
import sys
import tempfile
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np

URL = "https://huggingface.co/datasets/SentientNapkin/viobench-stage3/resolve/main/"


class HTTPRange(io.RawIOBase):
    """Seekable read-only file over HTTP range requests (resolves the CDN redirect once)."""

    def __init__(self, url):
        r = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60)
        self.url, self.size, self.pos = r.geturl(), int(r.headers["Content-Length"]), 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        for attempt in range(6):
            try:
                req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"})
                data = urllib.request.urlopen(req, timeout=60).read()
                break
            except Exception:
                if attempt == 5:
                    raise
        self.pos += len(data)
        return data

    def readinto(self, b):
        d = self.read(len(b)); b[:len(d)] = d; return len(d)


def stub_zip(src, dst):
    """Copy every non-PNG member of zip `src` (path or file object) into `dst`."""
    with zipfile.ZipFile(src) as z, zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED) as out:
        for info in z.infolist():
            if not info.filename.endswith(".png"):
                out.writestr(info, z.read(info.filename))


def cache_from_zip(path):
    """The arrays cache_imu.py saves (verbatim logic)."""
    from viobench.tools.datasets.storage import read_episode
    from viobench.tools.geometry import interpolate_poses, poses_to_matrices
    ep = read_episode(path, frames="lazy")
    t = ep.frame_times; F = len(t)
    imu = np.stack([ep.imu_window(i) for i in range(1, F)])
    tr = ep.ground_truth
    M = poses_to_matrices(interpolate_poses(tr[:, 0], tr[:, 1:8], t))
    Tbc = ep.T_body_camera; Rbc, tbc = Tbc[:3, :3], Tbc[:3, 3]
    Rwb, pwb = M[:, :3, :3], M[:, :3, 3]
    pc = pwb + np.einsum("nij,j->ni", Rwb, tbc); Rwc = Rwb @ Rbc
    cam = (pc - pc[0]) @ Rwc[0]
    Rc0c = np.einsum("ji,njk->nik", Rwc[0], Rwc)
    return dict(t=t, imu=imu, cam=cam, Rc0c=Rc0c, Tbc=Tbc, Rwb0=Rwb[0])


def one(args):
    out, row = args
    dst = os.path.join(out, row["id"] + ".npz")
    if os.path.exists(dst):
        return "have " + row["id"]
    try:
        with tempfile.TemporaryDirectory() as tmp:
            stub = os.path.join(tmp, row["id"] + ".zip")
            stub_zip(io.BufferedReader(HTTPRange(URL + row["path"]), buffer_size=1 << 20), stub)
            np.savez(dst + ".tmp.npz", **cache_from_zip(stub))
        os.replace(dst + ".tmp.npz", dst)
        return "ok " + row["id"]
    except Exception as e:
        return f"ERR {row['id']} {e}"


def main():
    if sys.argv[1] == "--check":
        full = cache_from_zip(sys.argv[2])
        with tempfile.TemporaryDirectory() as tmp:
            stub = os.path.join(tmp, "x.zip"); stub_zip(sys.argv[2], stub); part = cache_from_zip(stub)
        print({k: bool(np.array_equal(full[k], part[k])) for k in full})
        return
    out, manifest, ids = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    rows = {r["id"]: r for r in csv.DictReader(open(manifest, newline=""))}
    want = [rows[i.strip()] for i in open(ids) if i.strip() in rows]
    with ThreadPoolExecutor(int(sys.argv[4]) if len(sys.argv) > 4 else 16) as pool:
        for msg in pool.map(one, [(out, r) for r in want]):
            if not msg.startswith("have"):
                print(msg, flush=True)


if __name__ == "__main__":
    main()
