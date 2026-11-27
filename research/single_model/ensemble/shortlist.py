"""Cross-pool shortlist of candidate ensembles (reads comp_summary_POOL.json written by comp_report.py).
Absolute ATE vs the deployed single build LJA (GSLV-linejac arith, server 0.633 @ 4.2 M) and an ESTIMATED score delta using the
tier1m area formula: d = -2.24*ln(ATE_ens/ATE_LJA) + 0.28*log2(peak_LJA/peak_ens), peak_ens = sum of member peaks (upper bound)."""
import json, os, math
H = os.path.dirname(os.path.abspath(__file__))
POOLS = ['st2dev', 'st2conf', 'st3', 'st1dev', 'st1conf', 'fdev', 'fconf']
PEAK = {'GSLV': 6.8, 'LJA': 4.8, 'LJB4': 4.1, 'GSLM': 7.0, 'B17X': 16.1, 'RSOFT': 4.0, 'EDGE': 5.4, 'KV1': 4.0, 'SLPMM': 7.1, 'LYPK': 7.0}
CAND = [('rep', 'GSLV', 3), ('rep', 'LJA', 3), ('rep2', 'LJA', 2), ('rep2', 'GSLV', 2), ('rep', 'LJB4', 3),
        ('set', 'GSLV+LJA', 2), ('set', 'GSLV+GSLM', 2), ('set', 'LJA+GSLM', 2), ('set', 'LJA+LJB4', 2), ('set', 'GSLV+B17X', 2),
        ('set', 'LJA+SLPMM', 2), ('set', 'GSLV+LJB4+GSLM', 3), ('set', 'LJA+LJB4+GSLM', 3), ('set', 'GSLV+LJA+GSLM', 3),
        ('set', 'GSLV+GSLM+B17X', 3), ('set', 'LJA+GSLM+B17X', 3), ('set', 'RSOFT+B17X+EDGE', 3), ('set', 'RSOFT+B17X+EDGE+KV1', 4)]
S = {p: json.load(open(H + '/comp_summary_%s.json' % p)) for p in POOLS if os.path.exists(H + '/comp_summary_%s.json' % p)}
out = []
print('%-22s %s' % ('candidate', ' '.join('%-27s' % p for p in S)))
print('%-22s %s' % ('', ' '.join('%-27s' % 'causal(vsLJA) hind | estArea' for p in S)))
for kind, name, K in CAND:
    cells = []; rec = {'cand': '%s:%s' % (kind, name)}
    for p, s in S.items():
        if 'LJA' not in s['single']: cells.append('%-27s' % '-'); continue
        lja = s['single']['LJA']['mean']
        if kind.startswith('rep'):
            r = s['rep'].get(name)
            if not r: cells.append('%-27s' % '-'); continue
            ca = r['mean2'] if kind == 'rep2' else min(r['mean'], r['median'], r['medoid']); hi = r['hind'] if kind == 'rep' else float('nan')
            peak = PEAK[name] * K
        else:
            row = [x for x in s['sets'] if x['set'] == name]
            if not row:
                cand = [x for x in s['sets'] if sorted(x['set'].split('+')) == sorted(name.split('+'))]
                row = cand
            if not row: cells.append('%-27s' % '-'); continue
            row = row[0]; ca = row[row['causal_best']]; hi = row['hind']; peak = sum(PEAK[f] for f in name.split('+'))
        area = -2.24 * math.log(ca / lja) + 0.28 * math.log2(PEAK['LJA'] / peak)
        rec[p] = dict(causal=ca, hind=hi, lja=lja, gain_vs_lja=1 - ca / lja, est_area=area, peak=peak)
        cells.append('%.3f(%+5.1f%%) %.3f | %+5.2f' % (ca, -100 * (1 - ca / lja), hi, area))
    out.append(rec)
    print('%-22s %s' % (rec['cand'][:22], ' '.join('%-27s' % c for c in cells)))
print('LJA single per pool: ' + ' '.join('%s %.4f' % (p, s['single']['LJA']['mean']) for p, s in S.items() if 'LJA' in s['single']))
json.dump(out, open(H + '/shortlist.json', 'w'), indent=0)
