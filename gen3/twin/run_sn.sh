cd /data/backups/rganapa/Sebastian/gen3/twin
for pool in /data/backups/rganapa/Sebastian/gen3/pools/twin120 /data/backups/rganapa/Sebastian/gen3/pools/twin24 /data/backups/rganapa/Sebastian/gen3/twin/pools/v3val120; do
 /data/backups/rganapa/Sebastian/venv-teacher/bin/python seed_cache.py tw_snace6e1 /data/backups/rganapa/Sebastian/gen3/agents/anchors/builds/snace6e1/solution.wasm $pool; (cd /data/backups/rganapa/Sebastian/gen3 && /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B evalpool.py tw_snace6e1 /data/backups/rganapa/Sebastian/gen3/agents/anchors/builds/snace6e1/solution.wasm $pool 14) > state/eval_snace6e1_$(basename $pool).log 2>&1
done
/data/backups/rganapa/Sebastian/venv-teacher/bin/python calib.py > calib.log 2>&1; /data/backups/rganapa/Sebastian/venv-teacher/bin/python reweight.py > reweight.log 2>&1; touch state/SN.done
