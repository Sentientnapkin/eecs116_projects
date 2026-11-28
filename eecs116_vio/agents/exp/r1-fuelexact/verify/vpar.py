"""vpar.py OUTDIR MODE ZIP... : run base and candidate wasm on each episode via the viobench Sandbox, save raw float64
states (N,13) and per-frame fuel. MODE: plain | black (frames 300-339 zeroed) | blank (frames 300-339 = 255) | dark (every frame /16 from 200-400, frame 600 black)."""
import os, sys, numpy as np
from viobench import abi
from viobench.tools.runner.engine import Engine
from viobench.tools.runner.sandbox import Limits, Sandbox, SandboxError, SandboxTrap
from viobench.tools.datasets.sources import episodes
from viobench.tools.runner.metrics import evaluate_trajectory

BASE = "/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/baseline/gslv_s3_snace6e1.wasm"
CAND = "/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/exp/r1-fuelexact/r1-fuelexact.wasm"
out, mode = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
engine, limits = Engine(), Limits()

def xform(i, frame):
    if mode == "plain": return frame
    f = np.array(frame, copy=True)
    if mode == "black" and 300 <= i < 340: f[...] = 0
    elif mode == "blank" and 300 <= i < 340: f[...] = 255
    elif mode == "dark":
        if 200 <= i < 400: f = (f // 16).astype(frame.dtype)
        if i == 600: f[...] = 0
    return f

def run(w, path, logdir):
    ep = next(iter(episodes([path])))
    est = np.full((ep.num_frames, abi.STATE_VALUES), np.nan); fuel = np.zeros(ep.num_frames); fail = ""
    try:
        sb = Sandbox(w, engine, limits=limits, log_dir=logdir)
        config, frames = ep.adapt(sb.resolution); sb.init(config)
        for i, (t, frame, imu) in enumerate(ep.steps(frames)):
            try:
                r = sb.step(t, xform(i, frame), imu)
            except SandboxError as e:
                fuel[i] = e.fuel; raise
            fuel[i] = r.fuel; est[i] = np.concatenate([r.pose, r.twist])
    except SandboxTrap as e: fail = f"trap {e.trap_code}"
    except SandboxError as e: fail = str(e).splitlines()[0]
    ate = evaluate_trajectory(ep.ground_truth_state(), est, ep.frame_times).as_dict()["ate_rmse"]
    return est, fuel, fail, ate

for p in sys.argv[3:]:
    n = os.path.basename(p)[:-4]
    eb, fb, xb, ab = run(BASE, p, f"/tmp/vpar_{os.getpid()}_b")
    ec, fc, xc, ac = run(CAND, p, f"/tmp/vpar_{os.getpid()}_c")
    np.savez(os.path.join(out, n + ".npz"), eb=eb, ec=ec, fb=fb, fc=fc, xb=xb, xc=xc, ab=ab, ac=ac)
    same = eb.shape == ec.shape and np.array_equal(eb.view(np.uint64), ec.view(np.uint64))
    print(n, "IDENTICAL" if same else "DIFFERENT", f"ate {ab:.4f} {ac:.4f} fmax {fb.max():.0f} {fc.max():.0f} fail[{xb}][{xc}]", flush=True)
