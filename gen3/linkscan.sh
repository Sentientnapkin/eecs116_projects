cd /data/backups/rganapa/Sebastian
for d in baselines gen eecs116_projects/research tmp; do timeout 500 find $d -type l -printf '%p -> %l\n' 2>/dev/null | grep -E 'raw-(rerender|fast|bench|servertail|speed|learnvel-st3)|gen/raw/|raw/(train|dev|test)' ; done > gen3/links.txt
for d in raw raw-fast raw-bench raw-servertail raw-speed raw-learnvel-st3 raw-rerender; do find gen/$d -name '*.zip' -type f -links +1 -printf "$d %n\n"; done | sort | uniq -c > gen3/hard.txt; echo done >> gen3/hard.txt
