"""Fetch SentientNapkin/viobench-tuning-sets WITHOUT the images: HTTP range requests read each zip's central directory
and copy only the non-image members (episode.json, cam0/data.csv + sensor.yaml, imu0, groundtruth, ~2.4 MB of ~250 MB)
into a mini zip that read_episode(frames="none") / cache_imu.py can open. Also saves the json sidecar.

  python tune_fetch.py OUT_DIR [FOLDER ...]     (default: all folders) -> OUT_DIR/<folder>/<name>.zip + .json
"""
import io, json, os, re, sys, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor

REPO = "https://huggingface.co/datasets/SentientNapkin/viobench-tuning-sets"
H = {"User-Agent": "py"}


def tree(p):
    out = []; url = f"https://huggingface.co/api/datasets/SentientNapkin/viobench-tuning-sets/tree/main/{p}?limit=1000"
    while url:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=H)); out += json.load(r)
        m = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get("Link", "") or ""); url = m.group(1) if m else None
    return out


class HttpFile(io.RawIOBase):
    """Seekable read-only view of a URL via Range requests (enough for zipfile)."""
    def __init__(self, url, size):
        r = urllib.request.urlopen(urllib.request.Request(url, headers=H | {"Range": "bytes=0-0"}))
        self.url = r.geturl(); self.size = size; self.pos = 0; r.read()
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off; return self.pos
    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0: return 0
        for attempt in range(5):
            try:
                r = urllib.request.urlopen(urllib.request.Request(self.url, headers=H | {"Range": f"bytes={self.pos}-{self.pos + n - 1}"}), timeout=60)
                data = r.read(); break
            except Exception:
                if attempt == 4: raise
        b[:len(data)] = data; self.pos += len(data); return len(data)


def one(job):
    folder, f, out = job
    name = os.path.basename(f["path"])[:-4]; dst = f"{out}/{folder}/{name}.zip"
    if os.path.exists(dst): return name, "skip"
    try:
        hf = io.BufferedReader(HttpFile(f"{REPO}/resolve/main/{f['path']}", f["size"]), buffer_size=1 << 20)
        z = zipfile.ZipFile(hf)
        with zipfile.ZipFile(dst + ".tmp", "w", zipfile.ZIP_DEFLATED) as w:
            for i in z.infolist():
                if "/cam0/data/" in i.filename: continue
                w.writestr(i.filename, z.read(i.filename))
        os.replace(dst + ".tmp", dst)
        js = urllib.request.urlopen(urllib.request.Request(f"{REPO}/resolve/main/{f['path'][:-4]}.json", headers=H)).read()
        open(f"{out}/{folder}/{name}.json", "wb").write(js)
        return name, "ok"
    except Exception as e:
        return name, f"ERR {type(e).__name__}: {e}"


def main():
    out = os.path.expanduser(sys.argv[1])
    folders = sys.argv[2:] or [d["path"] for d in tree("") if d["type"] == "directory"]
    jobs = []
    for folder in folders:
        os.makedirs(f"{out}/{folder}", exist_ok=True)
        jobs += [(folder, f, out) for f in tree(folder) if f["path"].endswith(".zip")]
    print(f"{len(jobs)} zips in {folders}", flush=True)
    ok = err = 0
    with ThreadPoolExecutor(int(os.environ.get("J", 16))) as ex:
        for n, s in ex.map(one, jobs):
            ok += s == "ok"; err += s.startswith("ERR")
            if s.startswith("ERR"): print(n, s, flush=True)
    print(f"done ok {ok} err {err}", flush=True)


if __name__ == "__main__":
    main()
