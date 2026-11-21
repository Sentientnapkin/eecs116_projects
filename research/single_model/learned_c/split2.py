"""Rows for learned_c: raw-fast pool (same rules as learned/split.py) + raw-speed pool (170 speed-matched flights).
Roles: train = fold 0-2 and not selected; val = fold 3; sealed = fold 4 (never opened; only the sidecar json is read)."""
import hashlib, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'learned'))
import split as S
SPEED = Path('/data/backups/rganapa/Sebastian/gen/raw-speed/bench')

def load_rows():
    rows = []
    for r in S.load_rows():
        r = dict(r); r['dir'] = str(S.RAW); r['pool'] = 'fast'; rows.append(r)
    for f in sorted(os.listdir(SPEED)):
        if not f.endswith('.json'):
            continue
        d = json.load(open(SPEED / f)); n = f[:-5]
        fo = S.fold_of(d['catalog'], d['scene'])
        role = 'sealed' if fo == 4 else 'val' if fo == 3 else 'train'
        rows.append(dict(name=n, catalog=d['catalog'], scene=d['scene'], fold=fo, selected=False, role=role, start='speed', dir=str(SPEED), pool='speed'))
    NEW = Path(__file__).parent / 'gen' / 'new_rows.json'
    if NEW.exists():
        for n, r in json.load(open(NEW)).items():
            r = dict(r); r['fold'] = S.fold_of(r['catalog'], r['scene']); r['selected'] = False; assert r['fold'] in (0, 1, 2); rows.append(r)
    return rows
