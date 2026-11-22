"""C (wasm) vs PyTorch parity for warp + teacher forward on validation samples.

  vio_env/Scripts/python parity.py --ckpt runs/t1/best.pt --weights out/dt_weights.h
Needs the eval venv's wasmtime CLI-free python API: run with vio_env (wasmtime installed there by this script's caller).
"""
import argparse, json, subprocess, tempfile
from pathlib import Path
import numpy as np
import torch

from model import Teacher, arch_of
from train import fixed_val, scene_val, prepare

HERE = Path(__file__).resolve().parent
WASI = Path("C:/Users/alexa/vio_tools/wasi-sdk-34.0-x86_64-windows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True); ap.add_argument("--weights", required=True); ap.add_argument("--n", type=int, default=24)
    a = ap.parse_args()
    data = Path("C:/Users/alexa/vio_data"); recs = json.load(open(data / "work/train_records.json"))
    va = [r for r in recs if scene_val(r["scene"])]
    ims, Hs, aux, tgt = fixed_val(data / "work/cache", va, n=a.n, seed=3)
    sd = torch.load(a.ckpt, map_location="cpu")["model"]; m = arch_of(sd); m.load_state_dict(sd); m.eval()
    with torch.no_grad():
        img, mask, aux2, _ = prepare(ims, Hs, aux, tgt, "cpu", False)
        ref = m(img, mask, aux2).numpy()
    tmp = Path(tempfile.mkdtemp())
    wasm = tmp / "parity.wasm"
    w = Path(a.weights).resolve()
    subprocess.run([str(WASI / "bin/clang.exe"), "--target=wasm32-wasip1", f"--sysroot={WASI / 'share/wasi-sysroot'}", "-O3", "-msimd128",
                    f"-I{w.parent}", f"-I{HERE}", str(HERE / "parity_main.c"), "-lm", "-o", str(wasm)], check=True)
    with open(tmp / "in.bin", "wb") as f:
        for i in range(len(ims)):
            f.write(ims[i].numpy().astype(np.uint8).tobytes()); f.write(Hs[i].numpy().astype(np.float64).tobytes()); f.write(aux[i].numpy().astype(np.float32).tobytes())
    import wasmtime
    eng = wasmtime.Engine(); store = wasmtime.Store(eng); cfg = wasmtime.WasiConfig(); cfg.preopen_dir(str(tmp), "."); store.set_wasi(cfg)
    linker = wasmtime.Linker(eng); linker.define_wasi()
    inst = linker.instantiate(store, wasmtime.Module.from_file(eng, str(wasm)))
    try:
        inst.exports(store)["_start"](store)
    except wasmtime.ExitTrap as e:
        assert e.code == 0, e.code
    raw = np.fromfile(tmp / "out.bin", np.float32).reshape(len(ims), -1)
    out = raw[:, :12]; warped = raw[:, 12:].reshape(len(ims), 2, 2, 96, 128)
    wimg = img[:, 1:].numpy(); wmask = mask[:, 1:].numpy()
    print("warp img max |d|", np.abs(warped[:, :, 0] - wimg).max(), "mask mismatches", int((warped[:, :, 1] != wmask).sum()))
    print("output max |d|", np.abs(out - ref).max(), "mean disp |d|", np.abs(out[:, :3] - ref[:, :3]).mean(), "ref |mu| mean", np.abs(ref[:, :3]).mean())


if __name__ == "__main__":
    main()
