"""stab.py results.json [results2.json] : per-case table (completed, failures, filled, mean ATE, ATE/identity, worst, peak/p95 fuel)."""
import json, sys, numpy as np
def load(p):
    R = json.load(open(p)); D = {}
    for r in R: D.setdefault(r['case'], {})[r['ep']] = r
    return D
A = load(sys.argv[1]); B = load(sys.argv[2]) if len(sys.argv) > 2 else None
print('%-15s %3s %5s %4s %6s %7s %6s %6s %7s %6s %6s' % ('case', 'n', 'compl', 'fill', 'err', 'ATE', 'base', 'ident', 'worst', 'peakM', 'p95M') + ('   | B: compl fill ATE worst peakM' if B else ''))
for c in A:
    rs = [r for r in A[c].values()]
    ok = [r for r in rs if 'error' not in r]
    err = len(rs) - len(ok)
    ate = np.array([r['ate'] for r in ok]); idn = np.array([r['ident'] for r in ok])
    base = np.array([A['base'][r['ep']]['ate'] for r in ok if r['ep'] in A.get('base', {})]) if 'base' in A else np.array([np.nan])
    line = '%-15s %3d %5d %4d %6d %7.3f %6.3f %6.3f %7.2f %6.2f %6.2f' % (c, len(rs), sum(r['completed'] for r in ok), sum(r['filled'] for r in ok), err, ate.mean() if len(ate) else np.nan,
        base.mean() if len(base) else np.nan, idn.mean() if len(idn) else np.nan, ate.max() if len(ate) else np.nan, max(r['peak'] for r in ok) / 1e6 if ok else np.nan, max(r['p95'] for r in ok) / 1e6 if ok else np.nan)
    if B and c in B:
        ob = [r for r in B[c].values() if 'error' not in r]; ab = np.array([r['ate'] for r in ob])
        line += '   | %3d %4d %7.3f %7.2f %6.2f' % (sum(r['completed'] for r in ob), sum(r['filled'] for r in ob), ab.mean(), ab.max(), max(r['peak'] for r in ob) / 1e6)
    print(line)
    for r in ok:
        if not r['completed']: print('      FAIL', r['ep'], r['failure'])
    for r in rs:
        if 'error' in r: print('      ERR', r['ep'], r['error'][-300:].replace('\n', ' '))
