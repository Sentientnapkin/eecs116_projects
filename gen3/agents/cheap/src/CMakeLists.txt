cmake_minimum_required(VERSION 3.20)
project(vio C CXX)
# wasm (the submission): viobench bundle classical/vio -o classical/output/vio.wasm
set(CMAKE_CXX_STANDARD 17)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()
set(VIOBENCH_NATIVE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/runtime" CACHE PATH "directory with viobench_abi.h and viobench_reactor.cmake")
include(${VIOBENCH_NATIVE_DIR}/viobench_reactor.cmake)
viobench_solution(vio solution.cpp net.c)
# -O3 (after the reactor's -O2) and no loop strength reduction: constant-trip loops become straight-line code and
# constant offsets fold into the load/store operands. Otherwise every such offset costs a const and an add, and fuel
# counts every operator (measured with classical/vio/bench.py: -40 % on the covariance and pyramid kernels).
target_compile_options(vio PRIVATE $<$<COMPILE_LANGUAGE:CXX>:-fno-exceptions -fno-rtti -fno-math-errno -O3 -mllvm -disable-lsr>)
target_compile_options(vio PRIVATE $<$<COMPILE_LANGUAGE:C>:-O3>)
