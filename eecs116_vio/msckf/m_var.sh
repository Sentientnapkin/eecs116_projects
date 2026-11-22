#!/bin/bash
# m_var.sh NAME [-DFLAG=VAL ...]: host-build msckf/solution.c (or $SRC) and score it on all 171 HF flights, 16 at a time.
# Output in proto/night/hf/out/NAME_cXX.txt (hf_sum.py / hf_robust.py read it); summary line -> msckf/summary.txt
NAME=$1; shift
M=/mnt/c/Users/alexa/Projects/eecs116_vio/msckf
H=/mnt/c/Users/alexa/Projects/eecs116_vio/proto/night/hf
SRC=${SRC:-$M/solution.c}
gcc -O2 -shared -fPIC -I "$HOME/ws_c/runtime/native" "$@" -o "$HOME/ws_c/libms_$NAME.so" "$SRC" -lm || exit 1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source ~/.venv/bin/activate; cd /mnt/c/Users/alexa/Projects/eecs116_vio/proto
for c in $H/chunks/c*; do
  python $M/mscore.py $(cat $c) lib=$HOME/ws_c/libms_$NAME.so 2>&1 | grep -v '^conta:' > $H/out/${NAME}_$(basename $c).txt &
done
wait
echo "$(python $H/hf_sum.py $NAME --line)  $*" >> $M/summary.txt
tail -1 $M/summary.txt
