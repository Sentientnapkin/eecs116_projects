#!/bin/bash
# hf_batch.sh FILE: each line "NAME -Dflags..." -> hf_var.sh, one variant at a time (each uses 16 processes)
while read -r name flags; do [ -z "$name" ] || [[ $name == \#* ]] && continue; bash /mnt/c/Users/alexa/Projects/eecs116_vio/proto/night/hf/hf_var.sh $name $flags; done < "$1"
