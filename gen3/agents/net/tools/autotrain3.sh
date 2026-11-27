#!/bin/bash
# autotrain3.sh [STEP=500]: successor of autotrain2.sh (2026-11-26), following the netv2 agent's findings:
#  - chain restarts from netv2/runs/A160ft (direct val err 0.2985 vs auto_3924 0.312, auto_727 0.343); netv2 recipe via lv4.py
#    (all cached HF train flights, old share 0.1, rev 0.3, lr 1e-3 warm-start fine-tune, 60 epochs), OMP_NUM_THREADS=3.
#  - PROMOTION on direct velocity error (seed noise ~0.001; tracks the server better than local in-filter ATE):
#    new best if direct 'all' < best_direct - 0.002 AND in-filter v3val d < +0.02 AND v1val d < +0.02 (regression check only).
#  - first action after hand-over: promote nv2_A160ft (netv2 evals: v3val d=-0.031 vs auto_727, v1val 0.617 vs 0.653), unless the
#    round autotrain2 is finishing produced something with better direct error.
STEP=${1:-500}
A=/data/backups/rganapa/Sebastian/gen3/agents/net; N2=/data/backups/rganapa/Sebastian/gen3/agents/netv2
P=/data/backups/rganapa/Sebastian/venv-teacher/bin/python; G=/data/backups/rganapa/Sebastian/gen3
cd $A
OLDPID=$(cat logs/autotrain.pid)
# hand-over: wait for autotrain2's running round to finish (it writes logs/auto_last), then stop it
while [ "$(cat logs/auto_last 2>/dev/null)" != "$(ls -d runs/auto_* | sed 's/.*auto_//' | sort -n | tail -1)" ]; do sleep 60; done
kill $OLDPID 2>/dev/null; echo $$ > logs/autotrain.pid
echo "$(date '+%F %H:%M') autotrain3 took over from $OLDPID (netv2 recipe, direct-error promotion)" >> logs/auto.log
export CUDA_VISIBLE_DEVICES=5 OMP_NUM_THREADS=3
FLAGS="PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0"
direct() { python3 -c "import json;print(json.load(open('$1/result.json'))['val']['all'])"; }
evalrun() { tools/ev.sh $1 $2 v3val 14 > /dev/null 2>&1; tools/ev.sh $1 $2 v1val 14 > /dev/null 2>&1; }
promote() { # EVALNAME WASM DIRECT
  echo $1 > logs/best_name; echo $2 > logs/best_wasm; echo $3 > logs/best_direct
  echo "$(date '+%F %H:%M') PROMOTED $1 direct=$3 (sha $(sha256sum $2 | cut -c1-8))" >> logs/auto.log; }
judge() { # RUNDIR : export, build sp10, eval, compare with best; promote on direct error + no in-filter regression
  local RD=$1 NAME=$(basename $1)
  $P -B tools/mkgslv.py $RD src/g_$NAME.c --base src/gslv_s3_copy.c >> logs/auto.log 2>&1
  [ -f builds/g_${NAME}_sp10/solution.wasm ] || $P -B tools/build.py src/g_$NAME.c g_${NAME}_sp10 "$FLAGS" >> logs/auto.log 2>&1
  local BN=$(cat logs/best_name) BW=$(cat logs/best_wasm) BD=$(cat logs/best_direct) ND=$(direct $RD)
  evalrun $BN $BW; evalrun net_${NAME}_sp10 $A/builds/g_${NAME}_sp10/solution.wasm
  read d3 lo3 hi3 n3 < <(python3 tools/pcmp.py $G/evals/${BN}__v3val.json $G/evals/net_${NAME}_sp10__v3val.json)
  read d1 lo1 hi1 n1 < <(python3 tools/pcmp.py $G/evals/${BN}__v1val.json $G/evals/net_${NAME}_sp10__v1val.json)
  echo "$(date '+%F %H:%M') judge net_${NAME}_sp10 (direct $ND) vs $BN (direct $BD): v3val d=$d3 [$lo3,$hi3] n=$n3 ; v1val d=$d1 [$lo1,$hi1] n=$n1" >> logs/auto.log
  if python3 -c "import sys; sys.exit(0 if $ND < $BD - 0.002 and $d3 < 0.02 and $d1 < 0.02 else 1)"; then
    promote net_${NAME}_sp10 $A/builds/g_${NAME}_sp10/solution.wasm $ND; fi
}
# initial best: A160ft, or autotrain2's last promoted round if its direct error is better
LASTRUN=runs/auto_$(cat logs/auto_last); BN=$(cat logs/best_name)
BD0=0.343; [ -f runs/${BN#net_}/result.json ] 2>/dev/null; R=${BN#net_}; R=${R%_sp10}; [ -f runs/$R/result.json ] && BD0=$(direct runs/$R)
echo $BD0 > logs/best_direct
AD=$(direct $N2/runs/A160ft)
if python3 -c "import sys; sys.exit(0 if $AD < $BD0 - 0.002 else 1)"; then promote nv2_A160ft $N2/builds/A160ft/solution.wasm $AD; fi
PREV=$N2/runs/A160ft; echo $PREV > logs/auto_prev
LAST=$(cat logs/auto_last)
while true; do
  N=$(wc -l < cache/train_meta.jsonl)
  if [ $N -ge $((LAST + STEP)) ]; then
    NAME=at3_$N
    echo "$(date '+%F %H:%M') round $NAME new=$N init=$PREV (lv4)" >> logs/auto.log
    bash $G/refresh_pools.sh >> logs/auto.log 2>&1
    $P -B /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learnvel/lv_prep.py $G/pools/v3val 12 $A/cache/val > logs/prep_val_$N.log 2>&1
    (cd $N2/tools && $P -B lv4.py --name $NAME --init $PREV --list "" --old 0.1 --rev 0.3 --alpha 0.5 --beta 0.5 --lr 1e-3 --epochs 60 > $A/logs/$NAME.log 2>&1)
    grep DONE logs/$NAME.log | cut -c1-300 >> logs/auto.log
    if [ -f $N2/runs/$NAME/best.pt ]; then judge $N2/runs/$NAME; PREV=$N2/runs/$NAME; echo $PREV > logs/auto_prev; fi
    LAST=$N; echo $N > logs/auto_last
  fi
  sleep 1800
done
