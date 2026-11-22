B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16/build.sh
bash $B b16q.c q0
bash $B b16q.c q5 MAX_CLONES=5
bash $B b16q.c q5m MAX_CLONES=5 MAP_SPREAD=1
bash $B b16q.c q5ml MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5
