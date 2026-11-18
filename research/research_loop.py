"""Unattended experiment queue for odometry training.

loop/queue.json is an append-only list of specs:
  {"name": "gru-recipe", "data": "<dir or hf:name>", "args": ["--head", "gru", "--set", "..."],
   "note": "why this experiment exists"}
The runner trains pending specs (up to --parallel at once), records each result in
loop/state.json and loop/leaderboard.md, and pushes the loop folder to the private Hub
lab repo after every finished run. Anyone (including a person or an agent) can append to
the queue while it runs. When nothing is pending for --idle-minutes, the runner queues a
new-seed replicate of the current best spec, so the GPU never sits idle and the best
result gets a variance estimate. It stops starting new runs after --until.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOOP = ROOT/"loop"
RUNS = ROOT/"results"/"loop"
LAB_REPO = "SentientNapkin/viobench-teacher-lab"


def read(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write(path, value):
    tmp = path.with_suffix(".partial")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")
    tmp.replace(path)


def summarize(run_dir):
    history = read(run_dir/"metrics.json", [])
    if not history:
        return None
    best = min(history, key=lambda h: h["selection_score"])
    manifest = read(run_dir/"manifest.json", {})
    return {"best_epoch": best["epoch"], "epochs_run": len(history),
            "selection_score": round(best["selection_score"], 4),
            "nominal_ate": round(best["nominal_ate"], 4), "moving_ate": round(best["moving_ate"], 4),
            "sim3_ate": round(best.get("sim3_ate", float("nan")), 4) if "sim3_ate" in best else None,
            "final_loss": round(history[-1]["loss"], 4), "parameters": manifest.get("parameters")}


def leaderboard(state):
    done = [(n, s) for n, s in state.items() if s.get("result")]
    done.sort(key=lambda item: item[1]["result"]["selection_score"])
    lines = ["# Odometry leaderboard", "",
             "Selection score = mean of nominal and moving-start unaligned ATE on the fixed",
             "development set (lower is better). Sim(3) ATE is the course-scorer alignment.", "",
             "| Rank | Run | Score (m) | Nominal (m) | Moving (m) | Sim(3) (m) | Best epoch | Params | Note |",
             "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for rank, (name, s) in enumerate(done, 1):
        r = s["result"]
        lines.append(f"| {rank} | {name} | {r['selection_score']:.3f} | {r['nominal_ate']:.3f} | "
                     f"{r['moving_ate']:.3f} | {r['sim3_ate'] if r['sim3_ate'] is not None else '–'} | "
                     f"{r['best_epoch']}/{r['epochs_run']} | {r['parameters'] or '–'} | {s.get('note', '')} |")
    failed = [n for n, s in state.items() if s.get("status") == "failed"]
    if failed:
        lines += ["", "Failed: " + ", ".join(failed)]
    (LOOP/"leaderboard.md").write_text("\n".join(lines)+"\n")


def push_loop():
    try:
        from huggingface_hub import HfApi
        HfApi().upload_folder(repo_id=LAB_REPO, folder_path=str(LOOP), path_in_repo="loop",
                              allow_patterns=["*.json", "*.md"], commit_message="Loop status")
    except Exception as error:  # the Hub is a mirror; never stop training for it
        print("hub push failed:", repr(error), flush=True)


def command(spec, run_dir, resume=None):
    cmd = [str(ROOT/"odometry_env.sh"), "odometry_train.py", "--data", spec["data"],
           "--output", str(run_dir), "--hub-repo", LAB_REPO, *spec.get("args", [])]
    if resume:
        cmd += ["--resume", str(resume)]
    return cmd


def latest_checkpoint(run_dir):
    done = sorted(p.parent for p in run_dir.glob("checkpoints/epoch-*/complete.json"))
    return done[-1] if done else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--until", default="08:30", help="Local HH:MM after which no run starts")
    parser.add_argument("--idle-minutes", type=float, default=15)
    args = parser.parse_args()
    LOOP.mkdir(exist_ok=True); RUNS.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    hour, minute = map(int, args.until.split(":"))
    deadline = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if deadline <= now:
        deadline += timedelta(days=1)
    print(f"loop started {now:%H:%M}, no new runs after {deadline:%Y-%m-%d %H:%M}", flush=True)
    active, idle_since = {}, time.time()
    while True:
        state = read(LOOP/"state.json", {})
        queue = read(LOOP/"queue.json", [])
        for spec in queue:
            state.setdefault(spec["name"], {"status": "pending", "note": spec.get("note", "")})
        # Reap finished processes.
        for name, (proc, log, started) in list(active.items()):
            if proc.poll() is None:
                continue
            log.close(); del active[name]
            run_dir = RUNS/name
            entry = state[name]
            entry["minutes"] = round((time.time()-started)/60 + entry.get("minutes", 0), 1)
            entry["result"] = summarize(run_dir)
            if proc.returncode == 0:
                entry["status"] = "done"
            elif entry.get("retries", 0) < 1 and latest_checkpoint(run_dir):
                entry.update(status="pending", retries=entry.get("retries", 0)+1)
            else:
                entry["status"] = "failed"
            print(f"{datetime.now():%H:%M} finished {name}: {entry['status']} {entry['result']}", flush=True)
            write(LOOP/"state.json", state); leaderboard(state); push_loop()
        pending = [s for s in queue if state[s["name"]]["status"] == "pending"]
        if pending or active:
            idle_since = time.time()
        if datetime.now() >= deadline:
            if not active:
                print("deadline reached; exiting", flush=True)
                write(LOOP/"state.json", state); leaderboard(state); push_loop()
                return
        else:
            while pending and len(active) < args.parallel:
                spec = pending.pop(0)
                run_dir = RUNS/spec["name"]
                resume = latest_checkpoint(run_dir) if run_dir.exists() else None
                if run_dir.exists() and not resume:
                    run_dir.rename(run_dir.with_name(run_dir.name+f"-abandoned-{int(time.time())}"))
                log = open(RUNS/f"{spec['name']}.log", "a")
                proc = subprocess.Popen(command(spec, run_dir, resume), stdout=log, stderr=subprocess.STDOUT,
                                        cwd=ROOT)
                active[spec["name"]] = (proc, log, time.time())
                state[spec["name"]]["status"] = "running"
                print(f"{datetime.now():%H:%M} started {spec['name']}" + (f" (resume {resume.name})" if resume else ""),
                      flush=True)
            if not pending and len(active) < args.parallel and time.time()-idle_since > args.idle_minutes*60:
                scored = [(s["result"]["selection_score"], n) for n, s in state.items() if s.get("result")]
                if scored:
                    best = min(scored)[1]
                    spec = next(s for s in queue if s["name"] == best)
                    base = spec.get("replicate_of", spec["name"])
                    seed = 1 + sum(1 for s in queue if s.get("replicate_of") == base)
                    clone = dict(spec, name=f"{base}-seed{seed}", replicate_of=base,
                                 args=[*spec.get("args", []), "--seed", str(217+seed)],
                                 note=f"auto replicate of {base}")
                    queue.append(clone); write(LOOP/"queue.json", queue)
                    print(f"{datetime.now():%H:%M} idle; queued {clone['name']}", flush=True)
                idle_since = time.time()
        write(LOOP/"state.json", state)
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
