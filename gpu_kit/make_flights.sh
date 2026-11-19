#!/bin/bash
# Render every flight in jobs_gpu.txt into ~/flights_gpu/<group>/ (one simulate call per scene; finished scenes are
# skipped, so re-running resumes).
#   bash make_flights.sh
KIT=$(cd "$(dirname "$0")" && pwd)
REPO=$(cat "$KIT/.repo_path" 2>/dev/null) || { echo "run setup.sh first"; exit 1; }
. "$REPO/.venv/bin/activate"
cd "$HOME"
mkdir -p flights_gpu/logs

style() {
  local n=$1


  grep -v '^#' "$KIT/styles.txt" | awk -F'|' -v n="$n" '{gsub(/ /, "", $1)} $1 == n {print $2}'
}

seed=7000
grep -v '^#' "$KIT/jobs_gpu.txt" | grep . | while IFS='|' read -r group st eps extra scenes; do
  group=$(echo $group)
  eps=$(echo $eps)
  x=$(style $(echo $st))
  [ -n "$x" ] || { echo "unknown style $st"; continue; }
  for scene in $scenes; do
    seed=$((seed + 1))
    out=flights_gpu/$group
    ls $out/sim-$scene-*.zip >/dev/null 2>&1 && continue
    start=$(date +%s)
    VIOBENCH_TASK_EXTRA="$x" viobench simulate -o $out --episodes $eps --seed $seed --duration 60 --no-video $extra \
      --scene-names $scene > flights_gpu/logs/$group-$scene.log 2>&1
    echo "$(date +%H:%M) $group $scene exit=$? $(( $(date +%s) - start )) s" | tee -a flights_gpu/logs/progress.txt
  done
done

echo
echo "speed check (hidden flights: 0.66-1.34 m/s average per flight, rms distance from start ~4.7 m):"
for d in flights_gpu/*/; do
  case $(basename $d) in logs|calib|_test) continue;; esac
  python "$KIT/flight_stats.py" $d 2>/dev/null | grep '^STAT' | awk -v n=$(basename $d) -F'\t' \
    '{k++; v+=$4; r+=$5} END {if (k) printf "  %-12s %3d flights  %4.2f m/s  rms from start %4.2f m\n", n, k, v/k, r/k}'
done
echo "done: $(du -sh flights_gpu | cut -f1). Copy ~/flights_gpu to the laptop (USB drive or network) and tell Claude where it is."
