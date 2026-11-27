#!/bin/bash
# autotrain2.sh [STEP=300]: successor of autotrain.sh (takes over after its running round finishes).
# Every 30 min, when >= STEP new HF v3 train flights are cached: refresh pools + val cache, fine-tune from the previous run,
# export into GSLV, build with the CURRENT BEST FLAGS (PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0, priors agent F_sp10) and also iso
# (PRIOR_MODE=1 START_STD=2.0) for continuity, evaluate on v3val + v1val, re-run the current best on the refreshed pool (cached),
# and PROMOTE the new build to best only if it beats the best paired on v3val (d < -0.01 m) and does not regress v1val (d < +0.02).
# Best build: logs/best_name (eval name) + logs/best_wasm. GPU 5 only; evals 14 workers. Stop: kill the PID in logs/autotrain.pid.
STEP=${1:-300}
A=/data/backups/rganapa/Sebastian/gen3/agents/net; P=/data/backups/rganapa/Sebastian/venv-teacher/bin/python; G=/data/backups/rganapa/Sebastian/gen3
cd $A
OLDPID=$(cat logs/autotrain.pid)
# hand-over: wait until the old loop has finished its current round (it writes logs/auto_last at the end), then stop it
while [ "$(cat logs/auto_last 2>/dev/null)" != "$(ls -d runs/auto_* | sed 's/.*auto_//' | sort -n | tail -1)" ]; do sleep 60; done
kill $OLDPID 2>/dev/null; echo $$ > logs/autotrain.pid
echo "$(date '+%F %H:%M') autotrain2 took over from $OLDPID" >> logs/auto.log
export CUDA_VISIBLE_DEVICES=5
FLAGS="PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0"
[ -f logs/best_name ] || { echo pr_F_sp10 > logs/best_name; echo $G/agents/priors/builds/F_sp10/solution.wasm > logs/best_wasm; }
REFW=/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/linejac/final/gslv_linejac_arith.wasm
evalrun() { # NAME WASM : v3val + v1val
  tools/ev.sh $1 $2 v3val 14 > /dev/null 2>&1; tools/ev.sh $1 $2 v1val 14 > /dev/null 2>&1; }
judge() { # NAME : build/eval sp10 variant of run NAME, compare, maybe promote
  local NAME=$1
  $P -B tools/mkgslv.py runs/$NAME src/g_$NAME.c --base src/gslv_s3_copy.c >> logs/auto.log 2>&1
  [ -f builds/g_${NAME}_sp10/solution.wasm ] || $P -B tools/build.py src/g_$NAME.c g_${NAME}_sp10 "$FLAGS" >> logs/auto.log 2>&1
  [ -f builds/g_${NAME}_iso/solution.wasm ] || $P -B tools/build.py src/g_$NAME.c g_${NAME}_iso "PRIOR_MODE=1 START_STD=2.0" >> logs/auto.log 2>&1
  local BN=$(cat logs/best_name) BW=$(cat logs/best_wasm)
  evalrun $BN $BW; tools/ev.sh gslvlj $REFW v3val 14 > /dev/null 2>&1
  evalrun net_${NAME}_sp10 $A/builds/g_${NAME}_sp10/solution.wasm
  tools/ev.sh net_${NAME}_iso $A/builds/g_${NAME}_iso/solution.wasm v3val 14 > /dev/null 2>&1
  (cd $G && python3 score.py evals/gslvlj__v3val.json evals/${BN}__v3val.json evals/net_${NAME}_iso__v3val.json evals/net_${NAME}_sp10__v3val.json | tail -n 4) >> logs/auto.log
  read d3 lo3 hi3 n3 < <(python3 tools/pcmp.py $G/evals/${BN}__v3val.json $G/evals/net_${NAME}_sp10__v3val.json)
  read d1 lo1 hi1 n1 < <(python3 tools/pcmp.py $G/evals/${BN}__v1val.json $G/evals/net_${NAME}_sp10__v1val.json)
  echo "$(date '+%F %H:%M') judge net_${NAME}_sp10 vs $BN: v3val d=$d3 [$lo3,$hi3] n=$n3 ; v1val d=$d1 [$lo1,$hi1] n=$n1" >> logs/auto.log
  if python3 -c "import sys; sys.exit(0 if $d3 < -0.01 and $d1 < 0.02 else 1)"; then
    echo net_${NAME}_sp10 > logs/best_name; echo $A/builds/g_${NAME}_sp10/solution.wasm > logs/best_wasm
    echo "$(date '+%F %H:%M') PROMOTED net_${NAME}_sp10 (sha $(sha256sum builds/g_${NAME}_sp10/solution.wasm | cut -c1-8))" >> logs/auto.log
  fi
}
LAST=$(cat logs/auto_last); PREV=$(cat logs/auto_prev 2>/dev/null || echo $A/runs/ft2)
[ -f $PREV/best.pt ] && [ "$(basename $PREV)" != ft2 ] && judge $(basename $PREV)   # catch-up: judge the round the old loop ran
while true; do
  N=$(wc -l < cache/train_meta.jsonl)
  if [ $N -ge $((LAST + STEP)) ]; then
    NAME=auto_$N; OLD=0.3; [ $N -ge 1000 ] && OLD=0.15; [ $N -ge 4000 ] && OLD=0.1
    echo "$(date '+%F %H:%M') round $NAME new=$N old_share=$OLD init=$PREV" >> logs/auto.log
    bash $G/refresh_pools.sh >> logs/auto.log 2>&1
    $P -B /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learnvel/lv_prep.py $G/pools/v3val 12 $A/cache/val > logs/prep_val_$N.log 2>&1
    (cd tools && $P -B lv3.py --name $NAME --init $PREV --old $OLD --rev 0.3 --epochs 60 > ../logs/$NAME.log 2>&1)
    grep DONE logs/$NAME.log | cut -c1-400 >> logs/auto.log
    if [ -f runs/$NAME/best.pt ]; then judge $NAME; PREV=$A/runs/$NAME; echo $PREV > logs/auto_prev; fi
    LAST=$N; echo $N > logs/auto_last
  fi
  sleep 1800
done
