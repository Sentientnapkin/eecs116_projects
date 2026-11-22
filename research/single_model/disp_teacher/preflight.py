"""Reduced preflight for a disp_teacher wasm (the lab's full preflight needs the lab box).

  vio_eval/Scripts/python preflight.py --wasm out/X/solution.wasm --n 3
1 viobench check; 2 imports must be empty; 3 determinism: two independent evaluations of n flights give
byte-identical estimate.tum. NOT covered (lab preflight): causality/prefix-poison and reset/re-init replay; the
teacher state is reset by dt_reset() on the same re-initialisation path B16 uses (step() with initialized == 0).
"""
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path
import numpy as np
import wasmtime

VIOBENCH = "C:/Users/alexa/vio_eval/Scripts/viobench.exe"
DATA = Path("C:/Users/alexa/vio_data")


def run_eval(wasm, zips, work):
    work.mkdir(parents=True, exist_ok=True)
    out = []
    for z in zips:
        subprocess.run([VIOBENCH, "evaluate", str(wasm), str(z)], cwd=work, capture_output=True)
        t = sorted(work.glob(f"report-*/logs/*/estimate.tum"), key=lambda p: p.stat().st_mtime)[-1]
        out.append(hashlib.sha256(t.read_bytes()).hexdigest())
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--wasm", required=True); ap.add_argument("--n", type=int, default=3)
    a = ap.parse_args()
    wasm = Path(a.wasm).resolve(); res = {}
    p = subprocess.run([VIOBENCH, "check", str(wasm)], capture_output=True, text=True)
    res["check"] = "check: ok" in p.stdout + p.stderr
    eng = wasmtime.Engine(); mod = wasmtime.Module.from_file(eng, str(wasm))
    res["imports"] = [f"{i.module}.{i.name}" for i in mod.imports]
    eps = json.load(open(DATA / "server-calibrated/manifest.json"))["episodes"]
    fold = lambda e: int(hashlib.sha256((e["catalog"] + ":" + e["scene"]).encode()).hexdigest()[:8], 16) % 5
    sel = [e for e in eps if fold(e) in (2, 3)]
    zips = [DATA / "server-calibrated" / e["file"] for e in (sel[:1] + [e for e in sel if e.get("start_offset_s", 0) > 0][:a.n - 1])]
    tmp = Path(tempfile.mkdtemp())
    h1 = run_eval(wasm, zips, tmp / "a"); h2 = run_eval(wasm, zips, tmp / "b")
    res["determinism"] = h1 == h2
    res["sha256"] = hashlib.sha256(wasm.read_bytes()).hexdigest()
    res["bytes"] = wasm.stat().st_size
    print(json.dumps(res, indent=1))
    Path(wasm.parent / "preflight.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
