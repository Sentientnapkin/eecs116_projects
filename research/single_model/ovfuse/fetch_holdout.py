"""Download the one-shot holdout set (HF dataset SentientNapkin/viobench-holdout-240) into vio_data/holdout240.

  python -I fetch_holdout.py [--out C:/Users/alexa/vio_data/holdout240] [--workers 4]
Lists the repo tree page by page (Link headers), then fetches every file not yet present with the right size
(resumable: partial files are written as .part and renamed when complete). Files are data only; nothing is executed.
"""
import argparse, json, re, time, urllib.request, concurrent.futures as cf
from pathlib import Path

REPO = "SentientNapkin/viobench-holdout-240"
API = f"https://huggingface.co/api/datasets/{REPO}/tree/main"
RAW = f"https://huggingface.co/datasets/{REPO}/resolve/main/"
UA = {"User-Agent": "dataset-fetch/1.0"}


def opener(url, headers=None, tries=6):
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=120)
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))


def listing():
    out, url = [], API + "?recursive=true&limit=1000"
    while url:
        with opener(url) as r:
            out += [x for x in json.load(r) if x["type"] == "file"]
            m = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get("Link") or "")
            url = m.group(1) if m else None
    return out


def fetch(item, root):
    dst = root / item["path"]
    if dst.exists() and dst.stat().st_size == item["size"]:
        return item["path"], "have"
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    with opener(RAW + item["path"], {"Range": f"bytes={have}-"} if have else None) as r, open(part, "ab" if have and r.status == 206 else "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    if part.stat().st_size != item["size"]:
        return item["path"], f"SIZE MISMATCH {part.stat().st_size} != {item['size']}"
    part.replace(dst)
    return item["path"], "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="C:/Users/alexa/vio_data/holdout240"); ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    root = Path(a.out); root.mkdir(parents=True, exist_ok=True)
    items = listing()
    (root / "_listing.json").write_text(json.dumps(items, indent=0))
    zips = [x for x in items if x["path"].endswith(".zip")]
    print(f"{len(items)} files, {len(zips)} zips, {sum(x['size'] for x in items) / 1e9:.1f} GB", flush=True)
    items.sort(key=lambda x: (x["path"].endswith(".zip"), x["path"]))  # small files first
    n = 0
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for fut in cf.as_completed([ex.submit(fetch, x, root) for x in items]):
            try:
                p, s = fut.result()
            except Exception as e:  # keep going; a rerun resumes
                p, s = "?", f"ERROR {e!r}"
            n += 1
            if s != "have":
                print(f"[{n}/{len(items)}] {s} {p}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
