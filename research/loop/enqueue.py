"""Append specs to loop/queue.json atomically: python loop/enqueue.py '<json spec or list>'"""
import json, sys
from pathlib import Path
path = Path(__file__).with_name("queue.json")
queue = json.loads(path.read_text())
new = json.loads(sys.argv[1]); new = new if isinstance(new, list) else [new]
names = {q["name"] for q in queue}
base = {"data": "hf:teacher-full", "args": []}
recipe = ["--group-size","16","--cache-gb","20","--epochs","12","--set","training.weight_ema=0.995",
          "--set",'training.schedule="cosine"',"--set","training.warmup_epochs=0.5","--set","training.patience=5"]
for spec in new:
    assert spec["name"] not in names, spec["name"]
    spec = {**base, **spec}
    if spec.pop("recipe", True): spec["args"] = recipe + spec["args"]
    queue.append(spec); names.add(spec["name"])
tmp = path.with_suffix(".partial"); tmp.write_text(json.dumps(queue, indent=1)); tmp.replace(path)
print([q["name"] for q in queue])
