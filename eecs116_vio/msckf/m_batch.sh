#!/bin/bash
# m_batch.sh FILE: lines "NAME -Dflags..." -> m_var.sh one after another
while read -r name flags; do [ -z "$name" ] || [[ $name == \#* ]] && continue; bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/m_var.sh $name $flags; done < "$1"
