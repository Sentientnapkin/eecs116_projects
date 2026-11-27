#!/bin/bash
# swap the long-recipe small-net weights (A2_Lkd, A2_L, E_Lkd) into the two best builds (snace6e1, snace6g27); 3 reps v3val + v1val.
set -e
cd /data/backups/rganapa/Sebastian/gen3/research/swapL
P=/data/backups/rganapa/Sebastian/venv-teacher/bin/python; SN=/data/backups/rganapa/Sebastian/gen3/agents/smallnet; AN=/data/backups/rganapa/Sebastian/gen3/agents/anchors
G=/data/backups/rganapa/Sebastian/gen3
(cd $SN && $P -B tools/mkgsn.py runs/A2_kd $G/research/swapL/x_A2_kd.c > /dev/null)
for R in A2_Lkd A2_L; do
  (cd $SN && $P -B tools/mkgsn.py runs/$R $G/research/swapL/x_$R.c > /dev/null)
  diff x_A2_kd.c x_$R.c > $R.patch || true
  cp $AN/base_sn.c base_$R.c; patch -s base_$R.c < $R.patch || grep -c "^- /\* GENERATED" base_$R.c.rej
done
E1="PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0 SN=1 NS_GCOST=1 MAX_CLONES=8 MAX_OBS=10 AN_ACE=1 AN_DTH=4.0 AN_CEF=6 EDGE=1 EDGE_MYTH=10.0"
G27="PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0 SN=1 NS_GCOST=1 MAX_CLONES=8 MAX_OBS=10 AN_ACE=1 AN_DTH=4.0 AN_CEF=6 GOV_B=2.7e6"
R1="PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0"; R2="PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0"
mkb() { $P $AN/mk.py $1 "$2" $3 | tail -1 > builds_$1.txt; mkdir -p wasm; cp $AN/builds/$1/solution.wasm wasm/$1.wasm; }
for R in A2_Lkd A2_L; do for C in e1 g27; do V=$E1; [ $C = g27 ] && V=$G27
  mkb swL_${C}_$R "$V" base_$R.c; mkb swL_${C}_${R}_r1 "$V $R1" base_$R.c; mkb swL_${C}_${R}_r2 "$V $R2" base_$R.c; done; done
ev() { (cd $G && ../venv-teacher/bin/python -B evalpool.py $1 $2 pools/$3 8 > /dev/null 2>&1); }
for C in e1 g27; do REF=snace6e1; [ $C = g27 ] && REF=snace6g27
  for s in "" _r1 _r2; do ev $REF$s $AN/builds/$REF$s/solution.wasm v3val; done; ev $REF $AN/builds/$REF/solution.wasm v1val
  for R in A2_Lkd A2_L; do for s in "" _r1 _r2; do ev swL_${C}_$R$s $PWD/wasm/swL_${C}_$R$s.wasm v3val; done; ev swL_${C}_$R $PWD/wasm/swL_${C}_$R.wasm v1val; done
done
touch DONE
