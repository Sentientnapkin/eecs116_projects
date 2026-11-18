#!/bin/sh
# Corrected visual, temporal and rotation runs are separate immutable jobs.
set -eu
PY=${PY:-/opt/miniconda3/bin/python}
case "$#" in
  0) "$PY" -B test_causal.py
     "$PY" -B learned_probe.py --smoke
     "$PY" -B learned_probe.py ;;
  1) "$PY" -B seq_heads.py "$1"
     "$PY" -B bias_probe.py "$1"
     "$PY" -B decompose.py "$1" --diagnostics-only ;;
  *) printf '%s\n' "usage: run_all.sh [completed-visual-run]" >&2; exit 2 ;;
esac
