#!/bin/bash
# hf_var.sh NAME [-DFLAG=VAL ...]: build solution.c with the flags and score it on all 171 HF-set flights (16 at a time).
# Per-chunk diag output -> night/hf/out/NAME_cXX.txt; summary line -> night/hf/summary.txt
NAME=$1; shift
H=/mnt/c/Users/alexa/Projects/eecs116_vio/proto/night/hf
SRC=${SRC:-/mnt/c/Users/alexa/Projects/eecs116_vio/csol/solution/solution.c}
gcc -O2 -shared -fPIC -I "$HOME/ws_c/runtime/native" "$@" -o "$HOME/ws_c/libvio_hf_$NAME.so" "$SRC" -lm || exit 1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 OPENCV_FOR_THREADS_NUM=1
source ~/.venv/bin/activate; cd /mnt/c/Users/alexa/Projects/eecs116_vio/proto
mkdir -p $H/out $H/chunks
if [ ! -f $H/chunks/c00 ]; then ls ~/data/hfcal/*/*.zip | sort > $H/files.txt; split -n r/16 -d $H/files.txt $H/chunks/c; fi
for c in $H/chunks/c*; do
  python diag.py $(cat $c) lib=$HOME/ws_c/libvio_hf_$NAME.so 2>&1 | grep -v '^conta:' > $H/out/${NAME}_$(basename $c).txt &
done
wait
echo "$(python $H/hf_sum.py $NAME --line)  $*" >> $H/summary.txt
tail -1 $H/summary.txt
