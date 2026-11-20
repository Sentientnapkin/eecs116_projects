"""Load every final zip with the repo's reader and re-run the generation gates (frames, consistency, finite, stalled, truth integration)."""
import sys, glob, json, os
sys.path.insert(0, '/data/backups/rganapa/Sebastian/eecs116_projects/research')
from concurrent.futures import ProcessPoolExecutor
import numpy as np
def chk(p):
    try:
        from common import Flight
        from native_campaign import audit, truth_integration_error
        from viobench.tools.datasets.storage import read_episode
        e = read_episode(p); e.check_consistency()
        f = Flight(p); a = audit(f)
        side = json.load(open(p[:-4].replace('/final/', '/bench/') + '.json'))
        ok = (a['frames'] == 1200 and np.isfinite(f.v_body).all() and np.isfinite(f.imu).all() and a['truth_integration_rms_m'] <= .05 and not a['stalled']
              and abs(a['travel_m'] - side['audit']['travel_m']) < 0.02)
        return os.path.basename(p), bool(ok), a['frames'], a['truth_integration_rms_m'], a['stalled']
    except Exception as ex:
        return os.path.basename(p), False, repr(ex)[:200], None, None
if __name__ == '__main__':
    ps = sorted(glob.glob('/data/backups/rganapa/Sebastian/gen/raw-holdout/final/*.zip'))
    with ProcessPoolExecutor(16) as ex: r = list(ex.map(chk, ps))
    bad = [x for x in r if not x[1]]
    print(len(r), 'checked;', len(bad), 'bad', bad[:5], 'max integ rms', max(x[3] for x in r if x[3] is not None))
