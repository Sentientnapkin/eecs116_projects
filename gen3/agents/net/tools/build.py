"""build.py SRC NAME ["DEFINES"] -> gen3/agents/net/builds/NAME/solution.wasm (same toolchain/cmake as run_variant.build / linejac)."""
import sys, shutil, subprocess, hashlib
from pathlib import Path
TOOLCHAIN = Path('/data/backups/rganapa/Sebastian/tmp/viobench-toolchain')
NATIVE = Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')
CMAKE = Path('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/linejac/CMakeLists.txt')
OUT = Path('/data/backups/rganapa/Sebastian/gen3/agents/net/builds')
def build(src, name, defines=''):
    work = OUT / name / 'src'
    if work.exists(): shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copy(src, work / 'solution.c'); shutil.copy(CMAKE, work / 'CMakeLists.txt')
    flags = ' '.join('-D' + d for d in defines.split()) if defines else ''
    cfg = ['cmake', '-S', str(work), '-B', str(work / 'build'), f'-DCMAKE_TOOLCHAIN_FILE={TOOLCHAIN}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',
           f'-DVIOBENCH_NATIVE_DIR={NATIVE}', f'-DCMAKE_C_FLAGS={flags}']
    for cmd in (cfg, ['cmake', '--build', str(work / 'build')]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode: raise SystemExit(p.stdout[-2000:] + p.stderr[-2000:])
    w = OUT / name / 'solution.wasm'; shutil.copy(work / 'build/solution.wasm', w)
    return w, hashlib.sha256(w.read_bytes()).hexdigest()
if __name__ == '__main__':
    print(*build(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ''))
