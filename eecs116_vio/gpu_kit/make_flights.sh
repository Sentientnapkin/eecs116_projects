#!/bin/bash
# Render every flight in jobs_gpu.txt into ~/$F/<group>/ (one simulate call per scene; finished scenes are
# skipped, so re-running resumes).
#   bash make_flights.sh
KIT=$(cd "$(dirname "$0")" && pwd)
REPO=$(cat "$KIT/.repo_path" 2>/dev/null) || { echo "run setup.sh first"; exit 1; }
. "$REPO/.venv/bin/activate"
FLIGHTS=$(cat "$KIT/.flights_path" 2>/dev/null || echo "$HOME/flights_gpu")
cd "$(dirname "$FLIGHTS")"
F=$(basename "$FLIGHTS")
mkdir -p $F/logs

style() {
  local n=$1


  grep -v '^#' "$KIT/styles.txt" | awk -F'|' -v n="$n" '{gsub(/ /, "", $1)} $1 == n {print $2}'
}

seed=7000
fails=0
made=0
grep -v '^#' "$KIT/jobs_gpu.txt" | grep . | while IFS='|' read -r group st eps extra scenes; do
  group=$(echo $group)
  eps=$(echo $eps)
  x=$(style $(echo $st))
  [ -n "$x" ] || { echo "unknown style $st"; continue; }
  for scene in $scenes; do
    seed=$((seed + 1))
    out=$F/$group
    ls $out/sim-$scene-*.zip >/dev/null 2>&1 && continue
    start=$(date +%s)
    VIOBENCH_TASK_EXTRA="$x" viobench simulate -o $out --episodes $eps --seed $seed --duration 60 --no-video $extra \
      --scene-names $scene > $F/logs/$group-$scene.log 2>&1
    n=$(ls $out/sim-$scene-*.zip 2>/dev/null | wc -l)
    echo "$(date +%H:%M) $group $scene: $n flights, $(( $(date +%s) - start )) s" | tee -a $F/logs/progress.txt
    if [ "$n" = 0 ]; then
      fails=$((fails + 1)); echo "  FAILED. Log:"; grep -v '^conta:' $F/logs/$group-$scene.log | tail -4
      [ "$fails" -ge 3 ] && [ "$made" = 0 ] && { echo "Nothing works; stopping. Send these lines to Claude."; exit 1; }
    else made=$((made + 1)); fi
  done
done

echo
echo "speed check (hidden flights: 0.66-1.34 m/s average per flight, rms distance from start ~4.7 m):"
for d in $F/*/; do
  case $(basename $d) in logs|calib|_test) continue;; esac
  python "$KIT/flight_stats.py" $d 2>/dev/null | grep '^STAT' | awk -v n=$(basename $d) -F'\t' \
    '{k++; v+=$4; r+=$5} END {if (k) printf "  %-12s %3d flights  %4.2f m/s  rms from start %4.2f m\n", n, k, v/k, r/k}'
done
echo "done: $(du -sh $F | cut -f1). Copy ~/flights_gpu to the laptop (USB drive or network) and tell Claude where it is."
