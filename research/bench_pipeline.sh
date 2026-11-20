#!/bin/bash
# Self-driving server-benchmark pipeline. Idempotent: every stage skips finished work, so rerunning resumes.
#
#   setsid nohup bash bench_pipeline.sh > /data/backups/rganapa/Sebastian/baselines/bench-pipeline/pipeline.log 2>&1 < /dev/null &
#
# Stages: (1) finish flight generation  (2) score every guest on every flight, all cores  (3) calibrate
# (4) failure-mode analysis  (5) package + upload a PRIVATE Hugging Face dataset  (6) commit small result files to the
# current branch (no push)  (7) watch the queue folder for HOURS hours: any new .wasm dropped there is scored on the
# whole pool and the reports and the dataset are refreshed.
# Progress: <LOG>/STATUS. Nothing here pushes to GitHub, makes anything public, or submits to the course server.
set -u
R=/data/backups/rganapa/Sebastian
RES=$R/eecs116_projects/research
B=$R/baselines
OUT=$B/bench-fast/selected; FULL=$B/bench-fast/full; RAW=$R/gen/raw-fast; Q=$B/queue; LOG=$B/bench-pipeline
EVAL=$RES/results/eval/server-benchmark
PY=$R/venv-viobench-9b1b079/bin/python; TPY=$R/venv-teacher/bin/python
HOURS=${HOURS:-4}; DEADLINE=$(( $(date +%s) + HOURS*3600 )); WORKERS=${WORKERS:-180}; SELECT=${SELECT:-300}
mkdir -p "$Q" "$LOG" "$EVAL" "$OUT" "$FULL"
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG/STATUS"; }
cd "$RES" || exit 1
export HF_HOME=$R/hf TMPDIR=$R/tmp

missing() {  # number of pool flights not yet generated
  "$TPY" - <<'EOF'
import json, os
n = 0
for name in ("server_fast_pool", "server_fast_mid_pool"):
    p = f"configs/{name}.json"
    if os.path.exists(p):
        n += sum(not os.path.exists(f"/data/backups/rganapa/Sebastian/gen/raw-fast/bench/{f['id']}.zip") for f in json.load(open(p))["flights"])
print(n)
EOF
}

