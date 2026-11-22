cd ~
B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16
bld() { n=$1; shift; SRC=$B/b16s.c FLAGS=-O3 bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh $n $(python3 $B/dedup.py "$@") | tr '\n' ' '; echo $n; echo "$@" > $B/defs_$n.txt; }
bld e6u $(cat $B/e6.defs) LC_SLICE=0
bld e7u $(cat $B/defs_e7.txt) LC_SLICE=0
cd ~/ws_m; for n in e6u e7u; do J=10 bash $B/w_eval.sh $n hf; done
