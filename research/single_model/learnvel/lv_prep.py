"""lv_prep.py POOLDIR [workers] [CACHE]: C-matched cache (learned_c/prep2.py pipeline) for every zip in POOLDIR (eval-only or new training flights)."""
import sys, os
from pathlib import Path
from multiprocessing import Pool
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'learned_c')); sys.path.insert(0, str(HERE.parent / 'learned'))
import prep2
prep2.CACHE = Path(sys.argv[3] if len(sys.argv) > 3 else '/data/backups/rganapa/Sebastian/tmp/lv_cache')
def one(z):
    try: return prep2.one(dict(name=z.stem, dir=str(z.parent), role='val'))
    except Exception as e: return z.stem, 'ERR %r' % e
if __name__ == '__main__':
    prep2.CACHE.mkdir(parents=True, exist_ok=True)
    zs = sorted(Path(sys.argv[1]).glob('*.zip'))
    with Pool(int(sys.argv[2]) if len(sys.argv) > 2 else 16) as p:
        for i, r in enumerate(p.imap_unordered(one, zs)):
            if i % 20 == 0 or 'ERR' in r[1]: print(i, r, flush=True)
    print('done', len(zs))
