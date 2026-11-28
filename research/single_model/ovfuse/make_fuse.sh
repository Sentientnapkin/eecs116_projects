#!/usr/bin/env bash
# make_fuse.sh NAME [FUSE_DEFINE=VAL ...]  (run inside WSL) -> ~/ws_ov/NAME/build/solution.wasm, copied to ~/ws_ov/NAME.wasm
# Source tree = the provided OpenVINS example (unchanged except its 5 ABI functions renamed ov_* and an ovx_started() accessor)
#             + B16 (b16s_snapshot.c defaults, ABI functions renamed b16_*) + fuse.cpp (the real exports).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
NAME=$1; shift
WS=~/ws_ov; D=$WS/$NAME
mkdir -p "$D"
rsync -a --exclude build "$WS/openvins_plain/" "$D/"
# a copy of the ABI header without export attributes, for the two inner units
sed 's/#define VIOBENCH_EXPORT(name) __attribute__((export_name(#name)))/#define VIOBENCH_EXPORT(name)/' \
    "$WS/runtime/native/viobench_abi.h" > "$D/abi_noexport.h"
grep -q '#define VIOBENCH_EXPORT(name)$' "$D/abi_noexport.h"
# OpenVINS: rename the ABI definitions, add the accessor
sed -e 's/#include "viobench_abi.h"/#include "abi_noexport.h"/' \
    -e 's/^int32_t abi_version() {/int32_t ovx_abi_version() {/' -e 's/^void\* alloc(uint32_t size) {/void* ovx_alloc(uint32_t size) {/' \
    -e 's/^int32_t frame_width() {/int32_t ovx_frame_width() {/' -e 's/^int32_t init(const char\* json, uint32_t length) {/int32_t ovx_init(const char* json, uint32_t length) {/' \
    -e 's/^int32_t step(double t, const uint8_t\* frame, const double\* imu, int32_t imu_count, double\* out) {/int32_t ovx_step(double t, const uint8_t* frame, const double* imu, int32_t imu_count, double* out) {/' \
    "$WS/openvins_plain/solution.cpp" > "$D/solution.cpp"
for f in ovx_abi_version ovx_alloc ovx_frame_width ovx_init ovx_step; do grep -q "^[a-z0-9_]*\*\? $f(" "$D/solution.cpp" || { echo "rename of $f failed"; exit 1; }; done
echo 'bool ovx_started() { return chain_state.vio && chain_state.vio->started(); }' >> "$D/solution.cpp"
# B16
sed -e 's/#include "viobench_abi.h"/#include "abi_noexport.h"/' \
    -e 's/^int32_t abi_version(void) {/static int32_t b16_abi_version(void) {/' -e 's/^void \*alloc(uint32_t size) {/static void *b16_alloc(uint32_t size) {/' \
    -e 's/^int32_t frame_width(void) {/static int32_t b16_frame_width(void) {/' -e 's/^int32_t init(const char \*json, uint32_t length) {/int32_t b16_init(const char *json, uint32_t length) {/' \
    -e 's/^int32_t step(double t, const uint8_t \*frame, const double \*imu, int32_t imu_count, double \*out) {/int32_t b16_step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {/' \
    "$HERE/../proxy/b16s_snapshot.c" > "$D/b16_unit.c"
for f in b16_init b16_step; do grep -q "^int32_t $f(" "$D/b16_unit.c" || { echo "rename of $f failed"; exit 1; }; done
cp "$HERE/fuse.cpp" "$D/fuse.cpp"
DEFS=""; for d in "$@"; do DEFS="$DEFS ${d%%=*}=${d#*=}"; done
sed -i 's/^viobench_solution(solution solution.cpp)$/viobench_solution(solution fuse.cpp solution.cpp b16_unit.c)\
set_source_files_properties(b16_unit.c PROPERTIES COMPILE_OPTIONS "-O3;-Wno-constant-logical-operand;-Wno-macro-redefined")\
set_source_files_properties(fuse.cpp PROPERTIES COMPILE_DEFINITIONS "'"${DEFS# }"'")/' "$D/CMakeLists.txt"
sed -i 's/COMPILE_DEFINITIONS " /COMPILE_DEFINITIONS "/; s/COMPILE_DEFINITIONS "\(.*\)")/COMPILE_DEFINITIONS "\1")/' "$D/CMakeLists.txt"
python3 - "$D/CMakeLists.txt" <<'PY'
import sys; p=sys.argv[1]; s=open(p).read()
import re
s=re.sub(r'COMPILE_DEFINITIONS "([^"]*)"', lambda m: 'COMPILE_DEFINITIONS "'+';'.join(m.group(1).split())+'"', s)
open(p,'w').write(s)
PY
grep -n 'viobench_solution\|set_source_files' "$D/CMakeLists.txt"
# reuse the plain build's downloads/sources so nothing is fetched twice
mkdir -p "$D/build"; [ -d "$WS/openvins_plain/build/downloads" ] && cp -rn "$WS/openvins_plain/build/downloads" "$D/build/" || true
cd "$WS" && CMAKE_BUILD_PARALLEL_LEVEL=12 ~/.venv/bin/viobench bundle "$NAME" -o "$NAME.wasm" > "$NAME.bundle.log" 2>&1 || { tail -30 "$NAME.bundle.log"; exit 1; }
sha256sum "$NAME.wasm" | cut -c1-16; ls -la "$NAME.wasm"
