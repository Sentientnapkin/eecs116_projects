cd /data/backups/rganapa/Sebastian/gen3; . ./env.sh; export HYPERLUX_SKIP_BUILD=1 OMP_NUM_THREADS=1
echo "$(date -u +%F' '%T) mid group: 8 on GPU6 + 8 on GPU7" >> logs/run.log
for w in $(seq 0 15); do CUDA_VISIBLE_DEVICES=$((6+w%2)) nice -n 10 python g3.py cfg/roster_mid.json out $w 16 >> logs/m$w.log 2>&1 & done; wait
echo "$(date -u +%F' '%T) mid done" >> logs/run.log
