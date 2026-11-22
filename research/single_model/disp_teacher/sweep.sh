#!/usr/bin/env bash
# sweep.sh TAG CKPT WORKERS SLICE "VARIANT_NAME:DEF=V,DEF=V" ...
# export CKPT -> out/TAG/dt_weights.h, parity check, then for every variant: build + evalrun vs b16.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); cd "$HERE"
TAG=$1; CKPT=$2; WORKERS=$3; SLICE=$4; shift 4
PY=/c/Users/alexa/vio_env/Scripts/python
CUDA_VISIBLE_DEVICES= $PY export_c.py --ckpt "$CKPT" --out out/$TAG/dt_weights.h 2>&1 | grep -v Warn
CUDA_VISIBLE_DEVICES= $PY parity.py --ckpt "$CKPT" --weights out/$TAG/dt_weights.h 2>&1 | grep -v Warn | tail -2
for spec in "$@"; do
  name=${spec%%:*}; defs=${spec#*:}
  bash build.sh "${TAG}_$name" out/$TAG/dt_weights.h DT_ON=1 DT_LOG=1 ${defs//,/ } > /dev/null
  echo "### ${TAG}_$name  ($defs)"
  python -I evalrun.py --wasm out/${TAG}_$name/solution.wasm --name ${TAG}_$name --ref b16 --slice $SLICE --workers $WORKERS 2>&1 | grep -v "^[0-9]*/[0-9]* [0-9]*s$"
done
