"""Low-resolution proxy-set generator with agility tiers (research only, not the VIOBench storage format).

Flies the same HyperDrone visual-inertial-localization autopilot as `viobench simulate`, but
  * renders at a small resolution (frames are stored as 8-bit gray),
  * shadows the task's agility constants (cruise speed, acceleration, jerk, yaw rate, hover),
  * stores one compressed .npz per flight: 200 Hz IMU, 200 Hz ground truth (p, R, v, w), 20 Hz frames.

    python gen.py --tier agile --scenes ProcTHOR-Train-3 ProcTHOR-Train-4 --episodes 4 --seed 10 -o data/agile

Everything is seeded: the same command produces the same flights.
"""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

_D = dict(margin=0.25, clip=1.0, spacing=0.65, connect=4.0)
TIERS = {
    # stage-1 defaults
    "base": dict(cruise_min=0.45, cruise_max=0.8, max_acc=0.7, max_jerk=2.0, max_yaw=0.8, hover=1.0, **_D),
    # faster pacing constants only (stays slow in practice: the pacer and route geometry throttle it)
    "fastpace": dict(cruise_min=2.0, cruise_max=3.5, max_acc=3.0, max_jerk=8.0, max_yaw=1.8, hover=1.0, **_D),
    # also loosen the tracking pacer, the autopilot's target clip and the roadmap spacing
    "mid": dict(cruise_min=1.0, cruise_max=2.0, max_acc=1.5, max_jerk=4.0, max_yaw=1.2, hover=1.0,
                margin=0.4, clip=1.5, spacing=0.9, connect=4.0),
    "agile": dict(cruise_min=2.0, cruise_max=3.5, max_acc=3.0, max_jerk=8.0, max_yaw=1.8, hover=1.0,
                  margin=0.6, clip=2.5, spacing=1.2, connect=5.0),
    "agile_inflight": dict(cruise_min=2.0, cruise_max=3.5, max_acc=3.0, max_jerk=8.0, max_yaw=1.8, hover=0.0,
                           margin=0.6, clip=2.5, spacing=1.2, connect=5.0),
}

HEADER = """#pragma once
#include <rl_tools/rl/environments/hyperdrone/presets.h>
#include <rl_tools/rl/environments/hyperdrone/operations_cpu.h>
#include <rl_tools/rl/environments/hyperdrone/tasks/visual_inertial_localization/visual_inertial_localization.h>
#include <rl_tools/rl/environments/hyperdrone/tasks/visual_inertial_localization/operations_cpu.h>
#include <cstddef>
namespace hyperdrone_user {
    using T = float;
    using TI = std::size_t;
    namespace hyperdrone = rl_tools::rl::environments::hyperdrone;
    struct SPEC: hyperdrone::presets::X500FPVIMU<T, TI> {
        static constexpr TI INSTANCES_PER_WORLD = @INSTANCES@;
        static constexpr TI N_CAMERA_AGENTS = 1;
        static constexpr TI MAX_DRONES = 1;
        static constexpr TI CAM_WIDTH = @WIDTH@;
        static constexpr TI CAM_HEIGHT = @HEIGHT@;
        using SHADING = rl_tools::hyperlux::High;
        static constexpr bool ENABLE_ANTI_ALIASING = false;
        static constexpr TI ANTI_ALIASING_GRID_SIZE = 1;
        static constexpr bool ENABLE_MOTION_BLUR = false;
        static constexpr TI MOTION_BLUR_SAMPLES = 1;
        static constexpr bool SELF_VISIBLE = false;
        static constexpr T CAMERA_FOV_RANDOMIZATION_RANGE = @FOV_RANGE@;
        static constexpr T CAMERA_MOUNT_ROTATION_RANDOMIZATION_RANGE = 0;
        static constexpr T CAMERA_MOUNT_OFFSET_RANDOMIZATION_RANGE = 0;
        static constexpr T BRIGHTNESS_RANDOMIZATION_RANGE = 0;
    };
    using BASE_WORLD = hyperdrone::World<SPEC>;
    struct TASK_SPEC: hyperdrone::tasks::visual_inertial_localization::Specification<BASE_WORLD> {
        static constexpr TI FRAME_STRIDE = 10;
        static constexpr TI NUM_WAYPOINTS = @WAYPOINTS@;
        static constexpr TI INITIALIZATION_HOLD_STEPS = @HOLD_STEPS@;
        static constexpr T CRUISE_SPEED_MIN = @CRUISE_MIN@;
        static constexpr T CRUISE_SPEED_MAX = @CRUISE_MAX@;
        static constexpr T MAX_ACCELERATION = @MAX_ACC@;
        static constexpr T MAX_JERK = @MAX_JERK@;
        static constexpr T MAX_YAW_RATE = @MAX_YAW@;
        static constexpr T TRACKING_MARGIN = @MARGIN@;
        static constexpr T TARGET_POSITION_ERROR_CLIP = @CLIP@;
        static constexpr T ROADMAP_SPACING = @SPACING@;
        static constexpr T CONNECTION_DISTANCE = @CONNECT@;
    };
    using WORLD = hyperdrone::tasks::visual_inertial_localization::World<TASK_SPEC>;
}
"""

