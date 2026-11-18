"""Apply the recorded development rule and freeze deployment representatives."""
import json
from pathlib import Path

import numpy as np

from learned_probe import open_run, write
from pairs import digest


def read_records(run):
    manifest = json.loads((run/"manifest.json").read_text())
    if manifest["status"] != "completed":
        raise ValueError(f"incomplete training {run}")
    return json.loads((run/"scores.json").read_text()), manifest


def choose(records, policy):
    candidates = []
    for name in ("ssm-expanded","ssm-reliability","ssm-zero-initial"):
        group = [r for r in records if r["model"]==name]
        if sorted(r["seed"] for r in group)!=policy["train_seeds"]:
            raise ValueError(f"missing or duplicate screening seeds for {name}")
        nominal = np.mean([r["selected"]["nominal_ate"] for r in group])
        nominal_delta = np.mean([r["selected"]["nominal_ate"]-r["baseline"]["nominal_ate"] for r in group])
        stress = np.mean([r["selected"]["stress_ate"] for r in group])
        stress_delta = np.mean([r["selected"]["stress_ate"]-r["baseline"]["stress_ate"] for r in group])
        qualifies = nominal_delta<=policy["nominal_ate_allowance_m"] and stress_delta<=-policy["min_stress_improvement_m"]
        candidates.append({"model":name,"nominal_ate":float(nominal),"nominal_delta":float(nominal_delta),
                           "stress_ate":float(stress),"stress_delta":float(stress_delta),"qualifies":bool(qualifies)})
    qualified = [r for r in candidates if r["qualifies"]]
    selection = min(qualified,key=lambda r:r["stress_ate"]) if qualified else min(
        candidates,key=lambda r:(r["nominal_delta"],r["stress_ate"]))
    return selection, candidates


def select(args, settings):
    screen, manifest = read_records(args.screen)
    selected, summary = choose(screen,settings["training"])
    if not args.followup:
        print(json.dumps({"selected":selected,"candidates":summary},indent=2))
        return
    followup = []
    for run in args.followup:
        records, followup_manifest = read_records(run)
        if followup_manifest["datasets"]!=manifest["datasets"]:
            raise ValueError("training rosters differ")
        followup.extend(records)
    seed = settings["training"]["confirmation_seed"]
    names = selected["model"], "ema-expanded"
    if sorted((r["model"],r["seed"]) for r in followup)!=sorted((name,seed) for name in names):
        raise ValueError("followup models do not match the screen selection")
    representatives = {}
    results = {}
    for name in names:
        group = [r for r in screen+followup if r["model"]==name]
        if sorted(r["seed"] for r in group)!=[0,1,2]:
            raise ValueError(f"incomplete finalist seeds: {name}")
        ranked = sorted(group,key=lambda r:r["selected"]["nominal_ate"])
        rep = ranked[1]
        for row in group:
            if digest(row["checkpoint"])!=row["sha256"]:
                raise ValueError("checkpoint changed")
        representatives[name] = {key:rep[key] for key in ("seed","checkpoint","sha256")}
        results[name] = [{"seed":r["seed"],"selected":r["selected"],"baseline":r["baseline"]} for r in group]
    directory, freeze = open_run("robust-freeze", settings, manifest["datasets"])
    freeze.update(status="completed",screen_selection=selected,screen_candidates=summary,
                  training_inputs=[{"path":str(run),"manifest_sha256":digest(run/"manifest.json")}
                                   for run in [args.screen,*args.followup]],
                  representatives=representatives,finalist_development=results,
                  representative_rule="median seed by nominal ATE",deployment_preprocessing="fixed-point remap",
                  confirmation_scenes_preassigned=settings["simulation"]["confirmation"])
    write(directory/"manifest.json",freeze)
    print(directory/"manifest.json",flush=True)
