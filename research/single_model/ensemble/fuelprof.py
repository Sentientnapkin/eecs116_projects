"""T4: per-frame fuel profile of GSLV-family runs and K-back-end peak estimates (shared front end, optional time slicing).
python fuelprof.py  -> prints tables, writes fuelprof.json
Model (ESTIMATE): frame fuel f = FE + BE. FE (shareable: pyramid + KLT + detection [+ net steps]) is a constant guess
FE in {0.6, 0.9} M (fuelpush/NOTES.md zero-row frames 0.87-0.90 M = klt .22 pyr .21 detect .175 priors .146 map .03 prop .03).
Member back-end work BE_k(t) = max(f_k(t) - FE, 0) taken from a DIFFERENT run on the same flight (real chaos-decorrelated
timing of clone/update spikes). Time slicing: primary member served on its frame; secondary back-end work queued FIFO and must
finish within D frames; capacity C per frame; find min C."""
import glob, os, json
import numpy as np

R = '/data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model/'
FAM = {'J': ['lj_ajc', 'lj_ajc_r1', 'lj_ajc_r2'], 'V': ['lv_glNP', 'lv_glNP_r1', 'lv_glNP_r2'], 'M': ['lv_gl', 'lv_gl_r1', 'lv_gl_r2']}


def fuel(run, pool):
    out = {}
    for f in glob.glob(R + '%s/%s/*/*/report/logs/*/fuel.npy' % (run, pool)):
        out[f.split('/report/')[0].split('/')[-1]] = np.load(f).astype(float)
    return out


def minC(f1, others, FE, D):
    """min capacity C so primary f1 is served each frame and secondary work (sum of others - FE) finishes within D frames."""
    w = sum(np.maximum(o - FE, 0) for o in others)
    n = len(f1); cw = np.cumsum(w)
    lo, hi = f1.max(), f1.max() + w.max() * 1.0 + 1
    for _ in range(40):
        C = 0.5 * (lo + hi)
        cc = np.cumsum(np.maximum(C - f1, 0))
        idx = np.minimum(np.arange(n) + D, n - 1)
        # demand-bound test (EDF = FIFO here): for all a<=s, W[a..s] <= cap[a..s+D]
        W0 = np.concatenate([[0], cw[:-1]]); C0 = np.concatenate([[0], cc[:-1]])
        m = np.arange(n) + D <= n - 1   # work arriving in the last D frames is not required to finish (flight ends)
        ok = np.all((cw - cc[idx] <= np.minimum.accumulate(W0 - C0) + 1e-6)[m])
        if ok: hi = C
        else: lo = C
    return hi


if __name__ == '__main__':
    res = {}
    for pool in ['st2conf', 'fconf']:
        F = {r: fuel(r, pool) for fam in FAM.values() for r in fam}
        names = sorted(set.intersection(*[set(v) for v in F.values()]))
        res[pool] = {'n': len(names)}
        print('\n=== pool', pool, 'flights', len(names))
        print('%-11s %7s %7s %7s %7s %7s %7s %8s %8s %9s' % ('run', 'peak', 'p99.9', 'p99', 'p95', 'median', 'mean', 'fr<.5pk', 'fr<1.0M', 'slack/pk'))
        for r in F:
            a = np.concatenate([F[r][n] for n in names]); pk = a.max()
            pfl = np.array([F[r][n].max() for n in names])
            row = dict(peak=pk, p999=np.percentile(a, 99.9), p99=np.percentile(a, 99), p95=np.percentile(a, 95), med=np.median(a), mean=a.mean(),
                       frac_below_half=(a < 0.5 * pk).mean(), frac_below_1M=(a < 1e6).mean(), slack=(pk - a).mean() / pk,
                       flight_peak_med=np.median(pfl), argmax_frames=[int(np.argmax(F[r][n])) for n in names][:0])
            res[pool][r] = row
            print('%-11s %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f %8.2f %8.2f %9.2f  flight-peak median %.2f' % (
                r, pk / 1e6, row['p999'] / 1e6, row['p99'] / 1e6, row['p95'] / 1e6, row['med'] / 1e6, row['mean'] / 1e6,
                row['frac_below_half'], row['frac_below_1M'], row['slack'], np.median(pfl) / 1e6))
        # where is the peak? frame-index distribution of per-flight argmax for J
        am = np.array([np.argmax(F['lj_ajc'][n]) for n in names])
        print('lj_ajc per-flight argmax frame: <20: %.2f, 20-60 %.2f, later %.2f; frames>=3.5M per flight (mean) %.1f' % (
            (am < 20).mean(), ((am >= 20) & (am < 60)).mean(), (am >= 60).mean(),
            np.mean([(F['lj_ajc'][n] >= 3.5e6).sum() for n in names])))
        # coincidence of spikes across replicas: corr of per-frame fuel between r0 and r1 (same flight)
        cs = [np.corrcoef(F['lj_ajc'][n], F['lj_ajc_r1'][n])[0, 1] for n in names]
        print('per-frame fuel corr J r0 vs r1 (median over flights) %.2f' % np.median(cs))
        res[pool]['fuel_corr_J'] = float(np.median(cs))
        # K back ends
        combos = {'J+J': ('lj_ajc', ['lj_ajc_r1']), 'J+J+J': ('lj_ajc', ['lj_ajc_r1', 'lj_ajc_r2']), 'J+M': ('lj_ajc', ['lv_gl']),
                  'J+J+M': ('lj_ajc', ['lj_ajc_r1', 'lv_gl']), 'J+M+M': ('lj_ajc', ['lv_gl', 'lv_gl_r1'])}
        print('%-7s %4s  %s' % ('combo', 'FE', '  global C/peak1 for D=0,1,2,5,10,20,40 frames   [no sharing D=0]'))
        for cn, (p, oth) in combos.items():
            for FE in [0.6e6, 0.9e6]:
                pk1 = max(F[p][n].max() for n in names)
                rowC = []
                for D in [0, 1, 2, 5, 10, 20, 40]:
                    rowC.append(max(minC(F[p][n], [F[o][n] for o in oth], FE, D) for n in names) / pk1)
                nosh = max(minC(F[p][n], [F[o][n] for o in oth], 0, 0) for n in names) / pk1
                res[pool]['%s_FE%.1f' % (cn, FE / 1e6)] = dict(ratio=rowC, noshare=nosh, pk1=pk1)
                print('%-7s %.1f  %s   [%.2f]' % (cn, FE / 1e6, ' '.join('%.2f' % x for x in rowC), nosh))
    json.dump(res, open(os.path.dirname(os.path.abspath(__file__)) + '/fuelprof.json', 'w'), default=float)
