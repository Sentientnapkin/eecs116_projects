"""Download viobench-stage3 flights by id into ~/data/s3match/, sha256-checked against manifest.csv.

    python3 fetch.py MANIFEST.csv IDS_FILE [JOBS]
"""
import csv
import hashlib
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

URL = "https://huggingface.co/datasets/SentientNapkin/viobench-stage3/resolve/main/"
OUT = os.path.expanduser("~/data/s3match")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(row):
    final = os.path.join(OUT, row["id"] + ".zip")
    if os.path.exists(final + ".ok"):
        return "have " + row["id"]
    part = final + ".part"
    for _ in range(3):
        r = subprocess.run(["curl", "-sSL", "--retry", "8", "--retry-all-errors", "-o", part, URL + row["path"]])
        if r.returncode == 0 and sha256(part) == row["sha256"]:
            os.replace(part, final)
            open(final + ".ok", "w").close()
            return "ok " + row["id"]
    return "FAILED " + row["id"]


def main():
    rows = {r["id"]: r for r in csv.DictReader(open(sys.argv[1], newline=""))}
    ids = [x.strip() for x in open(sys.argv[2]) if x.strip()]
    os.makedirs(OUT, exist_ok=True)
    missing = [i for i in ids if i not in rows]
    if missing:
        print("not in manifest:", missing)
    with ThreadPoolExecutor(int(sys.argv[3]) if len(sys.argv) > 3 else 4) as pool:
        for msg in pool.map(fetch, [rows[i] for i in ids if i in rows]):
            print(msg, flush=True)


if __name__ == "__main__":
    main()
