"""Causal attitude controls and one privileged fixed-bias diagnostic."""
import argparse
import glob

import numpy as np

from common import Flight
from learned_probe import open_run, read_inputs, score, write
from pairs import config, digest


def full_flight_bias(f):
    """Effective mean gyro-minus-truth-rate across this complete flight."""
    rate = np.column_stack([np.interp(f.imu[:, 0], f.ft, axis) for axis in f.w.T])
    return (f.imu[:, 4:7]-rate).mean(0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pattern")
    args = parser.parse_args()
    parents = [{"path":p,"sha256":digest(p)} for p in sorted(glob.glob(args.pattern))]
    if not parents:
        parser.error("no matching flights")
    cfg = config()
    directory, manifest = open_run("heading", cfg, {"development": parents})
    try:
        rows = []
        for crop in (0.,5.):
            for policy in ("none","startup","evidence"):
                for data in read_inputs(parents,{**cfg,"policy":policy},crop):
                    rows.append({"policy":policy, **score(data,data["v"])})
                    if policy=="none":
                        flight = Flight(data["path"],crop)
                        R = flight.gyro_attitude(full_flight_bias(flight))
                        rows.append({"policy":"privileged_full_flight_effective_bias", **score(data,data["v"],R)})
        write(directory/"scores.json",rows)
        manifest["status"]="completed"
        print(directory)
    except BaseException as error:
        manifest.update(status="failed",error=repr(error))
        raise
    finally:
        write(directory/"manifest.json",manifest)


if __name__=="__main__":
    main()
