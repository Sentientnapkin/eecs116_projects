# drive.sh OUT MODE LISTFILE : run vpar.py in J parallel parts under the heavy-job lock
set -e
source ~/.venv/bin/activate
S=/mnt/c/Users/alexa/AppData/Local/Temp/claude/24df673cbfed4a36/7259d14f-b38a-4306-96ea-dba8960ce8af/scratchpad/par
OUT=$1; MODE=$2; L=$3; J=${J:-8}
rm -rf $OUT; mkdir -p $OUT
exec 9> "$HOME/data/.heavy.lock"; echo "waiting for lock"; flock 9; echo "lock $(date +%T)"
split -n r/$J -d "$L" "$OUT/part_"
for p in $OUT/part_*; do ( cd /tmp && python -I $S/vpar.py $OUT $MODE $(cat $p) > $p.log 2>&1 ) & done
wait; echo "done $(date +%T)"; cat $OUT/part_*.log | sort
