#!/bin/bash
# Compile the C solution as host shared libraries for the Python harness (proto/csolution.py).
# Default build: libvio_host.so.  Experiments: libvio_<name>.so with -D overrides.
set -e
SRC=/mnt/c/Users/alexa/Projects/eecs116_vio/csol/solution/solution.c
INC="$HOME/ws_c/runtime/native"
build() { gcc -O2 -shared -fPIC -I "$INC" "${@:2}" -o "$HOME/ws_c/libvio_$1.so" "$SRC" -lm; echo "built libvio_$1.so ${*:2}"; }
build host
build coarse5  -DCOARSE_ITERATIONS=5 -DCOARSE_EPS=0.0009f
