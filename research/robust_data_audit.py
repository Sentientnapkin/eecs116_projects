"""Record independent-scene motion and the actual deterministic training-window mix."""
import json

import numpy as np

from common import Flight
from learned_probe import open_run, write
from pairs import digest
from robust_train import VARIANTS, select_segment


def summarize_motion(v, w):
    return {"speed_p10_p50_p90_m_s":np.percentile(np.linalg.norm(v,axis=1),[10,50,90]).tolist(),
            "forward_fraction":float(np.mean(v[:,0]>.2)), "backward_fraction":float(np.mean(v[:,0]<-.2)),
            "lateral_fraction":float(np.mean(np.abs(v[:,1])>.2)),
            "yawing_fraction":float(np.mean(np.abs(w[:,2])>.25))}


def audit(args):
    runs = [json.loads((p/"manifest.json").read_text()) for p in args.training]
    roster = runs[0]["datasets"]
    if any(run["datasets"]!=roster for run in runs):
        raise ValueError("training rosters differ")
    directory, manifest = open_run("robust-data-audit",{},roster)
    print(directory,flush=True)
    train = []
    rows = []
    for split, parents in roster.items():
        for parent in parents:
            if digest(parent["path"])!=parent["sha256"]:
                raise ValueError("parent archive changed")
            flight = Flight(parent["path"])
            rows.append({**parent,"split":split,"duration_s":float(flight.ft[-1]),"frames":len(flight.ft),
                         **summarize_motion(flight.v_body,flight.w)})
            if split=="train":
                # The audit needs only the labels and timing. Replace image payloads with placeholders.
                flight.frames = np.empty((len(flight.ft),0),dtype=np.uint8)
                train.append(flight)
    write(directory/"parent-motion.json",rows)
    variants = []
    for path, run in zip(args.training,runs):
        options = run["config"]["training"]
        for record in json.loads((path/"scores.json").read_text()):
            name, seed = record["model"], record["seed"]
            expanded = VARIANTS[name][1]
            for epoch in record["history"]:
                rng = np.random.default_rng([seed,epoch["epoch"]])
                for i in rng.permutation(len(train)):
                    segment, condition, sensor_seed = select_segment(train[i],rng,expanded,options)
                    variants.append({"model":name,"seed":seed,"epoch":epoch["epoch"],"scene":segment.scene,
                                     "parent":segment.path,"condition":condition,"sensor_seed":sensor_seed,
                                     "frames":len(segment.ft),"duration_s":float(segment.ft[-1]),
                                     "crop_s":segment.realized_crop,"speed_at_reset_m_s":float(np.linalg.norm(segment.v[0])),
                                     "yaw_at_reset_rad_s":float(segment.w[0,2]),
                                     **summarize_motion(segment.v_body,segment.w)})
    with (directory/"train-windows.jsonl").open("w") as stream:
        for row in variants:
            stream.write(json.dumps(row,allow_nan=False)+"\n")
    manifest["status"] = "completed"
    write(directory/"manifest.json",manifest)
