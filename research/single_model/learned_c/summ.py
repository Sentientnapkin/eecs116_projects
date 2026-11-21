"""summarise runs: summ.py run1 run2 ... : val head-K error all / by angle / by speed (cov1), crit, params/MACs, train err"""
import json, sys
for n in sys.argv[1:]:
    r = json.load(open(f'runs/{n}/result.json')); v = r['val']
    print(f"{n:12s} flights {r.get('n_train_flights')} crit {r.get('best_crit', min(x['val_balanced'] for x in r['log'])):.4f} all {v['all']['err0']:.3f}/{v['all']['errK']:.3f} cov1 {v['all']['cov1']:.2f} | ang " +
          ' '.join('%.3f' % v[k]['errK'] for k in v if k.startswith('ang')) + ' | spd ' + ' '.join('%.3f(%.2f)' % (v[k]['errK'], v[k]['cov1']) for k in v if k.startswith('spd')) +
          f" | MACs {r['macs']/1e6:.1f}M sig {r['sigma_scale_headK']:.2f} train_err {r.get('train_err_all', float('nan')):.3f}")
