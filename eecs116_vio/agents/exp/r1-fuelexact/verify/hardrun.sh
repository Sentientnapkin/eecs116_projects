S=/mnt/c/Users/alexa/AppData/Local/Temp/claude/24df673cbfed4a36/7259d14f-b38a-4306-96ea-dba8960ce8af/scratchpad/par
L=$S/twin120.list
( grep -- "-ro-" $L | awk 'NR%15==1'; grep -- "-wa-" $L | awk 'NR%15==1'; grep -- "-fo-" $L | awk 'NR%15==1' ) > $S/pert.list
wc -l $S/pert.list
source ~/.venv/bin/activate
J=8 bash $S/drive.sh ~/data/agents/vpar_hard plain $S/hard.list | tail -3
for m in black blank dark; do J=8 bash $S/drive.sh ~/data/agents/vpar_$m $m $S/pert.list | tail -2; done
for d in hard black blank dark; do echo "=== $d"; python -I $S/ana.py ~/data/agents/vpar_$d; done
