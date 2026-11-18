"""Matched error-budget diagnostics and actual benchmark guest measurements."""
import argparse
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from shutil import copy2

import cv2
import numpy as np
import torch

from common import Flight, ate, integrate_body_velocity
from learned_probe import digest, network, open_run, pose, predictions, read_inputs, score, write
from seq_heads import winner
from streaming import Estimator, Predictor
from streaming import CHANNELS

ROOT = Path(__file__).resolve().parents[4]
BENCH = ROOT/"Final Project"/"viobench"
CLASSICAL = ROOT/"Final Project"/"classical_vio"


def scale_fit(translation, target, lever=None):
    lever = np.zeros_like(translation) if lever is None else lever
    denom = np.sum(translation**2)
    scale = max(1e-8, float(np.sum(translation*(target-lever))/denom)) if denom > 0 else 1.
    return scale, ate(scale*translation+lever, target)


def moving_mean(values, times, width, centered=False):
    start = np.searchsorted(times, times-width/2 if centered else times-width)
    end = np.searchsorted(times, times+width/2, side="right") if centered else np.arange(1, len(times)+1)
    total = np.concatenate((np.zeros_like(values[:1]), values.cumsum(axis=0)))
    return (total[end]-total[start]) / (end-start)[:,None]


def error_budget(row, v):
    est = pose(row, v, row["R"])
    lever = pose(row, np.zeros_like(v), row["R"])
    target = row["cam_gt"]
    whole = scale_fit(est, target)
    translation = scale_fit(est-lever, target, lever)
    vel_world = (row["R"] @ v[...,None]).squeeze(-1)
    speed = np.linalg.norm(v, axis=1)
    real = np.linalg.norm(row["v"], axis=1)
    mask = (speed>.05) & (real>.05)
    def smooth(centered):
        vw = moving_mean(vel_world, row["times"], 1., centered)
        return ate(pose(row, (row["R"].transpose(0,2,1) @ vw[...,None]).squeeze(-1), row["R"]), target)
    return {"path": row["path"], "ate": ate(est, target), "whole_scale": whole[0], "whole_scale_ate": whole[1],
            "translation_scale": translation[0], "translation_scale_ate": translation[1],
            "speed_sum_matched_ate": ate(pose(row, v*real.sum()/max(speed.sum(),1e-8), row["R"]), target),
            "causal_smooth_ate": smooth(False), "centered_noncausal_ate": smooth(True),
            "direction_frames": int(mask.sum()),
            "direction_cosine": float(np.mean(np.sum(v[mask]*row["v"][mask],axis=1)/(speed[mask]*real[mask]))) if mask.any() else None}


def audit_proxy(f):
    return {"path": str(f.path), "tier": f.tier, "scene": f.scene, "seed": f.seed,
            "resolution": list(f.frames.shape[1:]), "intrinsics": f.K, "T_body_camera": f.T_bc.tolist(),
            "frame_count": f.F, "duration_s": float(f.ft[-1]), "first_packet_samples": len(f.win[0]),
            "median_imu_dt_s": float(np.median(np.diff(f.imu[:,0]))), "initial_speed": float(np.linalg.norm(f.v[0])),
            "speed_p50_p95": np.percentile(np.linalg.norm(f.v,axis=1),[50,95]).tolist(),
            "angular_rate_p50_p95": np.percentile(np.linalg.norm(f.w,axis=1),[50,95]).tolist(),
            "path_m": float(np.linalg.norm(np.diff(f.p,axis=0),axis=1).sum()),
            "extent_xyz_m": np.ptp(f.p,axis=0).tolist(),
            "stationary_fraction": float(np.mean(np.linalg.norm(f.v,axis=1) < .15))}


def payload(visual, temporal=None):
    if digest(visual["checkpoint"]) != visual["sha256"]:
        raise ValueError("visual checkpoint hash changed")
    net = network(visual["checkpoint"])
    base = {k:v.detach().numpy() for k,v in net.state_dict().items()}
    if temporal and digest(temporal["checkpoint"]) != temporal["sha256"]:
        raise ValueError("temporal checkpoint hash changed")
    head = torch.load(temporal["checkpoint"], map_location="cpu", weights_only=True) if temporal else None
    return {"variant":net.variant, "encoder":base, "kind":head["kind"] if head else None,
            "temporal":{k:v.detach().numpy() for k,v in head["state"].items()} if head else {}}


def native_host(ep, model, cfg):
    from viobench.tools.runner.metrics import evaluate_trajectory
    cam, frames = ep.adapt((320,240))
    estimator = Estimator(cam, model, cfg)
    states = np.stack([estimator.step(t, frame, imu) for t, frame, imu in ep.steps(frames)])
    gt = ep.ground_truth_state()
    metrics = evaluate_trajectory(gt, states, ep.frame_times).as_dict()
    probe = estimator.inputs.rotation_probe
    if probe:
        metrics.update(rotation_windows=probe.windows, rotation_accepted=probe.accepted)
    return metrics, states


def bundle_model(folder, model, cfg, runtime, diagnostic=False, gap_adapter=False):
    from viobench.solution.runtime.python.bundler.bundle import bundle
    folder.mkdir()
    for name in ("orientation.py", "streaming.py"):
        copy2(name, folder/name)
    np.savez(folder/"weights.npz", **{"enc/"+k:v for k,v in model["encoder"].items()},
             **{"head/"+k:v for k,v in model["temporal"].items()},
             **({"rotation":model["rotation_weights"]} if model.get("rotation_weights") is not None else {}))
    (folder/"config.json").write_text(json.dumps({"config":cfg, "variant":model["variant"],"kind":model["kind"],"rotation_method":model.get("rotation_method"),"settings":model.get("settings")}))
    (folder/"solution.py").write_text("""import io
import json
import numpy as np
import solution_bundle
from streaming import Estimator

class Solution(Estimator):
    def __init__(self, camera):
        settings = json.loads(solution_bundle.read_bytes("config.json"))
        with np.load(io.BytesIO(solution_bundle.read_bytes("weights.npz")), allow_pickle=False) as archive:
            weights = dict(archive)
        model = {"variant": settings["variant"], "kind": settings["kind"],
                 "settings":settings.get("settings"), "rotation_method": settings.get("rotation_method"), "rotation_weights": weights.get("rotation"),
                 "encoder": {k[4:]:v for k,v in weights.items() if k.startswith("enc/")},
                 "temporal": {k[5:]:v for k,v in weights.items() if k.startswith("head/")}}
        super().__init__(camera, model, settings["config"])
""")
    if diagnostic:
        solution = folder/"solution.py"
        with solution.open("a") as stream:
            stream.write("""
    def step(self, t, frame, packet):
        import base64
        index = getattr(self, "index", 0)
        self.index = index + 1
        self.trace = {} if index < 24 or index % 20 == 0 else None
        self.inputs.trace = self.model.trace = None
        result = super().step(t, frame, packet)
        if self.trace is not None:
            self.trace["output"] = result
            def encode(value):
                array = np.ascontiguousarray(value)
                return [array.dtype.str, array.shape,
                        base64.b64encode(array.tobytes()).decode("ascii")]
            fields = {k: encode(v) if isinstance(v, np.ndarray) else v
                      for k, v in self.trace.items()}
            print("TRACE " + json.dumps([index, fields], default=lambda scalar: scalar.item()), flush=True)
        return result
""")
    if gap_adapter:
        solution = folder/"solution.py"
        with solution.open("a") as stream:
            stream.write("""
    def step(self, t, frame, packet):
        if self.development_gap_adapter:
            self.index += 1
            if self.index and self.index % 137 in (0, 1, 2):
                frame = None
        return super().step(t, frame, packet)
""")
        solution.write_text(solution.read_text().replace(
            '        super().__init__(camera, model, settings["config"])',
            '        self.development_gap_adapter = camera.get("development_gap_adapter", False)\n'
            '        self.index = -1\n'
            '        super().__init__(camera, model, settings["config"])'))
    module = folder.with_suffix(".wasm")
    bundle(folder, module, runtime=runtime)
    return module


