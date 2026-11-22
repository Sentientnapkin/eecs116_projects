#!/bin/bash
# Bundle the prototype into a submission .wasm inside a viobench Python workspace (WSL), then sanity-check it.
set -e
source "$HOME/.venv/bin/activate"
cd "$HOME"
[ -d ws_proto ] || viobench init python ws_proto
cp /mnt/c/Users/alexa/Projects/eecs116_vio/proto/solution/solution.py ws_proto/solution/solution.py
ls ws_proto/solution
cd ws_proto
viobench bundle solution -o proto.wasm
ls -la proto.wasm
viobench check proto.wasm
