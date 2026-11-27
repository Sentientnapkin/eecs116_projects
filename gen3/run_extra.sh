cd /data/backups/rganapa/Sebastian/gen3; . ./env.sh; export HYPERLUX_SKIP_BUILD=1 OMP_NUM_THREADS=1
echo "$(date -u +%F' '%T) extra GPU5 x8 start" >> logs/run.log
for w in $(seq 0 7); do CUDA_VISIBLE_DEVICES=5 nice -n 10 python g3.py cfg/roster_rev.json out $w 8 >> logs/x$w.log 2>&1 & done; wait
echo "$(date -u +%F' '%T) extra done" >> logs/run.log
