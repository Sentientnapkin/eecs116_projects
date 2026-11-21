"""Per-flight starvation diagnosis (analysis only; truth used for scoring/attribution, never in the estimator).
  python -B research/single_model/atepush/dg.py RUNDIR OUT.json [workers]
RUNDIR = research/results/single_model/apf_X/eval/X-sha (TC_LOG=1 build: stderr 'D ...' lines per frame).
Per flight: ATE, ATE after removing the best rigid translation, and oracle counterfactuals that zero the position-error
increments (velocity error) in frames of a class: starved (accepted MSCKF features in the last 1 s below a threshold),
high Pv, low live tracks; plus share of frames in each class."""
import sys, glob, json, os, re
import numpy as np
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, '.')
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
POOL = '/data/backups/rganapa/Sebastian/tmp/fresh_pool'
RX = re.compile(r'D f=(\d+) t=([\d.]+) live=(\d+) used=\d+ u20=\d+ att=(\d+) gate=(\d+) tri=(\d+) nis=([\d.]+) .* fire=(\d+) Pv=([\d.]+)')

def one(d):
    ep = os.path.basename(d)
    try:
        est = glob.glob(f'{d}/report/logs/*/estimate.tum')[0]; se = est.replace('estimate.tum', 'stderr.txt')
        e = read_episode(f'{POOL}/{ep}.zip', frames='none')
        t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state()); n = len(t)
        E = fill_missing_states(load_estimates(est, t))
        Tg, Te = poses_to_matrices(S), poses_to_matrices(E)
        err = Te[:, :3, 3] - Tg[:, :3, 3]
        rms = lambda x: float(np.sqrt(np.mean(np.sum(x ** 2, 1))))
        ate = rms(err)
        live = np.zeros(n); acc = np.zeros(n); pv = np.zeros(n); fire = np.zeros(n)
        for line in open(se):
            m = RX.match(line)
            if not m: continue
            f = int(m.group(1)) - 1
            if 0 <= f < n:
                live[f] = int(m.group(3)); acc[f] = int(m.group(4)) - int(m.group(5)) - int(m.group(6)); pv[f] = float(m.group(9)); fire[f] = int(m.group(8))
        acc1 = np.convolve(acc, np.ones(20), 'full')[:n]   # accepted features in the last 1 s (causal)
        inc = np.diff(err, axis=0, prepend=err[:1])
        def cf(mask):  # zero increments in mask frames
            r = np.cumsum(np.where(mask[:, None], 0, inc), 0); return rms(r)
        out = dict(episode=ep, ate=ate, ate_mt=rms(err - err.mean(0)), start='mid' if ep.startswith('fastmid') else 'static',
                   e5=float(np.linalg.norm(err[min(100, n - 1)])), nfire=int((fire > 0).sum()))
        tt = t - t[0]
        for name, mask in (('acc0', acc1 == 0), ('acc3', acc1 < 3), ('acc10', acc1 < 10), ('acc20', acc1 < 20),
                           ('live10', live < 10), ('live20', live < 20), ('pv10', pv > 0.10), ('pv15', pv > 0.15), ('pv25', pv > 0.25),
                           ('first5', tt < 5)):
            out['f_' + name] = float(mask.mean()); out['cf_' + name] = cf(mask)
        return out
    except Exception as ex:
        return dict(episode=ep, error=str(ex))

if __name__ == '__main__':
    run, outp = sys.argv[1], sys.argv[2]; w = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    dirs = sorted(d for d in glob.glob(run + '/*') if os.path.isdir(d + '/report'))
    with ProcessPoolExecutor(w) as ex: rows = list(ex.map(one, dirs, chunksize=4))
    json.dump(rows, open(outp, 'w')); print(len(rows), sum('error' in r for r in rows))
