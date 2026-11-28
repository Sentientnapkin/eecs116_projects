S=/mnt/c/Users/alexa/AppData/Local/Temp/claude/24df673cbfed4a36/7259d14f-b38a-4306-96ea-dba8960ce8af/scratchpad/par
cut -f2 /mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/stage3/twin/twin120.txt | tr -d '\r' | sort -u | sed "s|^|$HOME/data/s3match/|; s|\$|.zip|" > $S/twin120.list
ls ~/data/agile2/*.zip ~/data/agile_a/*.zip ~/data/fast/*.zip > $S/hard.list
head -1 $S/twin120.list > $S/one.list
wc -l $S/*.list; ls $(cat $S/twin120.list) | wc -l
