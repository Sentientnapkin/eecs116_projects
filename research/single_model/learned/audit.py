"""Split audit: reads the train flight list stored in a run's result.json and the cache dir listing."""
import json, os, sys, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import split
rows = {r['name']: r for r in split.load_rows()}
sel = {f[:-4] for f in os.listdir(split.SEL)}
cache = {f[:-4] for f in os.listdir('/data/backups/rganapa/Sebastian/tmp/learned_cache') if f.endswith('.npz')}
res = json.load(open(sys.argv[1]))
tr = res['train_flights']
print('train flights', len(tr), 'folds', sorted({rows[n]['fold'] for n in tr}), 'selected among train', sum(n in sel for n in tr),
      'fold4 among train', sum(rows[n]['fold'] == 4 for n in tr), 'fold3 among train', sum(rows[n]['fold'] == 3 for n in tr))
print('train scenes', len({rows[n]['scene'] for n in tr}))
print('cache files', len(cache), 'fold4 in cache', sum(rows[n]['fold'] == 4 for n in cache), 'by role', {k: sum(rows[n]['role'] == k for n in cache) for k in ('train', 'val', 'search_sel', 'sealed')})
print('val flights', res['n_val_flights'], 'val anchors', res['n_val_anchors'], 'train anchors', res['n_train_anchors'])
sc_val = {r['scene'] for r in rows.values() if r['role'] == 'val'}; sc_tr = {rows[n]['scene'] for n in tr}
print('val scenes', len(sc_val), 'overlap with train scenes', len(sc_val & sc_tr))
ss = {r['scene'] for r in rows.values() if r['role'] == 'search_sel'}
print('search-selected scenes', len(ss), 'overlapping train scenes', len(ss & sc_tr), '(flights in those scenes:', sum(r['role']=='search_sel' and r['scene'] in sc_tr for r in rows.values()), 'of', sum(r['role']=='search_sel' for r in rows.values()), ')')
