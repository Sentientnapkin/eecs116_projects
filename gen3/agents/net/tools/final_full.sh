#!/bin/bash
# final_full.sh (2026-11-26): one-shot final net round on ALL stage-3 train flights, after the dataset upload finishes.
# Waits for 'UPLOAD FINISHED' in gen3/logs/up.log and for the HF train cache (driver.py) to stop growing for 1 h,
# lets autotrain3's running round finish, stops autotrain3, then trains from scratch with the netv2 long recipe
# (lv4.py, lr 4e-3 onecycle, 200 epochs, old 0.15, rev 0.3), exports into the A160ft/Ze0 source, builds with the Ze0 flags
# and evaluates 3 replicates on v3val + 1 on v1val vs sw_a1_Ze0 (A160ft + Ze0). GPU 5 only. Log: logs/final_full.log
A=/data/backups/rganapa/Sebastian/gen3/agents/net; N2=/data/backups/rganapa/Sebastian/gen3/agents/netv2
P=/data/backups/rganapa/Sebastian/venv-teacher/bin/python; G=/data/backups/rganapa/Sebastian/gen3
cd $A; L=logs/final_full.log; log() { echo "$(date -u '+%F %H:%M') $*" >> $L; }
log "waiting for UPLOAD FINISHED"
until grep -q "UPLOAD FINISHED" $G/logs/up.log; do sleep 600; done
prev=-1; while true; do n=$(wc -l < cache/train_meta.jsonl); [ $n -eq $prev ] && break; prev=$n; sleep 3600; done
log "cache stable at $n train flights; waiting for autotrain3 round to finish"
while pgrep -f "lv4.py --name at3_" > /dev/null; do sleep 300; done
kill $(cat logs/autotrain.pid) 2>/dev/null; log "stopped autotrain3"
export CUDA_VISIBLE_DEVICES=5 OMP_NUM_THREADS=3
NAME=final_$n
(cd $N2/tools && $P -B lv4.py --name $NAME --init none --list "" --old 0.15 --rev 0.3 --alpha 0.5 --beta 0.5 --lr 4e-3 --epochs 200 > $A/logs/$NAME.log 2>&1)
grep DONE logs/$NAME.log | cut -c1-300 >> $L
[ -f $N2/runs/$NAME/best.pt ] || { log "training failed"; exit 1; }
$P -B tools/mkgslv.py $N2/runs/$NAME src/g_$NAME.c --base $G/agents/sweep/baseA160.c >> $L 2>&1
Z="PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0"
$P -B tools/build.py src/g_$NAME.c g_${NAME}_Ze0 "$Z" >> $L 2>&1
$P -B tools/build.py src/g_$NAME.c g_${NAME}_Ze0_r1 "$Z PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0" >> $L 2>&1
$P -B tools/build.py src/g_$NAME.c g_${NAME}_Ze0_r2 "$Z PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0" >> $L 2>&1
for s in "" _r1 _r2; do tools/ev.sh net_${NAME}_Ze0$s $A/builds/g_${NAME}_Ze0$s/solution.wasm v3val 14 > /dev/null 2>&1; done
tools/ev.sh net_${NAME}_Ze0 $A/builds/g_${NAME}_Ze0/solution.wasm v1val 14 > /dev/null 2>&1
for s in "" _r1 _r2; do echo "rep$s $(python3 tools/pcmp.py $G/evals/sw_a1_Ze0${s}__v3val.json $G/evals/net_${NAME}_Ze0${s}__v3val.json)" >> $L; done
echo "v1val $(python3 tools/pcmp.py $G/evals/sw_a1_Ze0_v1__v1val.json $G/evals/net_${NAME}_Ze0__v1val.json)" >> $L
log "DONE $NAME build builds/g_${NAME}_Ze0 sha $(sha256sum builds/g_${NAME}_Ze0/solution.wasm | cut -c1-8) (d = new - A160ft_Ze0; negative is better)"
