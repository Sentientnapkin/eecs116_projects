#!/bin/bash
# Oracle-driven sweep on snace6e1 (i3 findings): net latency (AN_NETB extra net budget), net rate (LV_PERIOD), yaw/gyro consistency
# (GYRO_NOISE, GYRO_BIAS_WALK). Screen 1 run on pools/v3val; auto 2 replicates + v1val for d < -0.02; then a combo of the best per group.
cd /data/backups/rganapa/Sebastian/gen3/research/osweep
P=/data/backups/rganapa/Sebastian/venv-teacher/bin/python; AN=/data/backups/rganapa/Sebastian/gen3/agents/anchors; G=/data/backups/rganapa/Sebastian/gen3
E1="PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0 SN=1 NS_GCOST=1 MAX_CLONES=8 MAX_OBS=10 AN_ACE=1 AN_DTH=4.0 AN_CEF=6 EDGE=1 EDGE_MYTH=10.0"
R1="PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0"; R2="PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0"
ev() { [ -f $G/evals/$1__$3.json ] && [ "$(python3 -c "import json;print(len(json.load(open('$G/evals/$1__$3.json'))))")" -ge 250 ] && [ $3 = v3val ] && return; (cd $G && $P -B evalpool.py $1 $2 pools/$3 8 > /dev/null 2>&1); }
bld() { [ -f $AN/builds/$1/solution.wasm ] || $P $AN/mk.py $1 "$2" $PWD/base_sw.c > /dev/null; echo $AN/builds/$1/solution.wasm; }
d() { python3 $G/agents/net/tools/pcmp.py $G/evals/snace6e1$2__v3val.json $G/evals/$1__v3val.json | cut -d' ' -f1; }
pk() { python3 -c "import json;print(max(r['peak'] for r in json.load(open('$G/evals/$1__v3val.json')) if r.get('peak')))"; }
# reference (same sha as anchors build -> cached)
bld osw_ref "$E1" > /dev/null; ev osw_ref $AN/builds/osw_ref/solution.wasm v3val
declare -A V=( [nb3]="AN_NETB=0.3e6" [nb6]="AN_NETB=0.6e6" [nb10]="AN_NETB=1.0e6" [lp6]="LV_PERIOD=6" [lp8]="LV_PERIOD=8" [lp14]="LV_PERIOD=14"
  [gn15]="GYRO_NOISE=0.105" [gn20]="GYRO_NOISE=0.14" [gw2]="GYRO_BIAS_WALK=0.0012" [gw4]="GYRO_BIAS_WALK=0.0024" )
for k in nb3 nb6 nb10 lp6 lp8 lp14 gn15 gn20 gw2 gw4; do w=$(bld osw_$k "$E1 ${V[$k]}"); ev osw_$k $w v3val
  echo -e "$k\t${V[$k]}\td=$(python3 $G/agents/net/tools/pcmp.py $G/evals/osw_ref__v3val.json $G/evals/osw_${k}__v3val.json)\tpeak=$(pk osw_$k)" >> results.tsv; done
# replicates for promising
for k in nb3 nb6 nb10 lp6 lp8 lp14 gn15 gn20 gw2 gw4; do dd=$(grep -P "^$k\t" results.tsv | sed 's/.*d=\([-0-9.]*\).*/\1/')
  if python3 -c "import sys;sys.exit(0 if float('$dd')<-0.02 else 1)"; then
    for r in 1 2; do RR=$R1; [ $r = 2 ] && RR=$R2; w=$(bld osw_${k}_r$r "$E1 ${V[$k]} $RR"); ev osw_${k}_r$r $w v3val
      wr=$(bld osw_ref_r$r "$E1 $RR"); ev osw_ref_r$r $wr v3val; done
    ev osw_$k $AN/builds/osw_$k/solution.wasm v1val; ev osw_ref $AN/builds/osw_ref/solution.wasm v1val
    m=$(python3 - <<P
import json
def L(n): return {r['id']:r['ate'] for r in json.load(open('$G/evals/'+n+'__v3val.json')) if r.get('ate') is not None}
a=[L('osw_ref'),L('osw_ref_r1'),L('osw_ref_r2')]; b=[L('osw_$k'),L('osw_${k}_r1'),L('osw_${k}_r2')]
ids=set.intersection(*[set(x) for x in a+b]); import statistics as s
print(round(s.mean(sum(x[i] for x in a)/3 for i in ids),4), round(s.mean(sum(x[i] for x in b)/3 for i in ids),4), len(ids))
P
)
    echo -e "REP3\t$k\tref/new/n=$m\tv1val d=$(python3 $G/agents/net/tools/pcmp.py $G/evals/osw_ref__v1val.json $G/evals/osw_${k}__v1val.json)" >> results.tsv
  fi; done
touch DONE
