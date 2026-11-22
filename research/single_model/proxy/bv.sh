#!/usr/bin/env bash
# bv.sh NAME SRC.c [DEFINE=VAL ...] -> out/NAME/solution.wasm  (same flags as the B16 build; defines prepended)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
NAME=$1; SRC=$2; shift 2
WASI=/c/Users/alexa/vio_tools/wasi-sdk-34.0-x86_64-windows
NATIVE=/c/Users/alexa/viobench/viobench/solution/runtime/native
OUT=$HERE/out/$NAME; mkdir -p "$OUT"
{ for d in "$@"; do k=${d%%=*}; v=${d#*=}; echo "#define $k $v"; done; cat "$SRC"; } > "$OUT/solution.c"
"$WASI/bin/clang.exe" --target=wasm32-wasip1 --sysroot="$WASI/share/wasi-sysroot" -I"$NATIVE" -O3 -DNDEBUG -O2 -msimd128 -O3 \
  -mexec-model=reactor -Wl,--initial-memory=67108864 -Wl,--strip-debug -Wno-constant-logical-operand -Wno-macro-redefined "$OUT/solution.c" -lm -o "$OUT/solution.wasm"
echo "$SRC $*" > "$OUT/defines.txt"
sha256sum "$OUT/solution.wasm" | cut -c1-16
