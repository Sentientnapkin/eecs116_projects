cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model
for S in 0 16 17 18 22 28 31 33 35 36; do W=1 bash learnvel/bp.sh gb$S lvg_bench.c "LV_GRAV=1 LV_GT0=1000 LV_GBENCH=$S" /data/backups/rganapa/Sebastian/tmp/lv_pools/one >/dev/null
/data/backups/rganapa/Sebastian/venv-teacher/bin/python -c "
import numpy as np,glob;f=np.load(glob.glob('../results/single_model/lv_gb$S/one/*/*/report/logs/*/fuel.npy')[0]);print($S, f[0])"; done
