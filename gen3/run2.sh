cd /data/backups/rganapa/Sebastian/gen3; . ./env.sh; export HYPERLUX_SKIP_BUILD=1 OMP_NUM_THREADS=1
GP=(3 5 6 7)
echo "$(date -u +%F' '%T) run2: GPU4 workers moved to GPU3" >> logs/run.log
for w in $(seq 0 4 28); do CUDA_VISIBLE_DEVICES=${GP[$((w%4))]} nice -n 10 python g3.py cfg/roster.json out $w 32 >> logs/w$w.log 2>&1 & done
while ps -u $(id -un) -o args | grep -q "[g]3.py cfg/roster.json"; do sleep 60; done
echo "$(date -u +%F' '%T) pass 1 done; pass 2 start" >> logs/run.log
for w in $(seq 0 31); do CUDA_VISIBLE_DEVICES=${GP[$((w%4))]} nice -n 10 python g3.py cfg/roster.json out $w 32 >> logs/w$w.log 2>&1 & done; wait
while ps -u $(id -un) -o args | grep -q "[g]3.py cfg/roster"; do sleep 60; done
touch out/GEN_DONE; echo "$(date -u +%F' '%T) GEN_DONE" >> logs/run.log
