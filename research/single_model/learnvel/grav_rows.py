"""label raw-fast/raw-speed rows (train/val roles only; sealed fold 4 never opened)"""
import sys
from pathlib import Path
from multiprocessing import Pool
sys.path.insert(0, '../learned_c'); sys.path.insert(0, '../learned'); sys.path.insert(0, '.')
import split2, grav
rows = [r for r in split2.load_rows() if r['role'] in ('train', 'val') and r['pool'] in ('fast', 'speed')]
zs = [f"{r['dir']}/{r['name']}.zip" for r in rows if Path(f"{r['dir']}/{r['name']}.zip").exists()]
with Pool(16) as p: r = p.map(grav.label, zs)
print(len(zs), sum(x[1] == 'ok' for x in r))
