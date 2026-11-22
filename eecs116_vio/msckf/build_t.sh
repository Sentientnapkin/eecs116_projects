#!/bin/bash
# build_m.sh NAME [DEF=VAL ...]: msckf/solution.c (or $SRC) -> ~/ws_m/ms_NAME.wasm, then viobench check.
# FLAGS: extra compile flags on top of the reactor's -O2 -msimd128 (default none, like the submitted build).
set -e
source "$HOME/.venv/bin/activate"
cd "$HOME"
[ -d ws_t ] || viobench init native ws_t > /dev/null
cd ws_t
NAME=$1; shift || true
SRC=${SRC:-/mnt/c/Users/alexa/Projects/eecs116_vio/msckf/solution.c}
: > solution/solution.c
for def in "$@"; do echo "#define ${def%%=*} ${def#*=}" >> solution/solution.c; done
cat "$SRC" >> solution/solution.c
rm -f solution/solution.cpp
grep -q "VIO_FLAGS" solution/CMakeLists.txt || echo 'separate_arguments(VIO_FLAGS_LIST UNIX_COMMAND "$ENV{VIO_FLAGS}")
target_compile_options(solution PRIVATE ${VIO_FLAGS_LIST})' >> solution/CMakeLists.txt
sed -i 's/viobench_solution(solution solution.cpp)/viobench_solution(solution solution.c)/; s/^target_compile_options(solution .*-fno-exceptions.*$//' solution/CMakeLists.txt
grep -q "target_link_libraries(solution PRIVATE m)" solution/CMakeLists.txt || echo 'target_link_libraries(solution PRIVATE m)' >> solution/CMakeLists.txt
export VIO_FLAGS="${FLAGS-}"
rm -rf solution/build; viobench bundle solution -o "ms_$NAME.wasm" > "build_$NAME.log" 2>&1 || { tail -30 "build_$NAME.log"; exit 1; }
viobench check "ms_$NAME.wasm" | tail -1
