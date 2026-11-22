#!/bin/bash
# batch.sh FILE: each line "NAME FLAGS..." becomes one variant; runs 5 at a time.
D=/mnt/c/Users/alexa/Projects/eecs116_vio/proto/night
grep -v '^#' "$1" | grep . | xargs -P 5 -L 1 bash $D/variant.sh
