"""python -B -m research.single_model.learnvel.mkwasm NAME SRC "DEFINES" -> results/single_model/lv_NAME/solution.wasm"""
import sys
from pathlib import Path
from research.single_model import run_variant as RV
name, src, defs = sys.argv[1], Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else ''
print(RV.build(src, Path(__file__).with_name('CMakeLists.txt'), defs, 'lv_' + name))