PRIV = {"position": (0, 3), "R": (3, 9), "v": (12, 3), "w": (15, 3)}


def header_path(tier, width, height, instances, waypoints, fov_range):
    t = TIERS[tier]
    values = dict(INSTANCES=instances, WIDTH=width, HEIGHT=height, FOV_RANGE=repr(float(fov_range)),
                  WAYPOINTS=waypoints, HOLD_STEPS=int(round(t["hover"] * 200)), CRUISE_MIN=repr(float(t["cruise_min"])),
                  CRUISE_MAX=repr(float(t["cruise_max"])), MAX_ACC=repr(float(t["max_acc"])),
                  MAX_JERK=repr(float(t["max_jerk"])), MAX_YAW=repr(float(t["max_yaw"])),
                  MARGIN=repr(float(t["margin"])), CLIP=repr(float(t["clip"])), SPACING=repr(float(t["spacing"])),
                  CONNECT=repr(float(t["connect"])))
    text = HEADER
    for k, v in values.items():
        text = text.replace(f"@{k}@", str(v))
    assert "@" not in text
    cache = Path.home() / ".cache" / "viobench"
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"research_world-{hashlib.sha256(text.encode()).hexdigest()[:12]}.h"
    if not path.exists():
        path.write_text(text)
    return path


def fly(env, seed, steps, width, height):
    """One round of parallel flights. Returns per-instance dicts (crashed ones dropped)."""
    import cv2
    from viobench.tools.datasets.generate.simulation import mount_to_body_camera
    from viobench.tools.abi.config import pinhole_intrinsics

    total = env.total_instances
    lp, li = env.observation_layout_privileged, env.observation_layout_imu
    env.reset(np.ones(total, dtype=bool))
    params = env.instance_parameters()

    def priv():
        s = np.asarray(env.observe_privileged())
        out = {}
        for k, (o, n) in PRIV.items():
            o, n = lp.blocks.get({"R": "orientation_rotation_matrix", "v": "linear_velocity", "w": "angular_velocity"}.get(k, k), (o, n))
            out[k] = s[:, o:o + n].copy()
        return out

    s = priv()
    gt_p, gt_R, gt_v, gt_w = [s["position"]], [s["R"]], [s["v"]], [s["w"]]
    imu, frames, ftimes = [], [], []
    terminated = np.zeros(total, dtype=bool)
    def grab(t):
        fr = np.asarray(env.frames())  # (total, H, W, 3) float [0,1]; with FRAME_STRIDE=10 a fresh render
        g = (fr[..., 0] * 0.299 + fr[..., 1] * 0.587 + fr[..., 2] * 0.114)  # appears right after every 10th step
        frames.append(np.clip(np.rint(g * 255), 0, 255).astype(np.uint8))
        ftimes.append(t)

    grab(0.0)
    for step in range(steps):
        env.step()
        if (step + 1) % 10 == 0:
            grab((step + 1) * 0.005)
        smp = np.asarray(env.observe_imu())
        oa, _ = li.blocks.get("accelerometer", (0, 3))
        og, _ = li.blocks.get("gyroscope", (3, 3))
        imu.append(np.concatenate([np.full((total, 1), (step + 1) * 0.005), smp[:, oa:oa + 3], smp[:, og:og + 3]], 1))
        s = priv()
        gt_p.append(s["position"]); gt_R.append(s["R"]); gt_v.append(s["v"]); gt_w.append(s["w"])
        terminated |= np.asarray(env.terminated()).astype(bool).reshape(-1)
    out = []
    for i in range(total):
        if terminated[i]:
            continue
        cam = params[i]["cameras"].get("front") or next(iter(params[i]["cameras"].values()))
        fov = float(cam["fov"])
        K = pinhole_intrinsics(width, height, fov)
        out.append(dict(
            imu=np.stack(imu)[:, i].astype(np.float64),
            gt_t=np.arange(steps + 1) * 0.005,
            gt_p=np.stack(gt_p)[:, i].astype(np.float32), gt_R=np.stack(gt_R)[:, i].reshape(-1, 3, 3).astype(np.float32),
            gt_v=np.stack(gt_v)[:, i].astype(np.float32), gt_w=np.stack(gt_w)[:, i].astype(np.float32),
            frames=np.stack(frames)[:, i], frame_times=np.asarray(ftimes),
            T_body_camera=mount_to_body_camera(cam["mount"]), fov=fov, K=json.dumps(K, default=float),
            params=json.dumps(params[i], default=float)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="agile", choices=list(TIERS))
    ap.add_argument("--scenes", nargs="+", default=["ProcTHOR-Train-2"])
    ap.add_argument("--episodes", type=int, default=4, help="flights per scene (rounded up to instances)")
    ap.add_argument("--instances", type=int, default=4)
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--width", type=int, default=160)
    ap.add_argument("--height", type=int, default=120)
    ap.add_argument("--fov", type=float, default=120.0)
    ap.add_argument("--fov-range", type=float, default=15.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    import hyperdrone
    from viobench.tools.datasets.generate.simulation import scene_references

    out = Path(a.output); out.mkdir(parents=True, exist_ok=True)
    waypoints = max(8, int(round(a.duration * 0.8 * max(1.0, TIERS[a.tier]["cruise_max"] / 0.8))))
    hdr = header_path(a.tier, a.width, a.height, a.instances, waypoints, a.fov_range)
    steps = int(round(a.duration * 200))
    seed = a.seed
    for name, ref in scene_references(a.scenes).items():
        env = hyperdrone.HyperDrone([ref], config=hyperdrone.Config(num_worlds=1, spec_header=str(hdr)), seed=seed,
                                   parameters={"cameras": {"camera0": {"fov": a.fov}}})
        written = 0
        tries = 0
        while written < a.episodes and tries < 3 * a.episodes:
            t0 = time.perf_counter()
            flights = fly(env, seed, steps, a.width, a.height)
            for f in flights:
                if written >= a.episodes:
                    break
                path = out / f"{a.tier}-{name}-s{seed:05d}-{written:02d}.npz"
                np.savez_compressed(path, tier=a.tier, scene=name, seed=seed, **f)
                written += 1
            tries += a.instances
            print(f"{name} seed {seed}: {len(flights)}/{a.instances} ok, {time.perf_counter() - t0:.1f}s", flush=True)
            seed += 1
        env.close()




def native_main():
    """Render scene-disjoint 640x480 VIOBench episodes with the upstream camera and sensors."""
    from dataclasses import asdict
    import shutil
    import subprocess

    from viobench.tools.datasets.generate.simulation import SimConfig, scene_references, simulate
    from viobench.tools.datasets.storage import write_episode, read_episode
    from datetime import datetime, timezone
    from uuid import uuid4
    from importlib.metadata import version
    from pairs import config, digest
    cfg = config()
    joint = cfg["joint"]
    groups = {"train":joint["pilot_train"], "development":joint["pilot_dev"], "final_test":joint["final_test"]}
    scenes = [i for group in groups.values() for i in group]
    if len(set(scenes)) != len(scenes):
        raise ValueError("scene overlap")
    known = scene_references([f"ProcTHOR-Train-{n}" for n in scenes])
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-native-data-{uuid4().hex[:8]}"
    out = Path("results")/run_id
    out.mkdir(parents=True)
    def write(path, value):
        tmp = path.with_suffix(".partial")
        tmp.write_text(json.dumps(value,indent=2,allow_nan=False,default=lambda x:x.tolist())+"\n")
        tmp.replace(path)
    manifest = {"status":"running","config":cfg,"config_sha256":digest("experiments.json"),
                "source_sha256":digest(__file__),"metric":"unaligned_first_camera_ate_m",
                "packages":{name:version(name) for name in ("hyperdrone","hyperlux","numpy")}}
    print(out, flush=True)
    dest = Path("data") / out.name
    dest.mkdir()
    log = out/"generation.log"
    os.environ.setdefault("VIOBENCH_CACHE", str(Path("data/hyperlux-cache").resolve()))
    free = shutil.disk_usage(".").free
    options = SimConfig(instances=1, duration_seconds=joint["pilot_duration_s"], spool=str(dest.resolve()))
    bench_dir = Path(__file__).resolve().parents[4] / "Final Project" / "viobench"
    manifest.update(plan=groups, detail=asdict(options), disk_free_before=free,
                    estimated_archive_bytes=joint["peak_archive_estimate_bytes"],
                    benchmark_revision=subprocess.check_output(["git","-C",str(bench_dir),"rev-parse","HEAD"],text=True).strip(),
                    reduced_from={"train":96,"development":24,"final_test":24},
                    reduction_reason="An extrapolation from the previous native smoke exceeds measured free storage.")
    write(out/"manifest.json",manifest)
    started = time.monotonic()
    try:
        if free < joint["peak_archive_estimate_bytes"] + 3000000000:
            raise OSError("insufficient storage for planned pilot plus JIT/spool")
        records = {}
        audits = []
        for split, ids in groups.items():
            records[split] = []
            directory = dest/split
            directory.mkdir()
            for n in ids:
                name = f"ProcTHOR-Train-{n}"
                seed = 43100+n
                def log_event(message):
                    text = str(message)
                    print(text,flush=True)
                    with log.open("a") as stream:
                        stream.write(text+"\n")
                try:
                    for episode in simulate(options,{name:known[name]},1,seed=seed,log=log_event):
                        path = directory / (episode.name+".zip")
                        write_episode(episode,path)
                        record = {"path":str(path),"scene":name,"sha256":digest(path),"seed":seed,"domain":"benchmark"}
                        ep = read_episode(path)
                        images = sum(img.shape[:2]==(480,640) and img.dtype==np.uint8 for img in ep.frames)
                        state = ep.ground_truth_state()
                        speed = np.linalg.norm(state[:,7:10],axis=1)
                        turn = np.linalg.norm(state[:,10:13],axis=1)
                        audits.append({**record,"split":split,"bytes":path.stat().st_size,
                                       "valid_images":images,"frames":len(ep.frame_times),
                                       "duration":float(ep.duration),"frame_time_order":bool((np.diff(ep.frame_times)>0).all()),
                                       "imu_time_order":bool((np.diff(ep.imu[:,0])>0).all()),"imu_rows":len(ep.imu),
                                       "imu_packet_counts":sorted({len(ep.imu_window(i)) for i in range(len(ep.frame_times))}),
                                       "initial_speed":float(speed[0]),"speed_percentiles":np.percentile(speed,[10,50,90]).tolist(),
                                       "turn_percentiles":np.percentile(turn,[10,50,90]).tolist(),
                                       "intrinsics":ep.config["camera"],"T_bc":ep.T_body_camera.tolist(),
                                       "render_calibration":episode.meta,"noise_config":ep.config.get("imu",{}),
                                       "elapsed_s":time.monotonic()-started})
                        if images != len(ep.frame_times) or not audits[-1]["imu_time_order"]:
                            raise ValueError(f"invalid archived sensors in {name}")
                        records[split].append(record)
                        write(out/"audit.json",audits)
                        manifest["datasets"]=records
                        write(out/"manifest.json",manifest)
                except RuntimeError as e:
                    log_event(f"{name} did not finish: {e}")
                    manifest.setdefault("scene_failures",[]).append({"scene":name,"error":str(e)})
        manifest["status"]="completed"
    except BaseException as e:
        manifest.update(status="failed",error=repr(e))
        raise
    finally:
        manifest["elapsed_s"]=time.monotonic()-started
        write(out/"manifest.json",manifest)


def inventory_main():
    """Audit complete raw proxy rosters and optionally the archived native pilot."""
    import sys
    import zipfile
    from collections import Counter
    from datetime import datetime, timezone
    from uuid import uuid4
    from pairs import config, digest

    out=Path("results")/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+f"-inventory-{uuid4().hex[:8]}")
    out.mkdir(parents=True)
    rows=[]
    cfg=config()
    for split,folder in (("train","train"),("development","val")):
        for path in sorted(Path(f"data/{folder}").glob("*.npz")):
            with np.load(path) as d:
                scene,tier=str(d["scene"]),str(d["tier"])
                t=d["frame_times"]
                imu=d["imu"]
                body=np.einsum("nji,nj->ni",d["gt_R"],d["gt_v"])
                angular=np.linalg.norm(d["gt_w"],axis=1)
                speed=np.linalg.norm(body,axis=1)
                accel=np.linalg.norm(np.diff(d["gt_v"],axis=0),axis=1)/.005
                with zipfile.ZipFile(path) as z, z.open("frames.npy") as file:
                    shape=np.lib.format.read_array_header_1_0(file)[0] if np.lib.format.read_magic(file)==(1,0) else None
                rows.append({"path":str(path),"sha256":digest(path),"split":split,"scene":scene,"tier":tier,
                             "duration_s":float(t[-1]-t[0]),"frames":len(t),"archive_image_shape":shape,
                             "imu_rows":len(imu),"finite_imu_rows":int(np.isfinite(imu).all(axis=1).sum()),
                             "strict_frame_time":bool(np.all(np.diff(t)>0)),"strict_imu_time":bool(np.all(np.diff(imu[:,0])>0)),
                             "speed_p10_p50_p90":np.percentile(speed,[10,50,90]).tolist(),
                             "gyro_truth_p10_p50_p90":np.percentile(angular,[10,50,90]).tolist(),
                             "forward_fraction":float(np.mean(body[:,0]>.2)),"backward_fraction":float(np.mean(body[:,0]<-.2)),
                             "sideways_fraction":float(np.mean(np.abs(body[:,1])>.2)),
                             "vertical_fraction":float(np.mean(np.abs(body[:,2])>.2)),
                             "hover_fraction":float(np.mean(speed<.15)),
                             "pure_turn_fraction":float(np.mean((speed<.15)&(angular>.25))),
                             "accelerating_or_braking_fraction":float(np.mean(accel>.5)),
                             "intrinsics":json.loads(str(d["K"])),"T_bc":d["T_body_camera"].tolist(),
                             "absolute_physical_bias_labels":False,
                             "exclusion":"non-base legacy tier retained for distribution audit" if tier!="base" else None})
    by_split={}
    for split in ("train","development"):
        group=[r for r in rows if r["split"]==split]
        by_split[split]={"scenes":sorted({x["scene"] for x in group}),"archive_count":len(group),
                         "tier_counts":dict(Counter(x["tier"] for x in group))}
    overlap=set(by_split["train"]["scenes"])&set(by_split["development"]["scenes"])
    duplicates=[key for key,count in Counter(r["sha256"] for r in rows).items() if count>1]
    report={"status":"completed","config":cfg,"config_sha256":digest("experiments.json"),
            "source_sha256":digest(__file__),"splits":by_split,"overlap":sorted(overlap),"duplicated_archive_hashes":duplicates,
            "renderer":"legacy proxy 160x120 grayscale; High shading; antialiasing and blur disabled",
            "note":"archive identity uses digests; semantically duplicated trajectories with different metadata are unverified"}
    (out/"proxy.json").write_text(json.dumps(rows,indent=2)+"\n")
    (out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    print(out,flush=True)


def native_motion(run):
    """Audit geometry and motion labels without opening any model scores."""
    from datetime import datetime, timezone
    from uuid import uuid4
    from viobench.tools.datasets.storage import read_episode
    from pairs import digest
    run=Path(run)
    src=json.loads((run/"manifest.json").read_text())
    out=Path("results")/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+f"-native-motion-{uuid4().hex[:8]}")
    out.mkdir(parents=True)
    rows=[]
    for split,parents in src["datasets"].items():
        for parent in parents:
            path=Path(parent["path"])
            if digest(path)!=parent["sha256"]:
                raise ValueError(f"archive changed: {path}")
            ep=read_episode(path)
            targets=ep.ground_truth_state()
            R=ep.T_body_camera[:3,:3]
            gyro=targets[:,10:13] @ R.T
            v=targets[:,7:10] @ R.T - np.cross(gyro,ep.T_body_camera[:3,3])
            speed=np.linalg.norm(v,axis=1)
            angular=np.linalg.norm(gyro,axis=1)
            t=ep.frame_times
            change=np.diff(speed)/np.diff(t)
            still=(speed<.15)&(t>=t[0]+2.)
            edges=np.flatnonzero(np.diff(np.r_[False,still,False].astype(int)))
            longest=max((t[b-1]-t[a] for a,b in zip(edges[::2],edges[1::2])),default=0.)
            rows.append({**parent,"split":split,"duration_s":float(ep.duration),
                         "initial_speed_m_s":float(speed[0]),"speed_p50_p95":np.percentile(speed,[50,95]).tolist(),
                         "rate_p50_p95":np.percentile(angular,[50,95]).tolist(),
                         "forward_fraction":float(np.mean(v[:,0]>.2)),
                         "backward_fraction":float(np.mean(v[:,0]<-.2)),
                         "sideways_fraction":float(np.mean(np.abs(v[:,1])>.2)),
                         "vertical_fraction":float(np.mean(np.abs(v[:,2])>.2)),
                         "accelerating_fraction":float(np.mean(change>.4)),
                         "braking_fraction":float(np.mean(change<-.4)),
                         "slow_fraction":float(np.mean(speed<.15)),
                         "turn_fraction":float(np.mean(angular>.25)),
                         "pure_turn_fraction":float(np.mean((angular>.25)&(speed<.15))),
                         "extent_xyz_m":np.ptp(targets[:,:3],axis=0).tolist(),
                         "longest_stationary_after_start_s":float(longest),"stationary_flag":bool(longest>=3.)})
    (out/"motion.json").write_text(json.dumps(rows,indent=2)+"\n")
    (out/"manifest.json").write_text(json.dumps({"status":"completed","source_sha256":digest(__file__),
         "data_run":str(run),"data_manifest_sha256":digest(run/"manifest.json"),"motion_only":True,
         "preassigned_test_flights_included":True},indent=2)+"\n")
    print(out,flush=True)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--native-joint"]:
        native_main()
    elif len(sys.argv)==3 and sys.argv[1]=="--native-motion":
        native_motion(sys.argv[2])
    elif sys.argv[1:] == ["--inventory"]:
        inventory_main()
    else:
        main()
