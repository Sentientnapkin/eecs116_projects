#!/bin/bash
cd ~/ws_m
for n in "$@"; do
  /usr/bin/time -f "%e s" bash /mnt/c/Users/alexa/Projects/eecs116_vio/b16/w_eval.sh $n hf
  bash /mnt/c/Users/alexa/Projects/eecs116_vio/b16/w_eval.sh $n pub
done
