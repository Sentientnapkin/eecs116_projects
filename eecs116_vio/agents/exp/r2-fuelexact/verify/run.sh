set -e
source ~/.venv/bin/activate
S=/mnt/c/Users/alexa/AppData/Local/Temp/claude/24df673cbfed4a36/7259d14f-b38a-4306-96ea-dba8960ce8af/scratchpad/r2v
A=~/data/agents
ls $A/vpar_twin120/*.npz | wc -l; ls $A/vpar_hard/*.npz $A/vpar_black/*.npz $A/vpar_blank/*.npz $A/vpar_dark/*.npz | wc -l
exec 9> "$HOME/data/.heavy.lock"; echo "waiting for lock"; flock 9; echo "lock $(date +%T)"
job() { OUT=$1; MODE=$2; C=$3; L=$4; rm -rf $OUT; mkdir -p $OUT; split -n r/8 -d "$L" "$OUT/part_"
  for p in $OUT/part_*; do ( cd /tmp && python -I $S/vpar2.py $OUT $MODE $C $(cat $p) > $p.log 2>&1 ) & done; wait
  grep -L . $OUT/part_*.log >/dev/null; grep -h -E "Error|Traceback" $OUT/part_*.log | head -3 || true; }
job $A/r2v_twin120 plain $A/vpar_twin120 $S/twin120.list
echo "twin120 done $(date +%T)"
job $A/r2v_hard plain $A/vpar_hard $S/hard.list
for m in black blank dark; do job $A/r2v_$m $m $A/vpar_$m $S/pert.list; done
echo "all done $(date +%T)"
T=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/stage3/twin/twin120.txt
tr -d '\r' < $T > /tmp/twin120_lf.txt
echo "=== twin120"; python -I $S/../par/ana.py $A/r2v_twin120 /tmp/twin120_lf.txt
for d in hard black blank dark; do echo "=== $d"; python -I $S/../par/ana.py $A/r2v_$d; done
