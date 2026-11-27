cd /data/backups/rganapa/Sebastian/gen3; . ./env.sh; export HYPERLUX_SKIP_BUILD=1 OMP_NUM_THREADS=1
GP=(); for i in $(seq 8); do GP+=(3); done; for i in $(seq 20); do GP+=(5); done; for i in $(seq 16); do GP+=(6 7); done; N=${#GP[@]}
for pass in 1 2; do
  echo "$(date -u +%F' '%T) run3 pass $pass start: $N workers (GPU3 x8, GPU5 x20, GPU6 x16, GPU7 x16), roster4" >> logs/run.log
  for w in $(seq 0 $((N-1))); do CUDA_VISIBLE_DEVICES=${GP[$w]} nice -n 10 python g3.py cfg/roster4.json out $w $N >> logs/w$w.log 2>&1 & done; wait
done
touch out/GEN_DONE; echo "$(date -u +%F' '%T) GEN_DONE" >> logs/run.log
