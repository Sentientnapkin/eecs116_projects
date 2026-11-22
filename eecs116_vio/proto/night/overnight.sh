#!/bin/bash
# Overnight: simulate every flight in jobs.txt (2 at a time), retry failures once, then score v3 and do-nothing on each group.
D=/mnt/c/Users/alexa/Projects/eecs116_vio/proto/night
cd "$HOME"; mkdir -p logs_night; echo "start $(date)" >> logs_night/progress.txt
seed=5000; : > logs_night/joblist
while IFS='|' read -r group extra style scenes; do
  [[ $group =~ ^# || -z $group ]] && continue
  for s in $scenes; do seed=$((seed+1)); echo "$(echo $group) $(echo $style) $seed $s $(echo $extra)" >> logs_night/joblist; done
done < $D/jobs.txt
run() { while read -r g st sd sc ex; do printf '%s\0%s\0%s\0%s\0%s\0' "$g" "$st" "$sd" "$sc" "$ex"; done < logs_night/joblist | xargs -0 -n5 -P "$1" bash $D/one_flight.sh; }
run 2
run 1   # retry anything that failed (existing flights are skipped)
echo "simulation done $(date)" >> logs_night/progress.txt
bash $D/score.sh > $D/results.txt 2>&1
echo "all done $(date)" >> logs_night/progress.txt
