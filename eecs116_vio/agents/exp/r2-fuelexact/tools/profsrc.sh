#!/bin/bash
# profsrc.sh SRC.c TAG : active view -> PROF instrumentation -> build -> profile the 6 flights -> an.py summary
set -e
H=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/exp/r2-fuelexact
S=$1; T=$2; mkdir -p $H/prof
bash $H/tools/pp.sh $S $H/prof/active_$T.txt 2>/dev/null
python3 $H/tools/mkprof.py $S $H/prof/active_$T.txt $H/prof/p0_$T.c
python3 $H/tools/mkprof2.py $H/prof/p0_$T.c $H/prof/p_$T.c
bash $H/bld.sh $H/prof/p_$T.c $H/prof/p_$T.wasm -DPROF "$SHELLF"
rm -rf ~/r2fe/prof_$T; bash $H/tools/prof.sh $H/prof/p_$T.wasm ~/r2fe/prof_$T ${FL:-s3v3te-ro-9300648 s3v3te-ro-9300784 s3v3te-ro-9300867 s3va-ro-9010255 s3v3te-wa-h9500246 s3te-fo-9011115} > /dev/null
source ~/.venv/bin/activate; python $H/tools/an.py ~/r2fe/prof_$T $H/prof/p_$T.c.ids 10
