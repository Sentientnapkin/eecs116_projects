#!/bin/bash
while pgrep -f "chain4.sh" > /dev/null; do sleep 15; done
cd ~/ws_m
for n in "$@"; do bash /mnt/c/Users/alexa/Projects/eecs116_vio/b16/w_eval.sh $n hf; done
