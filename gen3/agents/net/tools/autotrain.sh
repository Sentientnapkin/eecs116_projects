#!/bin/bash
# autotrain.sh [STEP=300] : continue training as HF v3 train data arrives (driver.py must be running).
# Every 30 min: if cache/train_meta.jsonl grew by >= STEP flights since the last round -> refresh v3val pool + val cache,
# fine-tune from the previous best (first round: runs/ft2) on old + all new flights, export into GSLV (priors base gslvlj-compatible
# source src/gslv_s3_copy.c; no defines == gslv_linejac_arith + new weights), build, evaluate in-filter on v3val vs gslvlj and LC_ENABLE=0
# (net_lcoff) and vs the current best net_s3ft2_iso; builds plain + iso (PRIOR_MODE=1 START_STD=2.0); append everything to logs/auto.log. GPU 5 only; evals 14 workers. Stop: kill the PID in logs/autotrain.pid.
STEP=${1:-300}
A=/data/backups/rganapa/Sebastian/gen3/agents/net; P=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
cd $A; echo $$ > logs/autotrain.pid
export CUDA_VISIBLE_DEVICES=5
LAST=$(cat logs/auto_last 2>/dev/null || echo 139); PREV=$(cat logs/auto_prev 2>/dev/null || echo $A/runs/ft2)
REFW=/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/linejac/final/gslv_linejac_arith.wasm
while true; do
  N=$(wc -l < cache/train_meta.jsonl)
  if [ $N -ge $((LAST + STEP)) ]; then
    NAME=auto_$N; OLD=0.3; [ $N -ge 1000 ] && OLD=0.15; [ $N -ge 4000 ] && OLD=0.1
    echo "$(date '+%F %H:%M') round $NAME new=$N old_share=$OLD init=$PREV" >> logs/auto.log
    bash /data/backups/rganapa/Sebastian/gen3/refresh_pools.sh >> logs/auto.log 2>&1
    $P -B /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learnvel/lv_prep.py /data/backups/rganapa/Sebastian/gen3/pools/v3val 12 $A/cache/val > logs/prep_val_$N.log 2>&1
    (cd tools && $P -B lv3.py --name $NAME --init $PREV --old $OLD --rev 0.3 --epochs 60 > ../logs/$NAME.log 2>&1)
    grep DONE logs/$NAME.log | cut -c1-400 >> logs/auto.log
    if [ -f runs/$NAME/best.pt ]; then
      $P -B tools/mkgslv.py runs/$NAME src/g_$NAME.c --base src/gslv_s3_copy.c >> logs/auto.log 2>&1
      $P -B tools/build.py src/g_$NAME.c g_$NAME >> logs/auto.log 2>&1
      $P -B tools/build.py src/g_$NAME.c g_${NAME}_iso "PRIOR_MODE=1 START_STD=2.0" >> logs/auto.log 2>&1
      tools/ev.sh gslvlj $REFW v3val 14 > /dev/null 2>&1
      tools/ev.sh net_lcoff $A/builds/lcoff/solution.wasm v3val 14 > /dev/null 2>&1
      tools/ev.sh net_$NAME $A/builds/g_$NAME/solution.wasm v3val 14 > /dev/null 2>&1
      tools/ev.sh net_${NAME}_iso $A/builds/g_${NAME}_iso/solution.wasm v3val 14 > /dev/null 2>&1
      (cd /data/backups/rganapa/Sebastian/gen3 && python3 score.py evals/gslvlj__v3val.json evals/net_lcoff__v3val.json evals/net_${NAME}__v3val.json evals/net_${NAME}_iso__v3val.json evals/net_s3ft2_iso__v3val.json | tail -n 5) >> logs/auto.log
      PREV=$A/runs/$NAME; echo $PREV > logs/auto_prev
    fi
    LAST=$N; echo $N > logs/auto_last
  fi
  sleep 1800
done
