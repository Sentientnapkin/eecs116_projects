#!/bin/bash
# frames spooled per running simulator flight, sampled twice 60 s apart
for d in /tmp/viobench-sim-*; do echo "$d $(find "$d" -name '*.png' | wc -l)"; done > /tmp/rate_a.txt
sleep 60
for d in /tmp/viobench-sim-*; do echo "$d $(find "$d" -name '*.png' | wc -l)"; done > /tmp/rate_b.txt
join /tmp/rate_a.txt /tmp/rate_b.txt | awk '{printf "%s %d -> %d (+%d frames/min)\n", $1, $2, $3, $3-$2}'
