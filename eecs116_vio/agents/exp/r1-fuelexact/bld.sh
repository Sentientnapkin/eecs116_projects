#!/bin/bash
# bld.sh SRC.c OUT.wasm [EXTRA_FLAGS] [SHELL_FLAGS] : SHELL_FLAGS are passed as one CMake SHELL: group (no de-duplication, for -mllvm pairs).
# build a GSLV source with the preserved_best flags (as -D defines, like mk.py)
# in the WSL workspace ~/ws_r1fe (viobench init native), -O3 appended after the recipe's -O2 (as the teammate's CMakeLists).
set -e
source "$HOME/.venv/bin/activate"
HERE=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/exp/r1-fuelexact
SRC=$(realpath "$1"); OUT=$(realpath -m "$2"); EXTRA="$3"; export VIO_SHELL="$4"
DEFS=$(tr -d '\r' < "$HERE/src/flags.txt")
WS=$HOME/${WS:-ws_r1fe}; [ -d $WS ] || viobench init native $WS > /dev/null
cd $WS
cp "$SRC" solution/solution.c; rm -f solution/solution.cpp
sed -i 's/viobench_solution(solution solution.cpp)/viobench_solution(solution solution.c)/; s/^target_compile_options(solution .*-fno-exceptions.*$//' solution/CMakeLists.txt
grep -q "VIO_FLAGS" solution/CMakeLists.txt || echo 'separate_arguments(VIO_FLAGS_LIST UNIX_COMMAND "$ENV{VIO_FLAGS}")
target_compile_options(solution PRIVATE ${VIO_FLAGS_LIST})' >> solution/CMakeLists.txt
grep -q "VIO_SHELL" solution/CMakeLists.txt || echo 'if(NOT "$ENV{VIO_SHELL}" STREQUAL "")
target_compile_options(solution PRIVATE "SHELL:$ENV{VIO_SHELL}")
endif()' >> solution/CMakeLists.txt
grep -q "target_link_libraries(solution PRIVATE m)" solution/CMakeLists.txt || echo 'target_link_libraries(solution PRIVATE m)' >> solution/CMakeLists.txt
export VIO_FLAGS="$(for d in $DEFS; do printf -- '-D%s ' "$d"; done) -O3 $EXTRA"
rm -rf solution/build
viobench bundle solution -o out.wasm > build.log 2>&1 || { tail -30 build.log; exit 1; }
cp out.wasm "$OUT"; sha256sum "$OUT" | cut -c1-16
