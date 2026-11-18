"""Turn the growing generated pool into data-scaling experiments without supervision.

Every few minutes: when the pool has passed the next threshold of accepted shards, freeze
an immutable Hub snapshot (base teacher-full + every pool shard so far, same fixed
development set) and queue the current best spec on it, ahead of other pending work.
"""
import json
import time
from pathlib import Path

from teacher_store import snapshot

ROOT = Path(__file__).resolve().parent
LOOP = ROOT/"loop"
POOL = ROOT/"data/gen-spool/gen-pool-v1.json"
THRESHOLDS = [(100, "teacher-v2"), (200, "teacher-v3"), (280, "teacher-v4")]


def read(path, default):
    try: return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError): return default


def best_spec(queue, state):
    done = [(s["result"]["selection_score"], n) for n, s in state.items()
            if s.get("result") and not n.startswith("data-")]
    name = min(done)[1] if done else "gru-recipe"
    spec = next(q for q in queue if q["name"] == name)
    return spec.get("replicate_of", name), spec


def main():
    while True:
        pool = read(POOL, {"datasets": {"train": []}})
        count = len(pool["datasets"]["train"])
        queue, state = read(LOOP/"queue.json", []), read(LOOP/"state.json", {})
        names = {q["name"] for q in queue}
        for threshold, snap in THRESHOLDS:
            if count < threshold or any(n.startswith(f"data-{snap}") for n in names):
                continue
            manifest = snapshot(snap, "teacher-full", ["gen-pool-v1"])
            base_name, spec = best_spec(queue, state)
            args = list(spec["args"])
            # More data per epoch: keep total compute similar with fewer epochs and a
            # larger cache so parallel runs never evict each other's shards.
            for i, a in enumerate(args):
                if a == "--cache-gb": args[i+1] = "20"
                if a == "--epochs": args[i+1] = "10"
            new = {"name": f"data-{snap}-{base_name}", "data": f"hf:{snap}", "args": args,
                   "note": f"{base_name} config on {snap}: "
                           f"{len(manifest['datasets']['train'])} train shards (+{count} generated)"}
            # Insert ahead of every pending spec.
            first_pending = next((i for i, q in enumerate(queue)
                                  if state.get(q["name"], {}).get("status", "pending") == "pending"), len(queue))
            queue.insert(first_pending, new)
            tmp = (LOOP/"queue.json").with_suffix(".partial")
            tmp.write_text(json.dumps(queue, indent=1)); tmp.replace(LOOP/"queue.json")
            print(time.strftime("%H:%M"), "queued", new["name"], new["note"], flush=True)
            break
        if count >= THRESHOLDS[-1][0] and all(any(n.startswith(f"data-{s}") for n in names) for _, s in THRESHOLDS):
            return
        time.sleep(300)


if __name__ == "__main__":
    main()
