#!/bin/bash
while [ "$(grep -c ' pub ' /mnt/c/Users/alexa/Projects/eecs116_vio/b16/run3.out)" -lt 3 ]; do sleep 20; done
bash /mnt/c/Users/alexa/Projects/eecs116_vio/b16/run3.sh "$@"
