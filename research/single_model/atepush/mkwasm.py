"""python -B -m research.single_model.atepush.mkwasm NAME SRC "DEFINES" -> results/single_model/NAME/solution.wasm (same cmake recipe as bulk/exact)"""
import sys
from pathlib import Path
from research.single_model import run_variant as RV
name, src, defs = sys.argv[1], Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else ''
w = RV.build(src, Path(__file__).with_name('CMakeLists.txt'), defs, name)
print(w, RV.sha256(w) if hasattr(RV, 'sha256') else '')
