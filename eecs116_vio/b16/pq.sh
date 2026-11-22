# pq.sh build NAME DEFS... | pq.sh run NAME : profile build (serial) / 8-flight profile run (parallel ok)
source ~/.venv/bin/activate
B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16
if [ "$1" = build ]; then
  N=$2; shift 2; D=$(python $B/dedup.py "$@")
  echo "$D" > $B/defs_$N.txt
  cd ~ && SRC=$B/b16p.c FLAGS="-O3 -DPROF" bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh p_$N $D > /dev/null 2>&1 || echo "BUILD FAIL $N"
  cd ~ && SRC=$B/b16s.c FLAGS="-O3" bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh $N $D | grep -v "^check: ok" 
else
  N=$2; rm -rf ~/prof/$N; mkdir -p ~/prof/$N
  cd $B && python prof_run.py ~/ws_m/ms_p_$N.wasm ~/prof/$N 8 8 > /dev/null 2>&1
  echo "$N $(python prof_an.py ~/prof/$N | head -1)   [$(cat $B/defs_$N.txt | cut -c120-)]"
fi
