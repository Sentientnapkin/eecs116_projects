"""debug: run a wasm on a few selected episodes. usage: runpool.py name wasm ep1 ep2 ..."""
import sys, os, shutil
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
name, wasm, eps = sys.argv[1], sys.argv[2], sys.argv[3:]
P = Path('/data/backups/rganapa/Sebastian/tmp/lc_dbgpool') / name
shutil.rmtree(P, ignore_errors=True); P.mkdir(parents=True)
for e in eps: os.symlink(f'/data/backups/rganapa/Sebastian/gen/raw-fast/selected/{e}.zip', P / f'{e}.zip')
sc = RV.run_guest_fast(wasm, P, RV.OUT / ('lc_dbg_' + name), workers=8, name=name)
print(sc)
