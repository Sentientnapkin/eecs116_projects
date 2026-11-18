"""Render prospective holdout episodes or a small independent-yaw pilot."""
import argparse
import json
import re
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import numpy as np

from pairs import digest
from viobench.tools.datasets.generate.simulation import SimConfig, scene_references, simulate
from viobench.tools.datasets.storage import write_episode


class IndependentYaw(SimConfig):
    """Reuse the physics, camera, route planner and controller with alternate yaw targets."""

    def render_header(self, imu_rate_hz):
        import hyperlux
        base = super().render_header(imu_rate_hz)
        headers = Path(hyperlux.__file__).parent/(
            "_vendor/rl-tools/include/rl_tools/rl/environments/hyperdrone/tasks/visual_inertial_localization")
        tracking = headers/"tracking_operations_cpu.h"
        text = tracking.read_text()
        desired = "const T desired_yaw = math::atan2(device.math, forward[1], forward[0]);"
        pace = "pace *= alignment * alignment;"
        if text.count(desired) != 1 or text.count(pace) != 1:
            raise ValueError("unexpected upstream tracking header")
        text = text.replace(desired, """const T route_yaw = math::atan2(device.math,
                        instance_parameters.waypoints[1][1] - instance_parameters.waypoints[0][1],
                        instance_parameters.waypoints[1][0] - instance_parameters.waypoints[0][0]);
                    const T elapsed = (T)world.task_step * dt;
                    const T desired_yaw = route_yaw + (T)3.14159265359 + (T)0.65 * math::sin(device.math, (T)0.55 * elapsed);""")
        text = text.replace(pace, "(void)alignment; // position tracking still constrains pace")
        # Include the replacement first so the upstream include guard suppresses the original.
        text = re.sub(r'#include "([^"]+)"',
                      lambda match: f'#include "{(headers/match[1]).resolve()}"', text)
        original = "#include <rl_tools/rl/environments/hyperdrone/tasks/visual_inertial_localization/operations_cpu.h>"
        if base.read_text().count(original) != 1:
            raise ValueError("unexpected upstream simulator spec")
        spec = base.read_text().replace(original, text+"\n"+original)
        output = base.parent/f"independent-yaw-{sha256(spec.encode()).hexdigest()[:12]}.h"
        if not output.exists():
            output.write_text(spec)
        return output


def write(path, value):
    temp = path.with_suffix(".partial")
    temp.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")
    temp.replace(path)


def motion_audit(episode):
    truth = episode.ground_truth_state()
    R, arm = episode.T_body_camera[:3,:3], episode.T_body_camera[:3,3]
    w = truth[:,10:13] @ R.T
    v = truth[:,7:10] @ R.T - np.cross(w,arm)
    return {"frames":len(v),"duration_s":float(episode.duration),
            "body_velocity_p10_p50_p90_m_s":np.percentile(v,[10,50,90],axis=0).tolist(),
            "backward_fraction":float(np.mean(v[:,0]<-.2)),
            "lateral_fraction":float(np.mean(np.abs(v[:,1])>.2)),
            "yaw_rate_p10_p50_p90_rad_s":np.percentile(w[:,2],[10,50,90]).tolist(),
            "initial_speed_m_s":float(np.linalg.norm(v[0]))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("confirmation","yaw-pilot"))
    args = parser.parse_args()
    settings = json.loads(Path("robustness.json").read_text())
    confirmation = args.phase=="confirmation"
    plan = settings["simulation"][args.phase]
    references = scene_references([f"ProcTHOR-Train-{r['scene']}" for r in plan])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = Path("results")/f"{stamp}-robust-{args.phase}-{uuid4().hex[:8]}"
    directory.mkdir()
    data = Path("data")/directory.name
    data.mkdir()
    free = shutil.disk_usage(".").free
    manifest = {"status":"running","config":settings,"plan":plan,"disk_free_before":free,
                "simulator_source":digest(__file__),"datasets":{},"attempts":[]}
    print(directory,flush=True)
    write(directory/"manifest.json",manifest)
    try:
        if free<settings["simulation"]["required_free_bytes"]:
            raise OSError("insufficient disk for simulator spool and completed archives")
        klass = SimConfig if confirmation else IndependentYaw
        for item in plan:
            scene = f"ProcTHOR-Train-{item['scene']}"
            split = item["split"]
            options = klass(instances=1, duration_seconds=item["seconds"], waypoints=24, spool=str(data.resolve()))
            seed = 69500 + item["scene"]
            attempt = {"scene":scene,"seed":seed,"simulator":asdict(options),
                       "spec_sha256":digest(options.render_header(200.))}
            manifest["attempts"].append(attempt)
            try:
                episode, = simulate(options,{scene:references[scene]},1,seed=seed,
                                    name="holdout" if confirmation else "yaw-pilot",log=lambda msg: print(msg,flush=True))
                episode.check_consistency()
                target = data/(episode.name+".zip")
                write_episode(episode,target)
                record = {"scene":scene,"path":str(target),"sha256":digest(target),"seed":seed,
                          "domain":"benchmark","regime":item["regime"],**motion_audit(episode)}
                manifest["datasets"].setdefault(split,[]).append(record)
                attempt["status"] = "completed"
                print(scene, record["backward_fraction"],record["lateral_fraction"],flush=True)
            except Exception as error:
                attempt.update(status="failed",error=repr(error))
                print(scene,repr(error),flush=True)
            write(directory/"manifest.json",manifest)
        manifest["status"] = "completed" if all(r["status"]=="completed" for r in manifest["attempts"]) else "incomplete"
    except BaseException as error:
        manifest.update(status="failed",error=repr(error))
        raise
    finally:
        manifest["disk_free_after"] = shutil.disk_usage(".").free
        write(directory/"manifest.json",manifest)


if __name__=="__main__":
    main()
