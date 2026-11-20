"""Split rules (strict). fold = int(sha256(f'{catalog}:{scene}')[:8],16) % 5 from the sidecar json only (the zip of a fold-4
flight is never opened by any code in this directory).
  role 'train' : fold in {0,1,2} and NOT one of the 171 selected flights
  role 'val'   : fold 3 (selected or not)
  role 'sealed': fold 4 (never read)
  role 'search_sel': selected flights of folds 0-2 (evaluation only, not trained on)
"""
import hashlib, json, os
from pathlib import Path
RAW = Path('/data/backups/rganapa/Sebastian/gen/raw-fast/bench')
SEL = Path('/data/backups/rganapa/Sebastian/gen/raw-fast/selected')


def fold_of(catalog, scene):
    return int(hashlib.sha256(f'{catalog}:{scene}'.encode()).hexdigest()[:8], 16) % 5


def load_rows():
    sel = {f[:-4] for f in os.listdir(SEL) if f.endswith('.zip')}
    rows = []
    for f in sorted(os.listdir(RAW)):
        if not f.endswith('.json'):
            continue
        d = json.load(open(RAW / f)); n = f[:-5]
        fo = fold_of(d['catalog'], d['scene'])
        selected = n in sel
        role = 'sealed' if fo == 4 else 'val' if fo == 3 else ('search_sel' if selected else 'train')
        rows.append(dict(name=n, catalog=d['catalog'], scene=d['scene'], fold=fo, selected=selected, role=role,
                         start='mid' if n.startswith('fastmid-') else 'static'))
    return rows
