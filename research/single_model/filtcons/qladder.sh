#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/filtcons
H="$(cat hm40.defs)"
export W=40
for r in "" _r1 _r2; do
 ./bp.sh L6$r fc.c "$H GOV_B=5.4e6" /data/backups/rganapa/Sebastian/tmp/st_pools/st2dev /data/backups/rganapa/Sebastian/tmp/st_pools/st2conf
 ./bp.sh L8$r fc.c "$H GOV_B=7.2e6 GOV_UMAX=50" /data/backups/rganapa/Sebastian/tmp/st_pools/st2dev /data/backups/rganapa/Sebastian/tmp/st_pools/st2conf
 ./bp.sh L12$r fc.c "$H GOV_B=11e6 GOV_UMAX=60" /data/backups/rganapa/Sebastian/tmp/st_pools/st2dev /data/backups/rganapa/Sebastian/tmp/st_pools/st2conf
 ./bp.sh L16$r fc.c "$H GOV_B=14.5e6 GOV_UMAX=80" /data/backups/rganapa/Sebastian/tmp/st_pools/st2dev /data/backups/rganapa/Sebastian/tmp/st_pools/st2conf
done
for n in m40s1 m40s1_r1 m40s1_r2; do for p in st2dev st2conf; do ./rp.sh B$n /data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model/ap_$n/solution.wasm /data/backups/rganapa/Sebastian/tmp/st_pools/$p 40; done; done
for n in 1 2; do for p in st2dev st2conf; do ./rp.sh b17x_r$n /data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model/li_gnp_r$n/solution.wasm /data/backups/rganapa/Sebastian/tmp/st_pools/$p 40; done; done
./rp.sh hm40 /data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model/fc_chk/solution.wasm /data/backups/rganapa/Sebastian/tmp/st_pools/st1dev 40; ./rp.sh hm40 /data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model/fc_chk/solution.wasm /data/backups/rganapa/Sebastian/tmp/st_pools/st1conf 40
