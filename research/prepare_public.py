"""Prepare the ten public VIOBench flights (pinned revision eecdfdf) with the training preprocessing, for PyTorch replay.

    python prepare_public.py <dir with sim-ProcTHOR-Train-1-000N/*.zip> data/public-prepared
Writes shards plus records.json for `odometry_eval.py --set records --records ... --shards ...`. Crop 0 only (the
public set is scored from each recording's first frame).
"""
import json
import sys
from pathlib import Path

from odometry_pool import prepare

source, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parent
base = json.loads((root/"configs/odometry.json").read_text())
sensor = json.loads((root/"configs/sensor.json").read_text())
sensor.update(width=base["model"]["width"], height=base["model"]["height"], portable_pixels="remap", ordered_packet=True)
records = []
for archive in sorted(source.glob("sim-*/sim-*.zip")):
    rows, _ = prepare(archive, {"scene": "ProcTHOR-Train-1", "domain": "public", "tier": "public"}, sensor, [0],
                      base["seed"], out, gate_flights=False)
    for r in rows:
        r.update(parent_file=archive.name, catalog="public")
    records += rows
    print(archive.name, len(rows), flush=True)
(out/"records.json").write_text(json.dumps({"records": records, "source": "conta-shards/viobench-public@eecdfdf"}, indent=1))
