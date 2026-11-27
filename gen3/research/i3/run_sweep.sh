#!/bin/bash
cd /data/backups/rganapa/Sebastian/gen3/research/i3
while IFS='|' read -r n f; do
  [ -f ana/$n.json ] && continue
  while [ "$(cut -d. -f1 /proc/loadavg)" -gt 170 ]; do sleep 60; done
  python3 tools/run_one.py "$n" "$f" i3s120 8 >> logs/sweep.log 2>&1
done < queue.txt
echo "- i3 sweep done $(date)" >> NOTES.md; touch logs/sweep.done
