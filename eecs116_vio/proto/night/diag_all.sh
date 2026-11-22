#!/bin/bash
cd /mnt/c/Users/alexa/Projects/eecs116_vio/proto
for s in NIGHT TUNE HELDOUT AGILE2; do echo "=== $s"; bash pyrun.sh $s diag.py "$@"; done
