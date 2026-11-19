"""Apply the frozen visual-motion screen gates to two independent replay files."""
import argparse
import json
from pathlib import Path

import numpy as np

from teacher_eval import scene_paired


def compare(control, candidate):
    def roster(rows):
        return {(r["scene"], r["parent_sha256"], r["crop_s"], r["file"], r["regime"])
                for r in rows}

    if len(roster(control)) != len(control) or roster(control) != roster(candidate) or len(control) != len(candidate):
        raise ValueError("Candidate and control must replay the same unique source shards")

    def scores(rows):
        def mean(key, records):
            return float(np.mean([row[key] for row in records]))

        ordinary = [row for row in rows if row["regime"] == "ordinary"]
        stress = [row for row in rows if row["regime"] != "ordinary"]
        return {
            "unaligned_ate": mean("ate", rows), "ordinary_ate": mean("ate", ordinary),
            "stress_ate": mean("ate", stress) if stress else None,
            "sim3_ate": mean("sim3_ate", rows), "worst_ate": max(row["ate"] for row in rows),
            "speed_rmse": mean("speed_rmse", rows),
            "speed_bias": mean("speed_bias", rows),
            "direction_error_deg": mean("direction_error_deg", rows),
            "parents": len({row["parent_sha256"] for row in rows}),
            "scenes": len({row["scene"] for row in rows}),
        }

    baseline, new = scores(control), scores(candidate)
    relative = new["unaligned_ate"]/baseline["unaligned_ate"]-1
    ordinary_relative = new["ordinary_ate"]/baseline["ordinary_ate"]-1
    paired = scene_paired({"control": control, "candidate": candidate}, "candidate", "control")
    differences = paired["per_scene"]
    return {
        "control": baseline, "candidate": new, "relative_ate": relative,
        "relative_ordinary_ate": ordinary_relative,
        "passes_screen": relative <= -.10 and ordinary_relative <= .05,
        "paired_scene_ate": paired,
        "leave_one_scene_out": {scene: float(np.mean([v for s, v in differences.items() if s != scene]))
                                for scene in differences} if len(differences) > 1 else {},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--control-model", required=True)
    parser.add_argument("--candidate-model", required=True)
    args = parser.parse_args()
    control = json.loads(args.control.read_text())["rows"][args.control_model]
    candidate = json.loads(args.candidate.read_text())["rows"][args.candidate_model]
    print(json.dumps(compare(control, candidate), indent=2))


if __name__ == "__main__":
    main()