guest_args() {
  local args=()
  add() { [ -f "$2" ] && args+=(--guest "$1=$2"); }
  add dead_reckoning "$B/dead-reckoning-9b1b079/dead_reckoning.wasm"
  add vins_mono "$B/vins-mono-9b1b079/vins_mono.wasm"
  add openvins "$B/openvins-9b1b079/openvins.wasm"
  add b_d0 "$B/b-d0-s217-submitted.wasm"
  add n2_kfgrid "$B/candidates/n2-218-ungated/odometry.wasm"
  add n2_kfinputs_s217 "$RES/artifacts/n2-kfinputs-frozen/package/vio_n2_kfinputs_s217.wasm"
  add bd0_kfgrid "$B/candidates/bd0-217-kfgrid/odometry.wasm"
  add bd0_velfusion "$B/candidates/bd0-217-velfusion/odometry.wasm"
  for f in "$Q"/*.wasm; do [ -f "$f" ] && add "q_$(basename "$f" .wasm)" "$f"; done
  printf '%s\0' "${args[@]}"
}

select_flights() {  # draw the benchmark flights from truth statistics alone (no guest result is involved), link them into $RAW/selected
  "$TPY" server_benchmark.py calibrate --raw "$RAW" --select "$SELECT" --output "$EVAL/selection.json" > "$EVAL/selection.txt" 2>&1
  "$TPY" - <<EOF2
import json, os, shutil
sel = json.load(open("$EVAL/selection.json"))["selected"]
os.makedirs("$RAW/selected", exist_ok=True)
for n in sel:
    dst = f"$RAW/selected/{n}.zip"
    if not os.path.exists(dst):
        try: os.link(f"$RAW/bench/{n}.zip", dst)
        except OSError: shutil.copy2(f"$RAW/bench/{n}.zip", dst)
print(len(sel), "selected flights linked")
EOF2
  say "selected $SELECT flights (calibration weights from extent + path length only)"
}

score_all() {
  mapfile -d '' ARGS < <(guest_args)
  say "scoring ${#ARGS[@]} args (guests x2) on the $SELECT selected flights, $WORKERS workers"
  "$PY" bench_eval.py "${ARGS[@]}" --episodes "$RAW/selected" --out "$OUT" --workers "$WORKERS" >> "$LOG/bench_eval.log" 2>&1
  tail -n 14 "$LOG/bench_eval.log" | grep -E 'mean|total' | tee -a "$LOG/STATUS"
}

score_full() {  # reference guests on the whole pool (cheap ones only): whole-pool failure statistics
  say "scoring reference guests on the whole pool"
  "$PY" bench_eval.py --guest dead_reckoning="$B/dead-reckoning-9b1b079/dead_reckoning.wasm" --guest b_d0="$B/b-d0-s217-submitted.wasm" \
     --episodes "$RAW/bench" --out "$FULL" --workers "$WORKERS" >> "$LOG/bench_eval_full.log" 2>&1
  tail -n 6 "$LOG/bench_eval_full.log" | grep -E 'mean|total' | tee -a "$LOG/STATUS"
}

analyse() {
  "$TPY" server_benchmark.py calibrate --raw "$RAW" --selection "$EVAL/selection.json" --matrix "$OUT/matrix.json" --output "$EVAL/calibration.json" > "$EVAL/calibration.txt" 2>&1
  "$TPY" failure_analysis.py --raw "$RAW" --scores "$FULL" --output "$EVAL/failure-pool.json" > "$EVAL/failure-pool.txt" 2>&1
  "$TPY" failure_analysis.py --raw "$RAW" --scores "$OUT" --only "$EVAL/calibration.json" --output "$EVAL/failure-selected.json" > "$EVAL/failure-selected.txt" 2>&1
  { echo "# Server-calibrated benchmark: automatic summary ($(date -u +%FT%TZ))"; echo; echo '## Calibration'; echo '```'; cat "$EVAL/selection.txt" "$EVAL/calibration.txt"; echo '```'
    echo; echo '## Failure modes, whole pool (reference guests)'; echo '```'; cat "$EVAL/failure-pool.txt"; echo '```'
    echo; echo '## Failure modes, calibrated selection (all guests)'; echo '```'; cat "$EVAL/failure-selected.txt"; echo '```'; } > "$EVAL/SUMMARY.md"
  say "analysis written: $EVAL/SUMMARY.md"
}

release() {
  for attempt in 1 2; do
    "$TPY" release_benchmark.py --raw "$RAW" --calibration "$EVAL/calibration.json" --scores "$OUT" --stage "$B/bench-release" >> "$LOG/release.log" 2>&1 && { say "released (private HF dataset)"; return; }
    say "release attempt $attempt failed; see $LOG/release.log"
  done
}

commit_results() {
  cd "$R/eecs116_projects" || return
  git add research/server_benchmark.py research/bench_eval.py research/failure_analysis.py research/release_benchmark.py \
          research/native_campaign.py research/bench_pipeline.sh research/configs/server_benchmark_pool.json \
          research/configs/server_benchmark_pool_r2.json research/configs/server_fast_pool.json research/configs/server_fast_mid_pool.json research/configs/server_observed.json research/results/eval/server-benchmark 2>/dev/null
  if ! git diff --cached --quiet; then
    git -c user.name=SentientNapkin -c user.email=sebastian.vargas.reiners@gmail.com commit -q -m "Server-calibrated benchmark: pool, calibration, failure analysis (automatic)" && say "committed results (not pushed)"
  fi
  cd "$RES" || true
}

# 0. let any scoring pass that is already running finish (results are cached, so no work is repeated)
while pgrep -f '^[^ ]*python[^ ]* bench_eval[.]py' > /dev/null; do sleep 20; done

# 1. generation
for attempt in 1 2 3; do
  m=$(missing); [ "$m" = 0 ] && break
  say "generation: $m flights missing, attempt $attempt"
  N=48 ROSTER=configs/server_fast_pool.json TAG=pipe$attempt RAWDIR=$RAW $R/gen/run_speed.sh
  N=48 ROSTER=configs/server_fast_mid_pool.json TAG=pipem$attempt RAWDIR=$RAW $R/gen/run_speed.sh
  sleep 60; while pgrep -f '^[^ ]*python[^ ]* native_campaign[.]py generate' > /dev/null; do sleep 30; done
done
say "generation done: $(missing) missing of the roster"

# 2-6 first pass: select first (truth statistics only), then score
select_flights; score_all; score_full; analyse; commit_results; say "SCORING AND ANALYSIS DONE (upload not started)"

# 7. watch loop
seen="$LOG/seen.txt"; touch "$seen"
say "watching $Q for new .wasm guests until $(date -u -d @$DEADLINE +%FT%TZ)"
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  sleep 300
  new=0
  for f in "$Q"/*.wasm; do
    [ -f "$f" ] || continue
    sha=$(sha256sum "$f" | cut -d' ' -f1)
    grep -q "$sha" "$seen" || { echo "$sha $(basename "$f")" >> "$seen"; new=1; say "new guest in queue: $(basename "$f")"; }
  done
  [ "$new" = 1 ] && { score_all; analyse; commit_results; }
done
say "pipeline finished its $HOURS h budget"
