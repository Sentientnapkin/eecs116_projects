import argparse,sys
from pathlib import Path
H=Path(__file__).resolve().parent;SM=H.parent;sys.path.insert(0,str(SM.parents[1]))
from research.single_model import run_variant as R
R.OUT=H/'builds';p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--rep',type=int,required=True);a=p.parse_args();assert a.rep in (1,2)
defs='LV_STLONG=1 '+['','PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0','PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0'][a.rep]
print(R.build(H/'runs'/f'{a.name}.c',SM/'learnvel/CMakeLists.txt',defs,f'{a.name}_r{a.rep}'))
