#!/bin/bash
# calib_run.sh: evaluate probe_release.wasm and probe_debug.wasm on a fixed set of local episodes, one process each.
source "$HOME/.venv/bin/activate"
OUT=$HOME/probe_calib; rm -rf $OUT; mkdir -p $OUT
EPS="$(ls ~/data/ho240/*.zip | sed -n '1~30p') $(ls ~/data/mixed/*.zip | head -2)"
echo "$EPS" | tr ' ' '\n' > $OUT/list
i=0
for e in $EPS; do
  for b in release debug; do
    ( cd $OUT && mkdir -p ${b}_$i && cd ${b}_$i && /usr/bin/time -f "%e s" viobench evaluate ~/ws_probe/probe_$b.wasm $e > log.txt 2> time.txt ) &
  done
  i=$((i+1))
done
wait
cat $OUT/*/time.txt | tr '\n' ' '; echo
