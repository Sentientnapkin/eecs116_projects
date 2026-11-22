#!/bin/bash
# Build the C solution into a submission .wasm (inside WSL) and run viobench's quick check.
#   bash build.sh                      -> ~/ws_c/vio_c.wasm with the defaults in solution.c
#   bash build.sh p11 HALF=5           -> ~/ws_c/vio_p11.wasm with #define HALF 5 prepended
# Source of truth: /mnt/c/Users/alexa/Projects/eecs116_vio/csol/solution/solution.c
set -e
source "$HOME/.venv/bin/activate"
cd "$HOME"
[ -d ws_c ] || viobench init native ws_c
cd ws_c
NAME=${1:-c}
shift || true
: > solution/solution.c
for def in "$@"; do echo "#define ${def%%=*} ${def#*=}" >> solution/solution.c; done
cat /mnt/c/Users/alexa/Projects/eecs116_vio/csol/solution/solution.c >> solution/solution.c
rm -f solution/solution.cpp
# speed flags: wasm SIMD (4 floats per instruction) and the float re-association the compiler needs to vectorize sums;
# NaN/inf checks stay valid (no -ffinite-math-only). FLAGS="..." overrides for experiments.
grep -q "VIO_FLAGS" solution/CMakeLists.txt || echo 'separate_arguments(VIO_FLAGS_LIST UNIX_COMMAND "$ENV{VIO_FLAGS}")
target_compile_options(solution PRIVATE ${VIO_FLAGS_LIST})' >> solution/CMakeLists.txt
export VIO_FLAGS="${FLAGS--O3 -msimd128 -fno-math-errno -fassociative-math -fno-signed-zeros -fno-trapping-math -freciprocal-math}"
sed -i 's/viobench_solution(solution solution.cpp)/viobench_solution(solution solution.c)/; s/^target_compile_options(solution .*-fno-exceptions.*$//' solution/CMakeLists.txt
rm -rf solution/build; VIO_FLAGS="$VIO_FLAGS" viobench bundle solution -o "vio_$NAME.wasm" > "build_$NAME.log" 2>&1 || { tail -30 "build_$NAME.log"; exit 1; }
ls -la "vio_$NAME.wasm"
viobench check "vio_$NAME.wasm" | tail -2
