"""Build with the frozen toolchain. --off reproduces the submitted bytes exactly."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
from . import generate

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SDK=Path('/data/backups/rganapa/Sebastian/tmp/viobench-toolchain/wasi-sdk')
NATIVE=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('name');ap.add_argument('--off',action='store_true');ap.add_argument('--profile',action='store_true');ap.add_argument('--sync',action='store_true');ap.add_argument('--cap',type=int,default=5000000);ap.add_argument('--pixel',type=float,default=1.515);a=ap.parse_args()
    os.environ['TMPDIR']='/data/backups/rganapa/Sebastian/tmp/ensemble2'
    out=HERE/'build'/a.name;out.mkdir(parents=True,exist_ok=True)
    if a.off:
        from research.single_model import run_variant as rv
        import shutil
        built=rv.build(generate.BASE,HERE.parent/'linejac/CMakeLists.txt','','ens2_off_verified')
        wasm=out/'solution.wasm';shutil.copy(built,wasm)
        digest=hashlib.sha256(wasm.read_bytes()).hexdigest()
        expected='eb2799cbdc8dd9fa2711cdeda3062447364b6dfd4b05e72e543edd3ffa1a8e6d'
        assert digest==expected,(digest,expected)
        (out/'manifest.json').write_text(json.dumps(dict(vars(a),sha256=digest),indent=2)+'\n')
        print('Switch off verified:',digest);return
    generate.main()
    if a.off:sources=[generate.BASE]
    else:sources=[HERE/(s+'.c') for s in ('primary','secondary','cost','wrapper')]
    defs=[f'-DENS2_PROFILE={int(a.profile)}',f'-DENS2_SYNC={int(a.sync)}',f'-DENS2_CAP={a.cap}',f'-DENS2_PIXEL={a.pixel}'] if not a.off else []
    objects=[]
    for src in sources:
        obj=out/(src.stem+'.o');objects.append(str(obj))
        cmd=[str(SDK/'bin/clang'),'-I'+str(NATIVE),'-I'+str(HERE),*defs,'-O3','-DNDEBUG','-O2','-msimd128','-O3',*(['-mbulk-memory'] if not a.off else []),'-c',str(src),'-o',str(obj)]
        subprocess.run(cmd,check=True)
    wasm=out/'solution.wasm'
    subprocess.run([str(SDK/'bin/clang'),'-O3','-DNDEBUG','-mexec-model=reactor','-Wl,--initial-memory=67108864','-Wl,--strip-debug',*objects,'-o',str(wasm),'-lm'],check=True)
    manifest=dict(vars(a),wasm=str(wasm),sha256=hashlib.sha256(wasm.read_bytes()).hexdigest(),base_sha256=hashlib.sha256(generate.BASE.read_bytes()).hexdigest())
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest))

if __name__=='__main__':main()
