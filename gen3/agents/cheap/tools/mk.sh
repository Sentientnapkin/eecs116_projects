#!/bin/bash
# mk.sh NAME "DEFINES" -> builds/NAME/solution.wasm + import check
C=/data/backups/rganapa/Sebastian/gen3/agents/cheap
cd $C && ../../../venv-teacher/bin/python tools/build.py $1 src "$2" 2>&1 | grep -E "error|solution.wasm" && python3 tools/imports.py builds/$1/solution.wasm | head -1
