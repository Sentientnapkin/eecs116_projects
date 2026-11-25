#!/bin/bash
# build.sh [NAME] : probe.c -> ~/ws_probe/probe_NAME.wasm (inside WSL), then viobench check.
#   DEFS="DEBUGX=1" bash build.sh debug     # calibration build: prints the payloads to stderr
set -e
source "$HOME/.venv/bin/activate"
HERE=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/probe
NAME=${1:-release}
cd "$HOME"
WS=${WS:-ws_probe}; [ -d $WS ] || viobench init native $WS > /dev/null
cd $WS
: > solution/solution.c
for def in $DEFS; do echo "#define ${def%%=*} ${def#*=}" >> solution/solution.c; done
cat "$HERE/probe.c" >> solution/solution.c
rm -f solution/solution.cpp
sed -i 's/viobench_solution(solution solution.cpp)/viobench_solution(solution solution.c)/; s/^target_compile_options(solution .*-fno-exceptions.*$//' solution/CMakeLists.txt
grep -q "VIO_FLAGS" solution/CMakeLists.txt || echo 'separate_arguments(VIO_FLAGS_LIST UNIX_COMMAND "$ENV{VIO_FLAGS}")
target_compile_options(solution PRIVATE ${VIO_FLAGS_LIST})' >> solution/CMakeLists.txt
grep -q "target_link_libraries(solution PRIVATE m)" solution/CMakeLists.txt || echo 'target_link_libraries(solution PRIVATE m)' >> solution/CMakeLists.txt
export VIO_FLAGS="${FLAGS--O2}"
rm -rf solution/build
viobench bundle solution -o "probe_$NAME.wasm" > "build_$NAME.log" 2>&1 || { tail -30 "build_$NAME.log"; exit 1; }
ls -la "probe_$NAME.wasm"
sha256sum "probe_$NAME.wasm"
viobench check "probe_$NAME.wasm" | tail -3
