"""python build.py NAME SRCDIR "DEFINES" -> builds/NAME/solution.wasm (wasi-sdk, viobench reactor). SRCDIR holds CMakeLists.txt + sources."""
import sys, shutil, subprocess, hashlib
from pathlib import Path
TOOLCHAIN = Path('/data/backups/rganapa/Sebastian/tmp/viobench-toolchain')
NATIVE = Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')
HERE = Path(__file__).resolve().parent
def build(name, srcdir, defines=''):
    work = HERE.parent / 'builds' / name / 'src'
    if work.exists(): shutil.rmtree(work)
    shutil.copytree(srcdir, work)
    flags = ' '.join('-D' + d for d in defines.split()) if defines else ''
    cfg = ['cmake', '-S', str(work), '-B', str(work / 'build'), f'-DCMAKE_TOOLCHAIN_FILE={TOOLCHAIN}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',
           f'-DVIOBENCH_NATIVE_DIR={NATIVE}', f'-DCMAKE_C_FLAGS={flags}', f'-DCMAKE_CXX_FLAGS={flags}']
    for cmd in (cfg, ['cmake', '--build', str(work / 'build')]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode: raise SystemExit(p.stdout[-3000:] + p.stderr[-3000:])
    out = HERE.parent / 'builds' / name / 'solution.wasm'
    w = list((work / 'build').glob('*.wasm'))[0]
    shutil.copy(w, out)
    print(out, hashlib.sha256(out.read_bytes()).hexdigest())
    return out
if __name__ == '__main__':
    build(sys.argv[1], Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else '')
