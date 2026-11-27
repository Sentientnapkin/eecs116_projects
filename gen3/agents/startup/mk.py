"""python mk.py NAME "DEF1=1 DEF2=2" [src] -> agents/priors/builds/NAME/solution.wasm (prints path + sha)"""
import sys,shutil,subprocess,hashlib
from pathlib import Path
P=Path('/data/backups/rganapa/Sebastian/gen3/agents/startup')
SRC=Path(sys.argv[3]) if len(sys.argv)>3 else P/'gslv_st.c'
CM=Path('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/linejac/CMakeLists.txt')
TC=Path('/data/backups/rganapa/Sebastian/tmp/viobench-toolchain');NAT=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')
name,defs=sys.argv[1],sys.argv[2]
w=P/'builds'/name/'src'
if w.exists(): shutil.rmtree(w)
w.mkdir(parents=True);shutil.copy(SRC,w/'solution.c');shutil.copy(CM,w/'CMakeLists.txt')
flags=' '.join('-D'+d for d in defs.split())
for c in (['cmake','-S',str(w),'-B',str(w/'build'),f'-DCMAKE_TOOLCHAIN_FILE={TC}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',f'-DVIOBENCH_NATIVE_DIR={NAT}',f'-DCMAKE_C_FLAGS={flags}'],['cmake','--build',str(w/'build')]):
    p=subprocess.run(c,capture_output=True,text=True)
    if p.returncode: raise SystemExit(p.stdout[-3000:]+p.stderr[-3000:])
o=P/'builds'/name/'solution.wasm';shutil.copy(w/'build/solution.wasm',o)
(P/'builds'/name/'flags.txt').write_text(defs+'\n')
print(o,hashlib.sha256(o.read_bytes()).hexdigest()[:16])
