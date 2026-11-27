#!/bin/bash
# qd.sh: queue daemon; lines in logs/queue.txt: "NAME SRC DEFINES..." (build + eval v3val) ; pools via POOLS=... prefix? no: v3val only unless line starts with "@v1 "
S=/data/backups/rganapa/Sebastian/gen3/agents/smallnet; P=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
touch $S/logs/queue.txt $S/logs/done.txt
while true; do
  line=$(grep -vxF -f $S/logs/done.txt $S/logs/queue.txt | grep -v '^$' | head -1)
  if [ -z "$line" ]; then sleep 30; continue; fi
  set -- $line
  pools=v3val; if [ "$1" == "@v1" ]; then pools=v1val; shift; elif [ "$1" == "@both" ]; then pools="v3val v1val"; shift; fi
  N=$1; SRC=$2; shift 2
  if [[ $SRC == *.wasm ]]; then W=$SRC; else
    out=$(cd $S/tools && $P -B build.py $SRC $N "$*" 2>&1); W=$S/builds/$N/solution.wasm; echo "$(date +%H:%M) built $N $out" >> $S/logs/qd.log; fi
  bash $S/tools/ev.sh $N $W $pools
  echo "$(date +%H:%M) done $N" >> $S/logs/qd.log
  echo "$line" >> $S/logs/done.txt
done
