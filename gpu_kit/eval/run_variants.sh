#!/bin/bash
# Score solution variants on every flight group in the flights folder (the lab machine's own hidden-like flights).
#   bash run_variants.sh batch.txt [how many at once, default 8]
# batch.txt: one variant per line, "NAME -DFLAG=VALUE ...". Results: eval/results/var_NAME.txt, then a summary table.
# Commit and push eval/results/ afterwards (small text files).
EVAL=$(cd "$(dirname "$0")" && pwd)
KIT=$(dirname "$EVAL")
REPO=$(cat "$KIT/.repo_path" 2>/dev/null) || { echo "run setup.sh first"; exit 1; }
. "$REPO/.venv/bin/activate"
export EVAL FLIGHTS=$(cat "$KIT/.flights_path" 2>/dev/null || echo "$HOME/flights_gpu")
mkdir -p "$EVAL/results" "$EVAL/libs"
one() {
  name=$1; shift
  gcc -O2 -shared -fPIC -I "$EVAL" "$@" -o "$EVAL/libs/libvio_$name.so" "$EVAL/solution.c" -lm || { echo "BUILD FAILED $name"; return; }
  out="$EVAL/results/var_$name.txt"
  echo "flags: $*" > "$out.tmp"
  for g in "$FLIGHTS"/*/; do
    case $(basename "$g") in logs|calib|_test) continue;; esac
    ls "$g"*.zip >/dev/null 2>&1 || continue
    echo "=== $(basename "$g")" >> "$out.tmp"
    (cd "$EVAL" && python diag.py "$g" "lib=$EVAL/libs/libvio_$name.so" 2>&1 | grep -v '^conta:') >> "$out.tmp"
  done
  mv "$out.tmp" "$out"
  echo "$(date +%H:%M) done $name"
}
export -f one
grep -v '^#' "$1" | grep . | xargs -P "${2:-8}" -L 1 bash -c 'one "$@"' _
python "$EVAL/summary.py"
