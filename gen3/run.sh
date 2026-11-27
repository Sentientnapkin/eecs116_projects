cd /data/backups/rganapa/Sebastian/gen3; . ./env.sh; export HYPERLUX_SKIP_BUILD=1 OMP_NUM_THREADS=1
for pass in 1 2; do
  echo "$(date -u +%F' '%T) pass $pass start" >> logs/run.log
  for w in $(seq 0 31); do CUDA_VISIBLE_DEVICES=$((4+w%4)) nice -n 10 python g3.py cfg/roster.json out $w 32 >> logs/w$w.log 2>&1 & done; wait
  echo "$(date -u +%F' '%T) pass $pass done" >> logs/run.log
done
touch out/GEN_DONE; echo "$(date -u +%F' '%T) GEN_DONE" >> logs/run.log
