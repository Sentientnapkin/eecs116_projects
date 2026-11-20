import sys
sys.path.insert(0,'.')
import research.single_model.run_variant as RV
from pathlib import Path
RV.OUT = Path('research/results/single_model').resolve()
for name, src in (('fresh_gatedbg', 'research/single_model/final/submit/gate.c'), ('fresh_fgtdbg', 'research/single_model/final/fgt.c')):
    src = Path(src).resolve()
    print(RV.build(src, RV.CMAKE_DEFAULT, 'GATE_DEBUG=1', name))
