#!/usr/bin/env bash
# Copy finished proxy flights out of WSL, then score every calibration build on the flights it has not seen yet.
#   bash px_sync_eval.sh [WORKERS] [BUILD ...]      (default: all calibration builds)
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=${1:-4}; shift || true
SRC=//wsl.localhost/Ubuntu-24.04/home/alexa/data/proxy
DST=/c/Users/alexa/vio_data/proxy; mkdir -p "$DST"
for z in "$SRC"/*.zip; do
  [ -e "$z" ] || continue
  b=$(basename "$z" .zip)
  [ -e "$DST/$b.json" ] || { cp "$z" "$DST/$b.zip.part" && mv "$DST/$b.zip.part" "$DST/$b.zip" && cp "$SRC/$b.json" "$DST/$b.json"; }
done
echo "proxy flights: $(ls $DST/*.zip 2>/dev/null | wc -l)"
R=/c/Users/alexa/Projects/eecs_116/eecs116_projects
declare -A WASM=(
  [base]="$R/Final Project/classical_vio/gp_msckf/gp_msckf.wasm"
  [G]="$R/research/single_model/final/submit/gp_msckf_startup_gate.wasm"
  [b16]="/c/Users/alexa/vio_data/work/evals/b16/solution.wasm"
  [m7]="$HERE/out/srv_ms_m7/solution.wasm"
  [b16_nolc]="$HERE/out/s_b16_nolc/solution.wasm"
  [m7_nolc]="$HERE/out/m7_nolc/solution.wasm"
  [lowfuel_try]="$HERE/out/srv_lowfuel_try/solution.wasm"
  [b17]="$R/research/single_model/disp_teacher/final/gp_msckf_b17_dtstudent.wasm"
)
BUILDS=("$@"); [ ${#BUILDS[@]} -gt 0 ] || BUILDS=(b16 G m7 m7_S2k3 m7_spdk3 b17)
for b in "${BUILDS[@]}"; do
  C:/Users/alexa/vio_eval/Scripts/python -I "$HERE/evalproxy.py" --wasm "${WASM[$b]:-$HERE/out/$b/solution.wasm}" --name "$b" --workers "$W" > "/c/Users/alexa/vio_data/work/evals/px_$b.log" 2>&1
  echo "$b: $(grep -m1 '  all ' /c/Users/alexa/vio_data/work/evals/px_$b.log)"
done
