"""buildlc.py name src.c [cmake]: build to research/results/single_model/lc_<name>/solution.wasm with the (default O3 exact) recipe"""
import sys
from pathlib import Path
from research.single_model import run_variant as RV
name, src = sys.argv[1], Path(sys.argv[2])
cm = Path(sys.argv[3]) if len(sys.argv) > 3 else Path('research/single_model/fuel/CMakeLists_c1.txt').resolve()
print(RV.build(src, cm, '', 'lc_' + name))
