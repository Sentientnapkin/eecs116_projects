"""Build li.c with defines and run on lateinit pools.  python runpool.py NAME "DEFS" pool1,pool2 [workers]"""
import os, sys
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from pathlib import Path
from research.single_model import run_variant as RV
L = Path('research/single_model/lateinit')
name, defs, pools = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
wk = int(sys.argv[4]) if len(sys.argv) > 4 else 16
src = L / (sys.argv[5] if len(sys.argv) > 5 else 'li.c')
w = RV.build(src, RV.ROOT / 'research/single_model/bulk/exact/CMakeLists.txt', defs, name)
for p in pools:
    pdir = L / ('pool_' + p) if (L / ('pool_' + p)).exists() else Path(p)
    print(RV.run_guest_fast(w, pdir, RV.OUT / name / ('eval_' + p), workers=wk, name=name), flush=True)
