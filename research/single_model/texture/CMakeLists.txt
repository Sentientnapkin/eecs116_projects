cmake_minimum_required(VERSION 3.20)
project(gp_msckf C)
# Build from the parent directory with VIOBench installed (pip install -e <viobench checkout>):
#   viobench bundle gp_msckf -o build/gp_msckf.wasm
# `bundle` runs VIOBench's runtime/native/build.sh, which fetches wasi-sdk and passes VIOBENCH_NATIVE_DIR and the
# toolchain file. Configuring by hand: -DVIOBENCH_NATIVE_DIR=<viobench>/viobench/solution/runtime/native.
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()
set(VIOBENCH_NATIVE_DIR "" CACHE PATH "VIOBench's viobench/solution/runtime/native (viobench_abi.h, viobench_reactor.cmake)")
if(NOT VIOBENCH_NATIVE_DIR)
    message(FATAL_ERROR "build with `viobench bundle gp_msckf -o build/gp_msckf.wasm`, or pass -DVIOBENCH_NATIVE_DIR=<viobench>/viobench/solution/runtime/native")
endif()
include(${VIOBENCH_NATIVE_DIR}/viobench_reactor.cmake)
viobench_solution(solution solution.c)
target_link_libraries(solution PRIVATE m)
