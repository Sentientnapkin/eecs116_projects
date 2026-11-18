"""Export an inertial-only best.safetensors run as a C header."""
import argparse
import json
from pathlib import Path

from safetensors.numpy import load_file


PARAMETERS = {
    "init_weight": "init.weight", "init_bias": "init.bias",
    "input_weight": "input.0.weight", "input_bias": "input.0.bias",
    "weight_ih": "cell.weight_ih", "bias_ih": "cell.bias_ih",
    "weight_hh": "cell.weight_hh", "bias_hh": "cell.bias_hh",
    "delta_weight": "delta.weight", "delta_bias": "delta.bias",
}


def export(model, weights, path):
    if model.get("refine_signals") != ["inertial"] or model.get("refine_iters", 0) <= 0:
        raise ValueError("C weight export requires an enabled inertial-only refiner")
    hidden, context = weights["init.weight"].shape
    lines = ["#ifndef ODOMETRY_REFINE_WEIGHTS_H", "#define ODOMETRY_REFINE_WEIGHTS_H", '#include "refine.h"', ""]
    for name, key in PARAMETERS.items():
        values = weights[key].ravel()
        lines.append(f"static const float refine_{name}[] = {{")
        for start in range(0, len(values), 8):
            lines.append("    " + ", ".join(f"{value:.9e}f" for value in values[start:start+8]) + ",")
        lines += ["};", ""]
    lines += [
        f"#define REFINE_CONTEXT_SIZE {context}",
        "static const OdometryRefineWeights odometry_refine_weights = {",
        f"    {context}, {hidden}, {model['refine_iters']},",
        *[f"    refine_{name}," for name in PARAMETERS],
        "};", "", "#endif", "",
    ]
    path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("header", type=Path)
    args = parser.parse_args()
    model = json.loads((args.run/"config.json").read_text())["model"]
    weights = {key.removeprefix("refiner."): value for key, value in load_file(args.run/"best.safetensors").items()
               if key.startswith("refiner.")}
    export(model, weights, args.header)


if __name__ == "__main__":
    main()
