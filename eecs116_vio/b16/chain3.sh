#!/bin/bash
while pgrep -f "run3.sh h1 h2 l4" > /dev/null; do sleep 15; done
bash /mnt/c/Users/alexa/Projects/eecs116_vio/b16/run3.sh "$@"