def audit_native(ep, identity):
    state = ep.ground_truth_state()
    _, frames = ep.adapt((320,240))
    return {**identity, "frame_count": ep.num_frames, "duration_s": float(ep.duration),
            "delivery_resolution": [320,240], "source_resolution": list(ep.resolution),
            "T_body_camera": ep.T_body_camera.tolist(), "intrinsics": ep.config.get("camera"),
            "first_packet_samples": len(ep.imu_window(0)), "median_imu_dt_s": float(np.median(np.diff(ep.imu[:,0]))),
            "initial_speed": float(np.linalg.norm(state[0,7:10])),
            "speed_p50_p95": np.percentile(np.linalg.norm(state[:,7:10],axis=1),[50,95]).tolist(),
            "angular_rate_p50_p95": np.percentile(np.linalg.norm(state[:,10:13],axis=1),[50,95]).tolist(),
            "path_m": float(np.linalg.norm(np.diff(state[:,:3],axis=0),axis=1).sum()),
            "extent_xyz_m": np.ptp(state[:,:3],axis=0).tolist(),
            "stationary_fraction": float(np.mean(np.linalg.norm(state[:,7:10],axis=1) < .15)),
            "first_frame_valid": bool(np.isfinite(frames[0]).all())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("visual_run",type=Path)
    parser.add_argument("temporal_run",type=Path,nargs="?")
    parser.add_argument("--native", type=Path, action="append")
    parser.add_argument("--rotation-run",type=Path)
    parser.add_argument("--calibration", choices=("none","startup","evidence"))
    parser.add_argument("--skip-transfer", action="store_true")
    parser.add_argument("--student-only", action="store_true")
    parser.add_argument("--diagnostics-only",action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--pareto", type=Path, help="user-supplied scoreboard image for context")
    for name in ("diagnostic", "deployment", "smoke", "selective", "startup-rotation", "native-startup", "student", "student-guest"):
        parser.add_argument(f"--{name}-run", type=Path)
    args = parser.parse_args()
    if args.report:
        final_report(args)
        return
    torch.set_num_threads(4)
    prior = json.loads((args.visual_run/"manifest.json").read_text())
    cfg, groups = prior["config"], prior["datasets"]
    if args.calibration:
        cfg = {**cfg, "policy": args.calibration}
    visual = json.loads((args.visual_run/"scores.json").read_text())
    chosen = winner(visual)
    selected = min((r for r in visual if r["variant"] == chosen),
                   key=lambda r: np.mean([x["ate"] for x in r["rows"]]))
    out,m = open_run("diagnostics" if args.diagnostics_only else "deployment",cfg,groups)
    m["visual_run"] = str(args.visual_run)
    m["visual_manifest_hash"] = digest(args.visual_run/"manifest.json")
    print(out,flush=True)
    try:
        if args.diagnostics_only:
            net = network(selected["checkpoint"])
            rows,motion = [],[]
            for crop in (0.,5.):
                base = read_inputs(groups["development"], cfg,crop)
                v = {r["path"]:predictions(net,r) for r in base}
                for policy in ("none","startup","evidence"):
                    observations = base if policy==cfg["policy"] else read_inputs(
                        groups["development"],{**cfg,"policy":policy},crop)
                    for row in observations:
                        # Rebuild visual features under each policy. Also isolate attitude with fixed velocities.
                        rebuilt = predictions(net,row)
                        rows.append({**score(row,rebuilt),"policy":policy,
                                     "fixed_velocity_ate":score(row,v[row["path"]])["ate"]})
                        if policy==cfg["policy"]:
                            motion.append({"crop_s":crop,**error_budget(row,rebuilt)})
            tier_scores = []
            from learned_probe import split_paths
            roster = []
            for tier in ("base","mid","agile"):
                group = split_paths(cfg,tier)["development"]
                roster.extend(group)
                for row in read_inputs(group,cfg):
                    v = predictions(net,row)
                    tier_scores.append(score(row,v))
                    if len(v) > 601:
                        clipped = {k: val[:601] if isinstance(val,np.ndarray) and val.ndim and len(val)==len(v)
                                   else val for k,val in row.items()}
                        tier_scores.append({**score(clipped,v[:601]),"prefix_seconds":30.})
            write(out/"policy.json",rows)
            write(out/"error_budget.json",motion)
            write(out/"tiers.json",tier_scores)
            write(out/"proxy_audit.json",[audit_proxy(Flight(x["path"])) for x in [*groups["train"], *roster]])
        else:
            from viobench.tools.datasets.storage import read_episode
            from viobench.tools.runner.engine import Engine, WASMTIME_VERSION
            from viobench.tools.runner.run import run_episode
            from viobench.tools.runner.sandbox import Limits
            if args.temporal_run is None or not args.native:
                raise ValueError("deployment needs completed temporal run and native inputs")
            tm = json.loads((args.temporal_run/"manifest.json").read_text())
            if tm["status"]!="completed":
                raise ValueError("temporal run is incomplete")
            seq = json.loads((args.temporal_run/"scores.json").read_text())
            finalist = min((r for r in seq if r["variant"] in ("ssm","gru","ema")),
                           key=lambda r:np.mean([x["ate"] for x in r["rows"]]))
            ref = next(r for r in visual if r["checkpoint"]==finalist["encoder"])
            benchmark = [{"path":str(p),"sha256":digest(p)} for p in args.native]
            runtime = CLASSICAL/"build"/"runtime.wasm"
            limits = Limits()
            revision = subprocess.check_output(["git","-C",str(BENCH),"rev-parse","HEAD"],text=True).strip()
            m.update(benchmark=benchmark, runtime_sha256=digest(runtime), wasmtime=WASMTIME_VERSION,
                     limits=asdict(limits), benchmark_revision=revision, temporal_run=str(args.temporal_run),
                     temporal_manifest_hash=digest(args.temporal_run/"manifest.json"),
                     server_rules={"checked_utc":datetime.now(timezone.utc).isoformat(),
                                   "status":"externally unverified; no server endpoint configured"})
            episodes = [(read_episode(row["path"]),row) for row in benchmark]
            write(out/"native_audit.json",[audit_native(ep,row) for ep,row in episodes])
            rows,guest,export = [],[],[]
            sample = read_inputs(groups["development"][:1],cfg)[0]
            for r in ([] if args.skip_transfer else visual):
                model = payload(r)
                net = network(r["checkpoint"])
                impl = Predictor(model["variant"],model["encoder"])
                expected = predictions(net,sample)
                result = np.stack([impl.step(a[CHANNELS[model["variant"]]],b)
                                   for a,b in zip(sample["images"][:128],sample["imu"][:128])])
                error = float(np.max(np.abs(expected[:128]-result)))
                if error > 1e-5:
                    raise ValueError(f"CNN export parity {error}")
                export.append({"variant":r["variant"],"seed":r["seed"],"cnn_max_error":error})
                for ep,info in episodes:
                    metrics,_ = native_host(ep,model,cfg)
                    rows.append({"variant":r["variant"],"seed":r["seed"],"episode":info["sha256"],**metrics})
            write(out/"transfer.json",rows)
            write(out/"export_parity.json",export)
            m["modules"]={}
            engine = Engine()
            candidates = [("cnn",selected,None,None),("temporal",ref,finalist,None)]
            if args.rotation_run:
                weights = args.rotation_run/"ridge.npy"
                rotation_manifest = json.loads((args.rotation_run/"manifest.json").read_text())
                if rotation_manifest["status"] != "completed" or digest(weights) != rotation_manifest["rotation_model_sha256"]:
                    raise ValueError("rotation run is incomplete or its weights changed")
                m.update(rotation_run=str(args.rotation_run), rotation_weights_sha256=digest(weights))
                candidates += [(method,selected,None,method) for method in ("geometry","learned")]
            if args.student_only:
                if not args.student_run:
                    raise ValueError("--student-only needs --student-run")
                student = json.loads((args.student_run/"manifest.json").read_text())
                if student["status"]!="completed":
                    raise ValueError("student training is incomplete")
                m.update(student_run=str(args.student_run), student_manifest_sha256=digest(args.student_run/"manifest.json"))
                candidates = [(row["student"],row,None,None) for row in
                              json.loads((args.student_run/"scores.json").read_text())]
            for name,source,head,rotation in candidates:
                model = payload(source,head)
                if rotation:
                    model.update(rotation_method=rotation,
                                 rotation_weights=np.load(weights) if rotation=="learned" else None)
                wasm = bundle_model(out/name,model,cfg,runtime)
                m["modules"][name]={"sha256":digest(wasm),"checkpoint_sha256":source["sha256"],
                                    "variant":source["variant"],"head":head["variant"] if head else None,
                                    "head_sha256":head["sha256"] if head else None}
                for ep,info in episodes:
                    report, states, fuel = run_episode(wasm,ep,engine,limits,out/f"{name}-{ep.hash[:8]}")
                    host_metrics, host_states = native_host(ep,model,cfg)
                    guest.append({"model":name,"episode":info["sha256"],**report.as_dict(), 
                                  "host_ate":host_metrics["ate_rmse"],
                                  "host_rotation_windows":host_metrics.get("rotation_windows"),
                                  "host_rotation_accepted":host_metrics.get("rotation_accepted"),
                                  "host_guest_position_maximum":float(np.max(np.abs(host_states[:len(fuel),:3]-states[:len(fuel),:3])))
                                  if report.completed else None,
                                  "startup_peak":int(np.max(fuel[:21], initial=0))})
                    np.savez(out/f"{name}-{ep.hash[:8]}.npz",states=states, fuel=fuel)
                    write(out/"guest.json",guest)
                    print(name,ep.hash,report.completed,report.failure,report.metrics["ate_rmse"],report.fuel_per_frame_max,flush=True)
        m["status"]="completed"
    except BaseException as e:
        m.update(status="failed",error=repr(e))
        raise
    finally:
        write(out/"manifest.json",m)


def final_report(args):
    names = ("visual","temporal","smoke","selective","rotation","startup_rotation","diagnostic","deployment","native_startup","student","student_guest")
    folders = {name:getattr(args,f"{name}_run") for name in names}
    if any(path is None for path in folders.values()):
        raise ValueError("report requires all eleven constituent run directories")

    def load(name, file):
        return json.loads((folders[name]/file).read_text())

    manifests = {name:load(name,"manifest.json") for name in names}
    if any(m["status"]!="completed" for m in manifests.values()):
        raise ValueError("report requires completed constituent runs")
    directory, manifest = open_run("stage2",manifests["visual"]["config"],manifests["visual"]["datasets"])
    manifest["constituents"] = {k:{"path":str(p),"manifest_sha256":digest(p/"manifest.json")} for k,p in folders.items()}
    if args.pareto:
        copy2(args.pareto, directory/"supplied-pareto.png")
        manifest["pareto_snapshot"] = {"sha256":digest(directory/"supplied-pareto.png"), "source":"user attachment",
                                       "coordinate_precision":"visual approximation"}

    def average(rows, field):
        values = [r[field] for r in rows if r.get(field) is not None]
        return float(np.mean(values)) if values else float("nan")

    lines = ["# Stage-2 VIO evaluation","",
             "All primary position errors are unaligned ATE in the first-camera frame. Current local runner rules were "
             f"checked at commit `{manifests['deployment']['benchmark_revision'][:8]}`. "
             "The live server rule is externally unverified because no endpoint is configured.","",
             "## Constituent runs",""]
    for name,p in folders.items():
        lines.append(f"- [{name.replace('_',' ')}](../{p.name}/manifest.json)")
    def link(run,file,label):
        return f"[{label}](../{folders[run].name}/{file})"
    cfg = manifest["config"]
    roster = manifest["datasets"]
    lines += ["","## Evaluation contract","",
              f"The primary comparison uses {len(roster['train'])} training parents and "
              f"{len(roster['development'])} development parents across disjoint scenes. The base-tier budget is "
              "one parent per scene. Development scenes have influenced model choices. No independent proxy scene set was opened.",
              "",
              "Causal replay emits all frames, including startup. The identity attitude gauge cancels under first-camera "
              "coordinates. Bias activation occurs after the observed window and leaves emitted poses intact. Moving "
              "starts rebuild from raw data with a fresh orientation, image history and temporal state.","",
              "All architecture comparisons use body-frame endpoint velocity and the same displacement supervision. "
              "The displacement term rotates into a common frame with supervised truth attitude and integrates over "
              "0.25, 1 and 3 seconds using timestamped trapezoids. Estimated-attitude replay is the selection path. "
              "The test suite covers prefix invariance, coordinate gauge, irregular sampling, acceleration, turns, "
              "lever arm, tiny motion, scale and streaming parity.","",
              "Historical ATE values from the future-calibrated caches, averaged targets and prior sequence losses "
              "belong to their original experiments. The corrected runs support short visual context and a modest benefit "
              "from temporal filtering. Long-baseline gains, learned-memory gains and gyro improvements are evaluated below.","",
              "## Visual context","",
              "| Input | Seed | Est. attitude ATE m | Truth attitude ATE m | Sim(3) m | Startup ATE m | Parameters |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    visual = load("visual","scores.json")
    for record in visual:
        rows=record["rows"]
        lines.append(f"| {record['variant']} | {record['seed']} | {average(rows,'ate'):.3f} | "
                     f"{average(rows,'truth_attitude_ate'):.3f} | {average(rows,'sim3'):.3f} | "
                     f"{average(rows,'startup_ate'):.3f} | {record['parameters']} |")
    lines += ["",link("visual","scores.json","Per-flight startup, velocity, orientation, scale, motion and overlap scores"),
              "", "Models with derotation use gyro in preprocessing. The CNN variants with an explicit IMU branch "
              "also include current packet statistics and timing.","",
              "## Frozen-encoder heads","",
              "| Head | Seed | Est. attitude ATE m | Truth attitude ATE m | Moving start ATE m | Parameters | Streaming max error |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    heads = load("temporal","scores.json")+load("selective","scores.json")
    for record in heads:
        r=record["rows"]
        lines.append(f"| {record['variant']} | {record['seed']} | {average(r,'ate'):.3f} | "
                     f"{average(r,'truth_attitude_ate'):.3f} | {average(record['moving_start'],'ate'):.3f} | "
                     f"{record['parameters']} | {record['stream_max_error']:.2g} |")
    lines += ["","Each temporal head saw the same checkpoint features, loss and training steps per seed. "
              "The visual encoder was frozen. Chunk starts use up to 60 preceding frames of burn-in. "
              "Moving-start replay rebuilds the raw crop and evaluates the entire cropped flight.","",
              "## Calibration and rotation","",
              "| Crop s | Policy | Full causal ATE m | Fixed-velocity ATE m | Orientation RMSE rad |",
              "|---:|---|---:|---:|---:|"]
    policy = load("diagnostic","policy.json")
    for crop in (0,5):
        for name in ("none","startup","evidence"):
            rows = [r for r in policy if r["crop_s"]==crop and r["policy"]==name]
            lines.append(f"| {crop} | {name} | {average(rows,'ate'):.3f} | "
                         f"{average(rows,'fixed_velocity_ate'):.3f} | {average(rows,'rotation_rmse_rad'):.3f} |")
    lines += ["","The evidence gate matched the no-calibration policy on this development sample. Unconditional "
              "startup calibration is a substantive additional control, especially on nominal starts.","",
              "| Policy | Crop s | Injection | Method | ATE m | Rotation RMSE rad | Window residual RMS rad | Accepted / windows | Added-bias error rad/s |",
              "|---|---:|---|---|---:|---:|---:|---:|---:|"]
    for run in ("rotation","startup_rotation"):
        data=load(run,"scores.json")
        policy_name=manifests[run]["config"]["policy"]
        for crop in (0,5):
            for case in ("native","constant","changing"):
                for method in ("baseline","geometry","learned"):
                    r=[s for s in data if s["crop_s"]==crop and s["case"]==case and s["method"]==method]
                    accept,all_windows=sum(s["accepted"] for s in r),sum(s["windows"] for s in r)
                    bias=average(r,"bias_difference_to_injected_rad_s")
                    lines.append(f"| {policy_name} | {crop} | {case} | {method} | {average(r,'ate'):.3f} | "
                                 f"{average(r,'rotation_rmse_rad'):.3f} | {average(r,'relative_rotation_residual_rms'):.4f} | "
                                 f"{accept}/{all_windows} | {f'{bias:.4f}' if np.isfinite(bias) else '—'} |")
    lines += ["","Proxy rotation probes hold translation predictions fixed and correct accumulated orientation "
              "using nonoverlapping windows. The paired bias column measures recovery of the controlled addition "
              "by startup calibration. Instantaneous physical bias was unobserved. Separate rotation updates "
              "leave the gyro bias state intact.","",
              "## Proxy and native transfer","",
              "The proxy generator renders 160×120 gray images with antialiasing and motion blur disabled. "
              "Native episodes originate at 640×480 and deliver 320×240 RGB before grayscale conversion and "
              "network resize. Both resize intrinsics with the pixel-center convention. Native frame zero arrives "
              "with an IMU packet which this estimator discards to match the pre-origin convention in training. "
              "The native dataset samples differ in scene, duration and rendering. They quantify transfer for these "
              "archives with scene and rendering effects still coupled.","",
              "| Proxy tier | Mean ATE full m | Mean ATE first 30 s m |",
              "|---|---:|---:|"]
    tiers=load("diagnostic","tiers.json")
    for name in ("base","mid","agile"):
        r=[s for s in tiers if s["tier"]==name]
        lines.append(f"| {name} | {average([x for x in r if 'prefix_seconds' not in x],'ate'):.3f} | "
                     f"{average([x for x in r if 'prefix_seconds' in x],'ate'):.3f} |")
    lines += ["",link("diagnostic","proxy_audit.json","Proxy resolution, calibration, duration, speed, extent and stillness")+
              " · "+link("deployment","native_audit.json","Native frame, IMU and extent audit"),
              "", "The prefix comparison changes elapsed duration and traveled extent together. Speed, angular rate "
              "and spatial extent are retained per flight; independent effects of rendering and extent remain unresolved.","",
              "| Visual input | Proxy dev ATE m | Native host ATE m |",
              "|---|---:|---:|"]
    transfer=load("deployment","transfer.json")
    variants=sorted({r["variant"] for r in visual})
    proxy_order={}
    native_order={}
    for name in variants:
        proxy_order[name]=average([v for r in visual if r["variant"]==name for v in r["rows"]],"ate")
        native_order[name]=average([r for r in transfer if r["variant"]==name],"ate_rmse")
        lines.append(f"| {name} | {proxy_order[name]:.3f} | {native_order[name]:.3f} |")
    # Audit retained raw archives and preserve the historical render log as evidence of attempts.
    import re
    provenance_log = Path("data_gen.log")
    if provenance_log.is_file():
        counts = [(int(a),int(b)) for a,b in re.findall(r": (\d+)/(\d+) ok",provenance_log.read_text())]
        copy2(provenance_log,directory/"historical-generation.log")
        manifest["generation_log_sha256"] = digest(directory/"historical-generation.log")
        if counts:
            lines += ["", f"The historical generation log records {sum(a for a,_ in counts)} accepted trials "
                      f"out of {sum(b for _,b in counts)} attempts across its generation jobs. "
                      "The generator omits terminated flights. The log covers more trials than the primary roster. "
                      "[Historical generation log](historical-generation.log)"]
    stalls = []
    for entry in load("diagnostic","proxy_audit.json"):
        flight = Flight(entry["path"])
        still = (np.linalg.norm(flight.v,axis=1)<.15) & (flight.ft>=2.)
        boundaries = np.flatnonzero(np.diff(np.r_[False, still, False].astype(int)))
        longest = max((flight.ft[b-1]-flight.ft[a] for a,b in zip(boundaries[::2],boundaries[1::2])),default=0.)
        if longest>=3.:
            stalls.append({"path":entry["path"],"longest_stationary_s":float(longest)})
    write(directory/"stall_flags.json",stalls)
    lines += ["",f"The retained audit flagged {len(stalls)} parent flights with at least three consecutive seconds "
              "below 0.15 m/s after two seconds. All flagged files were retained. [Stationary interval audit](stall_flags.json)"]
    budget=load("diagnostic","error_budget.json")
    lines += ["","## Error-budget controls","",
              f"Across nominal and moving-start replays, mean unaligned ATE was {average(budget,'ate'):.3f} m. "
              f"Positive scalar fits gave {average(budget,'whole_scale_ate'):.3f} m for whole camera trajectories and "
              f"{average(budget,'translation_scale_ate'):.3f} m when keeping the rotational lever arm fixed. "
              f"Speed-sum matching gave {average(budget,'speed_sum_matched_ate'):.3f} m. "
              f"Causal trailing smoothing gave {average(budget,'causal_smooth_ate'):.3f} m and centered "
              f"noncausal smoothing gave {average(budget,'centered_noncausal_ate'):.3f} m. "
              "Direction statistics use frames with both predicted and true speed above 0.05 m/s. "
              "Separate diagnostics share related error sources.","",
              "## Measured WebAssembly","",
              "| Module | Complete | Mean unaligned ATE m | Mean Sim(3) m | Peak fuel/frame | Startup peak |",
              "|---|---:|---:|---:|---:|---:|"]
    guest=load("deployment","guest.json")
    guest_summary={}
    for name in dict.fromkeys(r["model"] for r in guest):
        r=[s for s in guest if s["model"]==name]
        v={"ate":average([s["metrics"] for s in r],"ate_rmse"),"fuel":max(s["fuel_per_frame_max"] for s in r),
           "completed":sum(s["completed"] for s in r),"count":len(r)}
        guest_summary[name]=v
        lines.append(f"| {name} | {v['completed']}/{len(r)} | {v['ate']:.3f} | "
                     f"{average([s['metrics'] for s in r],'sim3_ate_rmse'):.3f} | {v['fuel']:,} | "
                     f"{max(s['startup_peak'] for s in r):,} |")
    startup_guest = load("native_startup","guest.json")
    startup_points = {}
    lines += ["", "Native calibration sensitivity with the fixed startup policy", "",
              "| Module | Mean unaligned ATE m | Mean orientation RMSE rad | Peak fuel/frame |",
              "|---|---:|---:|---:|"]
    for name in dict.fromkeys(row["model"] for row in startup_guest):
        r = [row for row in startup_guest if row["model"] == name]
        startup_points[name] = {"ate":average([x["metrics"] for x in r],"ate_rmse"),
                                "fuel":max(x["fuel_per_frame_max"] for x in r)}
        lines.append(f"| {name} | {startup_points[name]['ate']:.3f} | "
                     f"{average([x['metrics'] for x in r],'rotation_rmse'):.3f} | "
                     f"{startup_points[name]['fuel']:,} |")
    lines += ["",link("deployment","guest.json","Per-episode guest fuel, failure fill, calibrated pose, orientation and velocity metrics")
              +" · "+link("native_startup","guest.json","Fixed startup native replay"),
              "", "Fuel includes preprocessing, history management, model, orientation updates and output conversion. "
              "Guest rotation modules feed corrected attitude back into derotation. "
              "Rotation acceptance fields in the guest results are paired host measurements.",""]
    lines += ["## Distillation control","",
              "The filtered teacher improved the paired proxy seeds and both native flights with fixed startup "
              "calibration. Teacher outputs were generated on training parents only. The compact students share "
              "initialization, architecture, inputs and label loss. The distilled arm adds a 0.5-weighted teacher loss.","",
              "| Student | Parameters | Proxy dev ATE m | Native guest ATE m | Peak fuel/frame |",
              "|---|---:|---:|---:|---:|"]
    student_results = load("student","scores.json")
    student_guest = load("student_guest","guest.json")
    student_points = {}
    for row in student_results:
        name = row["student"]
        r = [x for x in student_guest if x["model"] == name]
        student_points[name] = {"ate":average([x["metrics"] for x in r],"ate_rmse"),
                                "fuel":max(x["fuel_per_frame_max"] for x in r)}
        lines.append(f"| {name} | {row['parameters']} | {average(row['rows'],'ate'):.3f} | "
                     f"{student_points[name]['ate']:.3f} | {student_points[name]['fuel']:,} |")
    lines += ["", link("student","scores.json","Student checkpoints and development scores")+" · "+
              link("student_guest","guest.json","Student per-episode guest measurements"), ""]
    if args.pareto:
        lines += ["## Supplied Pareto curve","",
                  "[User-supplied scoreboard snapshot](supplied-pareto.png)","",
                  "The screenshot labels its log–log axes as mean ATE and maximum fuel per frame. "
                  "Visual readings place the frontier near 4.4 m at one million fuel and roughly 4.1 m in the "
                  "15–16 million fuel region. A much later step falls below 1 m at several billion fuel. These "
                  "are approximate readings from an image. The screenshot provides neither the exact reference "
                  "data nor the scorer configuration. Local guest points use two identified archives, so their "
                  "coordinates cannot establish scoreboard placement or an area gain.",""]
    visual_win=min(proxy_order,key=proxy_order.get)
    native_win=min(native_order,key=native_order.get)
    temporal_name=manifests["deployment"]["modules"]["temporal"]["head"]
    memory = {name: average([v for s in heads if s["variant"]==name for v in s["rows"]],"ate")
              for name in ("frame","ema","ssm","gru","selective")}
    geometry=guest_summary.get("geometry",{})
    learned=guest_summary.get("learned",{})
    os.environ.setdefault("MPLCONFIGDIR",str((directory/"plot-cache").resolve()))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.2,4.6), layout="constrained")
    points = {
        "CNN": startup_points["cnn"], "CNN + fixed EMA": startup_points["temporal"],
        "CNN + geometry": startup_points["geometry"], "CNN + learned rotation": startup_points["learned"],
        "Compact labels": student_points["labels"], "Compact distilled": student_points["distilled"],
    }
    for name, point in points.items():
        ax.scatter(point["fuel"],point["ate"],label=name,s=44)
    ax.set(xscale="log",yscale="log",xlabel="Peak guest fuel per frame",ylabel="Mean unaligned ATE (m)",
           title="Stage-2 point measurements on two local archives")
    ax.legend(fontsize=8)
    ax.grid(alpha=.2,which="both")
    fig.savefig(directory/"local-fuel-ate.png",dpi=160)
    plt.close(fig)
    lines += ["[Measured local cost and accuracy](local-fuel-ate.png)",""]
    lines += ["## Decisions","",
              "| Question | Evidence | Conclusion | Next action |","|---|---|---|---|",
              f"| Does long-baseline vision help? | {proxy_order['pair_derot']:.3f} m short, {proxy_order['triple_derot']:.3f} m short+long | "
              "Short-plus-long helped both proxy seeds under derotation; native input ranking shifted | Test the paired ablation on more native scenes |",
              f"| Does learned memory help beyond filtering? | EMA {memory['ema']:.3f}, SSM {memory['ssm']:.3f}, GRU {memory['gru']:.3f}, selective {memory['selective']:.3f} m | "
              "Fixed filtering is the reference for further temporal work | Validate the cheaper control on independent scenes |",
              f"| Does visual/learned rotation correction help? | Guest geometry {geometry.get('ate',float('nan')):.3f} m and learned "
              f"{learned.get('ate',float('nan')):.3f} m vs CNN {guest_summary['cnn']['ate']:.3f} m | "
              "Judge attitude improvement and trajectory benefit separately; LK updates dominate peak fuel | Check nominal and injected evidence with the startup control |",
              "| Are moving starts supported causally? | Prefix and reset tests plus raw 5 s crop replays | Implemented and measured on the proxy sample | Add fresh non-hover flights |",
              f"| Does the proxy ranking transfer? | Best proxy {visual_win}; best native host {native_win} | Two native flights provide limited transfer evidence | Retest a frozen ranking on a broader native split |",
              f"| What accuracy–fuel point is actually achieved? | Startup {temporal_name} guest {startup_points['temporal']['ate']:.3f} m at "
              f"{startup_points['temporal']['fuel']:,} peak | Measured on the same two native archives | Freeze the baseline for an independent native comparison |",
              "", "See the research README for the exact commands and environment."]
    (directory/"report.md").write_text("\n".join(lines)+"\n")
    write(directory/"summary.json",{"guest":guest_summary,"guest_startup":startup_points,"guest_students":student_points,
                                        "proxy":proxy_order,"native_host":native_order,"heads":memory})
    manifest.update(status="completed")
    write(directory/"manifest.json",manifest)
    print(directory,flush=True)




def archived_model(path):
    path=Path(path)
    meta=json.loads((path/"config.json").read_text())
    with np.load(path/"weights.npz") as raw:
        model={"variant":meta["variant"],"kind":meta["kind"],"settings":meta.get("settings"),
               "encoder":{k[4:]:raw[k] for k in raw if k.startswith("enc/")},
               "temporal":{k[5:]:raw[k] for k in raw if k.startswith("head/")}}
    identity={"weights_sha256":digest(path/"weights.npz"),"config_sha256":digest(path/"config.json")}
    return model,meta["config"],identity

def joint_payload(path):
    from seq_heads import Joint, joint_model
    saved=torch.load(path,map_location="cpu",weights_only=True)
    net=Joint(saved["settings"])
    net.load_state_dict(saved["state"])
    return joint_model(net),saved["config"]


def joint_deploy():
    """Freeze representatives before scoring disjoint native final-test archives."""
    import csv
    import resource
    from importlib.metadata import version
    from pairs import config

    parser=argparse.ArgumentParser(description=joint_deploy.__doc__)
    parser.add_argument("--finalists",type=Path)
    parser.add_argument("--data-run",type=Path)
    parser.add_argument("--smoke",type=Path)
    parser.add_argument("--profile",type=Path)
    parser.add_argument("--development-screen",action="store_true")
    parser.add_argument("--report",action="store_true")
    for name in ("inventory","screen","feedback","export-smoke","final","teacher","guest-dev","motion","pilot","unoptimized-smoke"):
        parser.add_argument(f"--{name}",type=Path)
    args=parser.parse_args()
    if args.report:
        joint_report(args)
        return
    from viobench.tools.datasets.storage import read_episode
    from viobench.tools.runner.engine import Engine
    from viobench.tools.runner.sandbox import Limits
    from viobench.tools.runner.run import run_episode
    cfg=config()
    models={}
    freeze={}
    if args.profile:
        archive="results/20261117T235707Z-deployment-6157297d/temporal"
        reference,spec,identity=archived_model(archive)
        parents=[{"path":str(args.profile),"sha256":digest(args.profile),"scene":"old-smoke","split":"profile"}]
        for stage in ("abi","orientation","resize","warp","cnn","full"):
            model={**reference,"settings":{"profile_stage":stage}}
            if stage=="cnn":
                model["kind"]=None
            models[stage]=(model,spec)
            freeze[stage]=identity.copy()
    elif args.smoke:
        from seq_heads import Joint, joint_model
        torch.manual_seed(51)
        settings=dict(variant="triple_derot",kind="selective",packet_mode="ordered",embedding=48,hidden=64,
                      width=32,height=24,bias_head=True,feedback=True)
        model=joint_model(Joint(settings))
        models["random-smoke"]=(model,{**cfg,"policy":"rolling","ordered_packet":True})
        parents=[{"path":str(args.smoke),"sha256":digest(args.smoke),"scene":"old-smoke","split":"regression"}]
        freeze["random-smoke"]={"purpose":"ABI and fuel smoke with random parameters"}
    else:
        if not args.finalists or not args.data_run:
            raise ValueError("finalist and native data runs are required")
        run=json.loads((args.finalists/"manifest.json").read_text())
        data=json.loads((args.data_run/"manifest.json").read_text())
        if run["status"]!="completed" or (not args.development_screen and data["status"]!="completed"):
            raise ValueError("finalists and native generation must finish before scoring")
        target="development" if args.development_screen else "final_test"
        qualified=data["datasets"][target]
        if args.development_screen:
            qualified=qualified[:2]
        prior=set(x["scene"] for group in run["datasets"].values() for x in group)
        if prior & {r["scene"] for r in qualified}:
            raise ValueError("test and fitting scenes overlap")
        earlier_hashes={x["sha256"] for group in run["datasets"].values() for x in group}
        test_hashes={x["sha256"] for x in qualified}
        if not qualified or len(test_hashes)!=len(qualified) or earlier_hashes & test_hashes:
            raise ValueError("evaluation archive identities must be new and unique")
        parents=[{**r,"split":target} for r in qualified]
        rows=json.loads((args.finalists/"scores.json").read_text())
        for name in ("ema","ssm","bias"):
            family="selective" if args.development_screen and name=="ssm" else name
            choices=sorted((r for r in rows if r["model"]==family),key=lambda r:np.mean([s["ate"] for s in r["rows"]]))
            record=choices[len(choices)//2]
            if digest(record["checkpoint"]) != record["sha256"]:
                raise ValueError("checkpoint changed")
            models[name]=joint_payload(record["checkpoint"])
            freeze[name]={"checkpoint":record["checkpoint"],"sha256":record["sha256"],
                          "seed":record["seed"],"selection":"median development seed"}
        if args.teacher:
            student_manifest=json.loads((args.teacher/"manifest.json").read_text())
            if student_manifest["status"]!="completed":
                raise ValueError("student comparison is incomplete")
            if student_manifest["datasets"]!=run["datasets"]:
                raise ValueError("student and finalist dataset rosters differ")
            student_rows=json.loads((args.teacher/"scores.json").read_text())
            for variant in ("student-labels","student-motion"):
                ranked=sorted((r for r in student_rows if r["model"]==variant),
                              key=lambda r:np.mean([s["ate"] for s in r["rows"]]))
                chosen=ranked[len(ranked)//2]
                if digest(chosen["checkpoint"])!=chosen["sha256"]:
                    raise ValueError("student checkpoint hash changed")
                models[variant]=joint_payload(chosen["checkpoint"])
                freeze[variant]={"checkpoint":chosen["checkpoint"],"sha256":chosen["sha256"],"seed":chosen["seed"]}
        model,spec=models["bias"]
        models["bias-disabled"]=({**model,"settings":{**model["settings"],"feedback":False}},spec)
        freeze["bias-disabled"]=freeze["bias"].copy()
        legacy=[
            ("previous-ema","results/20261117T235707Z-deployment-6157297d/temporal"),
            ("previous-student","results/20261117T235948Z-deployment-caa48f46/distilled"),
        ]
        for name,path in legacy:
            model,spec,identity=archived_model(path)
            models[name]=(model,spec)
            freeze[name]=identity
    directory,manifest=open_run("joint-profile" if args.profile else "joint-guest-smoke" if args.smoke else "joint-dev-guest" if args.development_screen else "joint-final",cfg,{"evaluation":parents})
    print(directory,flush=True)
    runtime=CLASSICAL/"build"/"runtime.wasm"
    manifest.update(frozen=freeze,runtime_sha256=digest(runtime),wasmtime=version("wasmtime"),
                    limits=asdict(Limits()),benchmark_revision=subprocess.check_output(
                        ["git","-C",str(BENCH),"rev-parse","HEAD"],text=True).strip(),
                    scorer="local VIOBench; live server unverified",selection_frozen_utc=datetime.now(timezone.utc).isoformat())
    if args.finalists:
        manifest["finalist_manifest_sha256"]=digest(args.finalists/"manifest.json")
    if args.teacher:
        manifest["teacher_manifest_sha256"]=digest(args.teacher/"manifest.json")
    for name,(m,spec) in models.items():
        freeze[name]["settings"]=m.get("settings")
        freeze[name]["runtime_config"]=spec
    write(directory/"manifest.json",manifest)
    results=[]
    modules={}
    try:
        engine=Engine()
        for name,(model,spec) in models.items():
            wasm=bundle_model(directory/name,model,spec,runtime)
            modules[name]={"sha256":digest(wasm),"wasm_bytes":wasm.stat().st_size,
                           "weights_bytes":(directory/name/"weights.npz").stat().st_size}
            manifest["modules"]=modules
            write(directory/"manifest.json",manifest)
            for parent in parents:
                if digest(parent["path"]) != parent["sha256"]:
                    raise ValueError("evaluation archive changed")
                ep=read_episode(parent["path"])
                log=directory/f"{name}-{ep.hash[:8]}"
                result,states,fuel=run_episode(wasm,ep,engine,Limits(),log)
                host,host_states=native_host(ep,model,spec)
                valid=np.isfinite(states).all(axis=1)
                initial=ep.frame_times<=ep.frame_times[0]+1.
                targets=ep.ground_truth_state()
                dp=np.where(valid[:,None],states[:,:3],0.)-targets[:,:3]
                speed=np.linalg.norm(targets[:,7:10],axis=1)
                turn=np.linalg.norm(targets[:,10:13],axis=1)
                regime={}
                for category,mask in {"startup":initial,"hover":speed<.15,"moving":speed>=.15,"turn":turn>.25,
                                      "late":ep.frame_times>=ep.frame_times[0]+.5*ep.duration}.items():
                    regime[category]=float(np.sqrt(np.mean(np.sum(dp[mask]**2,axis=1)))) if mask.any() else None
                record={**result.as_dict(),"model":name,"scene":parent["scene"],"split":parent["split"],
                        "coverage":float(valid.mean()),"startup_fuel":int(fuel[:int(initial.sum())].max(initial=0)),
                        "regime_ate":regime,"zero_output_ate":float(np.sqrt(np.mean(np.sum(targets[:,:3]**2,axis=1)))),
                        "host_position_delta_max":float(np.max(np.abs(states[valid,:3]-host_states[valid,:3])))
                        if valid.any() else None,"host_metrics":host,
                        "process_peak_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
                        (1 if os.uname().sysname=="Darwin" else 1024)}
                results.append(record)
                np.savez_compressed(directory/f"{name}-{ep.hash[:8]}.npz",states=states,fuel=fuel)
                write(directory/"guest.json",results)
                print(name,parent["scene"],result.completed,result.metrics["ate_rmse"],result.fuel_per_frame_max,flush=True)
        with (directory/"paired.csv").open("w",newline="") as stream:
            cols=("model","scene","ate","delta_vs_ema","paired_control","delta_vs_paired_control",
                  "peak_fuel","coverage","completed")
            writer=csv.DictWriter(stream,fieldnames=cols)
            writer.writeheader()
            paired={(r["model"],r["scene"]):r["metrics"]["ate_rmse"] for r in results}
            controls={"bias":"bias-disabled","student-motion":"student-labels"}
            for r in results:
                a=r["metrics"]["ate_rmse"]
                ema=paired.get(("ema",r["scene"]))
                control=controls.get(r["model"])
                control_ate=paired.get((control,r["scene"]))
                writer.writerow(dict(model=r["model"],scene=r["scene"],ate=a,
                                     delta_vs_ema=a-ema if ema is not None else None,
                                     paired_control=control,
                                     delta_vs_paired_control=a-control_ate if control_ate is not None else None,
                                     peak_fuel=r["fuel_per_frame_max"],coverage=r["coverage"], completed=r["completed"]))
        manifest["status"]="completed"
    except BaseException as e:
        manifest.update(status="failed",error=repr(e))
        raise
    finally:
        write(directory/"manifest.json",manifest)


def joint_report(args):
    """Generate immutable evidence tables and a Pareto plot from staged artifacts."""
    from collections import defaultdict
    from pairs import config
    paths={"inventory":args.inventory,"native-data":args.data_run,"screen":args.screen,
           "feedback-smoke":args.feedback,"finalists":args.finalists,"export-smoke":args.export_smoke,
            "profile":args.profile,"final":args.final,"teacher":args.teacher,"development-guest":args.guest_dev,
           "native-motion":args.motion,"pilot":args.pilot,"unoptimized-smoke":args.unoptimized_smoke}
    cfg=config()
    out,m=open_run("joint-report",cfg,{})
    manifests={}
    lines=["# CNN–IMU state-space evaluation","",
           "Primary deployment objectives are mean per-flight unaligned ATE and maximum measured Wasm fuel per frame. "
           "Sim(3) is diagnostic. Local VIOBench scoring was used. The live server rule remains unverified.","",
           "## Evidence",""]
    for label,path in paths.items():
        if path:
            cached=json.loads((path/"manifest.json").read_text())
            manifests[label]=cached
            m.setdefault("runs",{})[label]={"path":str(path),"sha256":digest(path/"manifest.json"),"status":cached["status"]}
            lines.append(f"- [{label}](../{path.name}/manifest.json), {cached['status']}")
    if args.inventory:
        audit=manifests["inventory"]
        for label,split in audit["splits"].items():
            lines += ["",f"The complete legacy {label} inventory has {split['archive_count']} parents from "
                      f"{len(split['scenes'])} scenes. Tier breakdown {split['tier_counts']}."]
        lines+=["",f"Archive duplicates {len(audit['duplicated_archive_hashes'])}. Scene overlaps {len(audit['overlap'])}. "
                 "Only the base legacy tier enters training to keep simulation pacing compatible. "
                 "Its rendering domain remains marked as proxy because resolution and image formation differ."]
    if args.data_run:
        data=manifests["native-data"]
        records=json.loads((args.data_run/"audit.json").read_text())
        counts={split:len(rows) for split,rows in data.get("datasets",{}).items()}
        lines+=["","## Native pilot","",
                f"Native allocation {counts}. The pilot archives total {sum(r['bytes'] for r in records)/1e9:.2f} GB. "
                f"Elapsed generation time {data.get('elapsed_s',0)/60:.1f} minutes. "
                "The generator used the upstream HyperDrone camera/sensor preset, 640×480 native images and native IMU packets.",
                "",f"[Native sensor and image audits](../{args.data_run.name}/audit.json)",
                "","The disk budget and measured generation throughput limited this milestone to the pilot. "
                "Thirty-second native flights provide scene diversity. Longer rolls and moving-start stress use "
                "the archived proxy trajectories or raw-crop development replays and are reported separately."]
    if args.motion:
        rows=json.loads((args.motion/"motion.json").read_text())
        lines += ["",f"Across {len(rows)} audited native parents, mean per-flight frame fractions were "
                  f"{np.mean([r['forward_fraction'] for r in rows]):.1%} forward, "
                  f"{np.mean([r['backward_fraction'] for r in rows]):.1%} backward, "
                  f"{np.mean([r['sideways_fraction'] for r in rows]):.1%} sideways and "
                  f"{np.mean([r['vertical_fraction'] for r in rows]):.1%} vertical. "
                  f"Stationary intervals flagged on {sum(r['stationary_flag'] for r in rows)} flights remained in the roster. "
                  "The current simulator autopilot leaves backward-motion and sustained sideways coverage sparse.",
                  "",f"[Direction, turn, acceleration and speed audit](../{args.motion.name}/motion.json)"]
    lines += ["","## Estimator and training","",
              "The compact CNN produces image embeddings from current, quarter-second and one-second context. "
              "The IMU branch uses either packet summaries or four timestamped subintervals with validity flags. "
              "A 64-state diagonal or input-selective SSM gates its recurrence with elapsed time. "
              "The deployment order is gyro propagation with the preceding bias, current derotation and features, "
              "recurrent prediction, endpoint-velocity integration, and bounded bias adjustment for later frames.",
              "", "The rolling calibration retries at 0.2-second intervals with robust gyro, acceleration and "
              "image-motion statistics. It never imposes zero velocity. Learned gyro bias is clipped to 0.12 rad/s per axis "
              "and updates with a 0.8-second time constant. The nominal and perturbed streams preserve the original labels. "
              "Controlled gyro bias varies by parent, in sensor axes. The target is the added component after the "
              "difference in startup or rolling calibration. Instantaneous physical simulator bias was unavailable in the archives.",
              "", "Velocity and timestamped displacement losses use cached estimated orientation. The added gyro "
              "objective includes a differentiable small-angle trajectory approximation. Exact feedback replay "
              "reintegrates individual samples and reconstructs visual inputs, with the same checkpoint replayed "
              "with feedback disabled for attribution. An accelerometer-bias head was deferred because there is no "
              "validated target or independent inertial propagation consumer.",
              "", "These are simplified state-space models. [S5](https://arxiv.org/abs/2208.04933) · "
              "[Mamba](https://arxiv.org/abs/2312.00752) · "
              "[Learned IMU Bias Prediction](https://arxiv.org/abs/2505.06748)",""]
    all_rows={}
    for label in ("screen","feedback-smoke","pilot","finalists","teacher"):
        root=paths[label]
        if not root or not (root/"scores.json").exists():
            continue
        rows=json.loads((root/"scores.json").read_text())
        groups=defaultdict(list)
        for r in rows:groups[r["model"]].append(r)
        all_rows[label]=rows
        lines += ["",f"## {label.replace('-', ' ').title()}","",
                  "| Candidate | Seeds scored | Dev ATE by seed (m) | Moving stress ATE (m) | Parameters |",
                  "|---|---:|---|---|---:|"]
        for name, rs in groups.items():
            means=[np.mean([x["ate"] for x in r["rows"]]) for r in rs]
            stress=[np.mean([x["ate"] for x in r["moving_stress"]]) for r in rs if r.get("moving_stress")]
            lines.append(f"| {name} | {len(rs)} | {', '.join(f'{v:.3f}' for v in means)} | "
                         f"{', '.join(f'{v:.3f}' for v in stress) or '—'} | {rs[0]['parameters']:,} |")
            if name=="bias":
                for r in rs:
                    stress=r.get("moving_stress") or []
                    if not stress:
                        continue
                    trend=np.mean([x["ate"]-x["disabled_feedback_ate"] for x in stress])
                    rmse=np.mean([x["added_bias_rmse_rad_s"] for x in stress])
                    lines.append(f"| Bias feedback delta, seed {r['seed']} | — | — | {trend:+.3f} m versus disabled; "
                                 f"added-bias RMSE {rmse:.4f} rad/s | — |")
        lines+=["",f"[Per-flight results, checkpoints and learning curves](../{root.name}/scores.json)"]
    finalists=all_rows.get("finalists",[])
    pilot=all_rows.get("pilot",[])
    if finalists or pilot:
        lines += ["","## Calibration, modality and memory ablations","",
                  "| Candidate | Seed | Rolling ATE m | Startup ATE m | Feedback disabled ATE m | Reset at 1 s ATE m | Accepted / flights | First acceptance median s | Moving / turning accepts |",
                  "|---|---:|---:|---:|---:|---:|---|---:|---:|"]
        for scope, rec in [("Mixed", r) for r in finalists]+[("Native pilot", r) for r in pilot]:
            if not any(key in rec for key in ("startup_policy","disabled_feedback","reset_1s")):
                continue
            scores=rec["rows"]
            accepted=[x for x in scores if x.get("calibration_accepted_at") is not None]
            first=f"{np.median([x['calibration_accepted_at'] for x in accepted]):.2f}" if accepted else "—"
            moving=sum(x["calibration_while_moving"] for x in accepted)
            turning=sum(x["calibration_while_turning"] for x in accepted)
            def avg(key):
                return f"{np.mean([x['ate'] for x in rec[key]]):.3f}" if rec.get(key) else "—"
            lines.append(f"| {scope} / {rec['model']} | {rec['seed']} | {avg('rows')} | {avg('startup_policy')} | "
                         f"{avg('disabled_feedback')} | {avg('reset_1s')} | {len(accepted)}/{len(scores)} | {first} | {moving} / {turning} |")
        lines += ["","Moving acceptance is speed greater than 0.15 m/s at first calibration. "
                  "Turning acceptance is ground-truth angular rate greater than 0.12 rad/s. "
                  "Moving and turning have different implications for gyro bias."]
    if all_rows:
        os.environ.setdefault("MPLCONFIGDIR",str((out/"plot-cache").resolve()))
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        traces=[(name,rs) for name,rs in all_rows.items() if rs]
        fig, axes=plt.subplots(1,len(traces),figsize=(4.7*len(traces),3.8),squeeze=False,layout="constrained")
        for ax,(name,rows) in zip(axes[0],traces):
            seen=set()
            for r in rows:
                h=r["history"]
                label=r["model"]
                ax.plot([x["epoch"] for x in h],[x["dev_ate"] for x in h],
                        alpha=.7,label=label if label not in seen else None)
                seen.add(label)
            ax.set(title=name,xlabel="Epoch",ylabel="Development ATE (m)")
            ax.legend(fontsize=6,ncol=2)
        fig.savefig(out/"learning-curves.png",dpi=135)
        plt.close(fig)
        lines += ["","[Development learning curves](learning-curves.png)"]
    if args.profile and (args.profile/"guest.json").is_file():
        profile=json.loads((args.profile/"guest.json").read_text())
        lines+=["","## Guest profiling on the old smoke archive","",
                "| Cumulative probe | Peak fuel/frame |","|---|---:|"]
        for r in profile:
            lines.append(f"| {r['model']} | {r['fuel_per_frame_max']:,} |")
        lines += ["","These cumulative active-code runs include runtime and output conversion. Stage peaks may occur "
                  "on different frames, so differences of peaks are approximate marginal costs."]
    if args.export_smoke:
        d=json.loads((args.export_smoke/"guest.json").read_text())[0]
        lines += ["",f"The random-weight selective SSM and bias-feedback export covered {d['frames']} frames "
                  f"at {d['fuel_per_frame_max']:,} peak fuel. Its maximum host-to-guest position difference was "
                  f"{d['host_position_delta_max']:.4f} m on this smoke archive. Treat its ATE as a plumbing result."]
        if args.unoptimized_smoke:
            before=json.loads((args.unoptimized_smoke/"guest.json").read_text())[0]
            same=abs(before["metrics"]["ate_rmse"]-d["metrics"]["ate_rmse"])<1e-8
            lines += ["",f"The same random-weight archive before the short-window quantile optimization peaked at "
                      f"{before['fuel_per_frame_max']:,}. Relative to that export, ATE was "
                      f"{'unchanged to 1e-8 m' if same else 'changed'}. "
                      "The original peak occurred on the first nonempty IMU packet."]
    if args.guest_dev and (args.guest_dev/"guest.json").exists():
        measured=json.loads((args.guest_dev/"guest.json").read_text())
        lines += ["","## Early trained guest screen on two native development scenes","",
                  "| Module | Mean unaligned ATE m | Peak fuel/frame | Completed |",
                  "|---|---:|---:|---:|"]
        for name in dict.fromkeys(r["model"] for r in measured):
            rows=[r for r in measured if r["model"]==name]
            lines.append(f"| {name} | {np.mean([r['metrics']['ate_rmse'] for r in rows]):.3f} | "
                         f"{max(r['fuel_per_frame_max'] for r in rows):,} | {sum(r['completed'] for r in rows)}/{len(rows)} |")
        lines += ["","The new candidates in this guest screen were fitted on four proxy scenes. "
                   "The native development sample measures transfer and compute for this smaller pipeline."]
    final={}
    if args.final and (args.final/"guest.json").exists():
        results=json.loads((args.final/"guest.json").read_text())
        groups=defaultdict(list)
        paired={r["scene"]:r["metrics"]["ate_rmse"] for r in results if r["model"]=="ema"}
        rng=np.random.default_rng(117)
        lines+=["","## Frozen fresh native test","",
                "| Model | Complete | Mean ATE m | Mean Sim(3) m | Peak fuel | Paired Δ vs EMA m (scene bootstrap 95%) |",
                "|---|---:|---:|---:|---:|---|"]
        for r in results:groups[r["model"]].append(r)
        for name,rows in groups.items():
            ates=[r["metrics"]["ate_rmse"] for r in rows]
            deltas=np.array([r["metrics"]["ate_rmse"]-paired[r["scene"]] for r in rows if r["scene"] in paired])
            ci=np.quantile(rng.choice(deltas,(4000,len(deltas))).mean(1),[.025,.975]) if len(deltas)>1 else None
            peak=max(r["fuel_per_frame_max"] for r in rows)
            final[name]={"ate":float(np.mean(ates)),"fuel":peak,
                         "coverage":float(np.mean([r["coverage"] for r in rows])),
                         "complete":all(r["completed"] and r["coverage"]==1. for r in rows)}
            lines.append(f"| {name} | {sum(r['completed'] for r in rows)}/{len(rows)} | {np.mean(ates):.3f} | "
                         f"{np.mean([r['metrics']['sim3_ate_rmse'] for r in rows]):.3f} | {peak:,} | "
                         f"{f'{deltas.mean():+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}]' if ci is not None else '—'} |")
        lines+=["",f"[Per-flight paired results](../{args.final.name}/paired.csv) · "
                 f"[Elapsed/regime errors, coverage, fuel, process memory and failures](../{args.final.name}/guest.json)"]
        if manifests["final"]["status"]=="completed":
            for name,control in (("bias","bias-disabled"),("student-motion","student-labels")):
                if name in groups and control in groups:
                    paired_control={r["scene"]:r["metrics"]["ate_rmse"] for r in groups[control]}
                    delta=np.array([r["metrics"]["ate_rmse"]-paired_control[r["scene"]] for r in groups[name]])
                    lo,hi=np.quantile(rng.choice(delta,(4000,len(delta))).mean(1),[.025,.975])
                    lines += [f"- {name} vs {control}. Mean paired Δ {delta.mean():+.3f} m "
                              f"(scene bootstrap 95% [{lo:+.3f}, {hi:+.3f}])."]
            eligible={n:r for n,r in final.items() if r["complete"]}
            nondominated=sorted(
                [(n,r) for n,r in eligible.items()
                 if not any(q["ate"]<=r["ate"] and q["fuel"]<=r["fuel"] and
                            (q["ate"]<r["ate"] or q["fuel"]<r["fuel"]) for q in eligible.values())],
                key=lambda item:item[1]["fuel"])
            os.environ.setdefault("MPLCONFIGDIR",str((out/"plot-cache").resolve()))
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig,ax=plt.subplots(figsize=(7,4.4),layout="constrained")
            if nondominated:
                ax.step([r["fuel"] for _,r in nondominated],[r["ate"] for _,r in nondominated],
                        where="post",color="0.4",linestyle="--",label="Measured frontier",zorder=1)
            for name,r in final.items():
                ax.scatter(r["fuel"],r["ate"],label=name if r["complete"] else f"{name} (incomplete)",
                           marker="o" if r["complete"] else "x",zorder=2)
            ax.set(xscale="log",yscale="log",xlabel="Peak fuel/frame",ylabel="Mean unaligned ATE (m)")
            ax.legend(fontsize=8)
            fig.savefig(out/"pareto.png",dpi=150)
            plt.close(fig)
            lines+=["","[Fresh-set Pareto plot](pareto.png)"]
    def mean_for(records,name,key="rows"):
        vals=[x["ate"] for r in records if r["model"]==name for x in r.get(key,[])]
        return float(np.mean(vals)) if vals else None

    lines += ["","## Decision summary",""]
    screen_records=all_rows.get("screen",[])
    if all(mean_for(screen_records,n) is not None for n in ("subset","expanded","wider","resolution")):
        label={n:mean_for(screen_records,n) for n in ("subset","expanded","wider","resolution")}
        lines += [f"- Proxy data and capacity. Subset {label['subset']:.3f} m, expanded {label['expanded']:.3f} m, "
                  f"wider {label['wider']:.3f} m, and higher resolution {label['resolution']:.3f} m. "
                  "Early stopping and the chunk cap constrain the interpretation."]
    if all(mean_for(finalists,n) is not None for n in ("ssm","ema","summary","proxy_ema")):
        label={n:mean_for(finalists,n) for n in ("ssm","ema","summary","proxy_ema")}
        lines += [f"- Estimated-orientation development ATE. Ordered SSM {label['ssm']:.3f} m, "
                  f"ordered EMA {label['ema']:.3f} m, summary SSM {label['summary']:.3f} m, "
                  f"and proxy-only EMA {label['proxy_ema']:.3f} m. Use the per-seed rows to judge consistency."]
    for scope, stage in (("Native-only pilot",pilot),("Mixed-data finalists",finalists)):
        bias_records=[r for r in stage if r["model"]=="bias" and r.get("moving_stress")]
        if bias_records:
            deltas=[x["ate"]-x["disabled_feedback_ate"] for r in bias_records for x in r["moving_stress"]]
            lines += [f"- {scope}, same-checkpoint feedback on moving stress. Mean Δ {np.mean(deltas):+.3f} m across "
                      f"{len(deltas)} seed–scene pairs. This measures the feedback path beyond its auxiliary training loss."]
    teacher=all_rows.get("teacher",[])
    teacher_means={n:mean_for(teacher,n) for n in ("teacher","student-labels","student-motion")}
    if all(v is not None for v in teacher_means.values()):
        lines += [f"- Compact distillation. Teacher dev ATE {teacher_means['teacher']:.3f} m, "
                  f"label-trained student {teacher_means['student-labels']:.3f} m, "
                  f"and motion-distilled student {teacher_means['student-motion']:.3f} m."]
    if final and manifests["final"]["status"]=="completed":
        if nondominated:
            lines += ["- Fresh-set measured frontier. "+", ".join(f"{n} {r['ate']:.3f} m at {r['fuel']:,} fuel"
                                                                    for n,r in nondominated)+"."]
        else:
            lines += ["- Every evaluated candidate had incomplete output on at least one fresh flight."]
    pending=[k for k in ("native-data","native-motion","screen","pilot","finalists","teacher","final") if
             k not in manifests or manifests[k]["status"]!="completed"]
    lines += ["","## Scope and reproducibility",""]
    if pending:
        lines.append("Unfinished evidence at report generation: "+", ".join(pending)+
                     ". These stages do not support a final comparison.")
    lines.append("See the research README for commands, staged prerequisites and the local interpreter paths.")
    (out/"report.md").write_text("\n".join(lines)+"\n")
    write(out/"summary.json",{"final":final,"pending":pending,"training":all_rows})
    m.update(status="completed",pending=pending)
    write(out/"manifest.json",m)
    print(out,flush=True)


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["--joint"]:
        sys.argv.pop(1)
        joint_deploy()
    else:
        main()
