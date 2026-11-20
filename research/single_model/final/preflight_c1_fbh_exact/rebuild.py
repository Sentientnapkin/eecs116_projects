import sys,hashlib,pathlib
sys.path.insert(0,'.')
from research.single_model import run_variant as RV
src=pathlib.Path('research/single_model/fuel/adopted_c1_fbh_exact.c'); cm=pathlib.Path('research/single_model/fuel/c1fbh/CMakeLists.txt')
for n in ('preflight_c1_fbh_exact_build1','preflight_c1_fbh_exact_build2'):
    w=RV.build(src,cm,'',n); print(n,hashlib.sha256(open(w,'rb').read()).hexdigest())
