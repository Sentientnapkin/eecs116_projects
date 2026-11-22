import json, sys, numpy as np
R = [r for r in json.load(open(sys.argv[1])) if r['ep'] == sys.argv[2]]
import glob
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.storage import read_episode
tw = np.loadtxt(glob.glob(f'{sys.argv[3]}/*/{sys.argv[2]}/report/logs/*/twist.txt')[0])
S = np.asarray(read_episode(f'{sys.argv[4]}/{sys.argv[2]}.zip', frames='none').ground_truth_state())
est = np.loadtxt(glob.glob(f'{sys.argv[3]}/*/{sys.argv[2]}/report/logs/*/estimate.tum')[0])
step = int(sys.argv[5]) if len(sys.argv) > 5 else 4
for r in R[::step]:
    f = r['f']; vt = S[f, 7:10]; ve = tw[f, 1:4]
    pe = np.linalg.norm(est[f, 1:4] - S[f, :3])
    print('t %5.1f |vt| %.2f |vf| %.2f |vnet| %.2f ferr %.2f nerr %.2f cos(vf,vt) %+.2f live %3.0f Pv %.2f posErr %.2f' % (f * 0.05, np.linalg.norm(vt), np.linalg.norm(ve), np.linalg.norm(r['mu']), r['ferr'], r['nerr'], ve @ vt / (np.linalg.norm(ve) * np.linalg.norm(vt) + 1e-9), r['live'], r['pv'], pe))
