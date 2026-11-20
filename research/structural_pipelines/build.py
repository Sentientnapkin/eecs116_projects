"""Build isolated seed217 structural ablations from the canonical packed weights. No scoring."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
VARIANTS = {'control': [], 'manhattan': ['-DSTRUCT_MANHATTAN'],
            'direction': ['-DSTRUCT_DIRECTION'], 'combined': ['-DSTRUCT_MANHATTAN', '-DSTRUCT_DIRECTION']}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=RESEARCH/'artifacts/structural-pipelines-v1')
    p.add_argument('--sdk', type=Path, default=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/build/toolchain/wasi-sdk'))
    p.add_argument('--opencv-wasm', type=Path, default=Path('/dev/shm/sebastian-vio/new-model-opencv510-wasm'))
    p.add_argument('--opencv-native', type=Path, default=Path('/dev/shm/sebastian-vio/new-model-opencv510-native'))
    p.add_argument('--variants', nargs='+', choices=VARIANTS, default=list(VARIANTS))
    a = p.parse_args(); out=a.out.resolve()
    if out.exists():
        raise SystemExit(f'Refusing to overwrite {out}; use a fresh --out')
    archive=RESEARCH/'artifacts/n2-kfinputs-frozen/package/source-code-and-canonical-weights.tar.gz'
    if sha(archive) != 'e309d0ec601189bd8a7205d954480851d0de94b6c3af7829174c20603685d81a':
        raise SystemExit('Canonical archive hash mismatch')
    out.mkdir(parents=True)
    snapshot=out/'source'; snapshot.mkdir()
    for file in (RESEARCH/'native_odometry').glob('*'):
        if file.suffix in ('.hpp','.cpp','.py'): shutil.copy2(file,snapshot/file.name)
    shutil.copy2(HERE/'structure.hpp',snapshot/'structure.hpp')
    header=(snapshot/'odometry.hpp').read_text()
    header=header.replace('// ---------------------------------------------------------------- estimator (streaming.Estimator)',
        '''#ifdef STRUCT_ENABLED
} // namespace odo
#include "structure.hpp"
namespace odo {
#endif
// ---------------------------------------------------------------- estimator (streaming.Estimator)''')
    header=header.replace('    Inputs in;', '    Inputs in;\n#ifdef STRUCT_ENABLED\n    Structure structure;\n#endif')
    header=header.replace('        net.w = w;', '''#ifdef STRUCT_ENABLED
        structure.init(fx, fy, cx, cy, R_bc);
#endif
        net.w = w;''')
    header=header.replace('        const double v64[3] = {vb[0], vb[1], vb[2]};', '''#ifdef STRUCT_ENABLED
        R = structure.attitude(t, rgb, in.sw, in.sh, R, packet, n);
#endif
        double v64[3] = {vb[0], vb[1], vb[2]};''')
    header=header.replace('        mv(R, v64, v);', '''        mv(R, v64, v);
#ifdef STRUCT_ENABLED
        double camera_position[3], lever[3]; mv(R, offset, lever);
        for(int i=0;i<3;++i) camera_position[i]=position[i]+lever[i]+(have_v ? .5*(t-last_t)*(v[i]+last_v[i]) : 0);
        // Direction geometry observes camera-centre displacement. Apply its rotation
        // to camera velocity, then remove the angular lever-arm contribution.
        double angular[3]={};
        if(n) for(int c=0;c<3;++c) angular[c]=packet[(n-1)*7+4+c]-input_policy.att.bias[c];
        double cross[3]={angular[1]*offset[2]-angular[2]*offset[1],angular[2]*offset[0]-angular[0]*offset[2],angular[0]*offset[1]-angular[1]*offset[0]};
        double rotational[3]; mv(R,cross,rotational);
        for(int c=0;c<3;++c) v[c]+=rotational[c];
        structure.velocity(t,rgb,in.sw,in.sh,R,camera_position,v);
        for(int c=0;c<3;++c) v[c]-=rotational[c];
        mv(tr(R),v,v64);
#endif''')
    (snapshot/'odometry.hpp').write_text(header)
    # Introspection is read-only and available in the actual scored binary.
    guest=(snapshot/'guest.cpp').read_text()
    guest+='''
#ifdef STRUCT_ENABLED
#ifdef __wasm__
__attribute__((export_name("structure_state")))
#endif
extern "C" void structure_state(double *out) {
    const auto &s=estimator.structure;
    out[0]=s.gravity_ready; out[1]=s.anchored; out[2]=s.yaw;
    out[3]=s.lines_used; out[4]=s.manhattan_updates; out[5]=s.direction_updates;
    out[6]=s.direction_valid; out[7]=s.direction_angle;
}
#endif
'''
    (snapshot/'guest.cpp').write_text(guest)
    spec=importlib.util.spec_from_file_location('export_flags',snapshot/'export.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    import viobench
    abi=Path(viobench.__file__).parent/'solution/runtime/native'
    wasm_compile,wasm_link=module.opencv_flags(a.opencv_wasm,True)
    native_build=a.opencv_native.resolve()
    source=Path(next(l.split('=',1)[1] for l in (native_build/'CMakeCache.txt').read_text().splitlines() if l.startswith('OpenCV_SOURCE_DIR:')))
    modules=['core','imgproc','video','geometry','features','flann']
    native_compile=['-DODO_INPUT_KF_GRID',f'-I{native_build}']+[f'-I{source}/modules/{m}/include' for m in modules]
    native_link=[f'-L{native_build}/lib',f'-Wl,-rpath,{native_build}/lib']+[f'-lopencv_{m}' for m in ['video','features','geometry','flann','imgproc','core']]
    records={}
    with tarfile.open(archive) as tar:
        assets={name:tar.extractfile('newest-cpp-source/canonical/'+name).read() for name in ['weights.f32','weights.S','model_config.h','counts.json']}
    for name in a.variants:
        folder=out/name; folder.mkdir()
        for file,data in assets.items(): (folder/file).write_bytes(data)
        extra=VARIANTS[name]+(['-DSTRUCT_ENABLED'] if name!='control' else [])
        common=['-std=c++17','-O3','-ffp-contract=off','-Wall','-Wextra','-Werror',f'-I{folder}',f'-I{abi}',str(snapshot/'guest.cpp'),*extra]
        commands=[['c++',*common,*native_compile,'-march=native','-fPIC','-shared',*native_link,'-o',str(folder/'host.so')],
                  [str(a.sdk.resolve()/'bin/clang++'),*common,*wasm_compile,*module.WASM_KERNEL_FLAGS['simd-8x32-k2'],
                   '-mexec-model=reactor','-Wl,--initial-memory=67108864','-Wl,--strip-debug','weights.S',*wasm_link,'-o','odometry.wasm']]
        for command in commands: subprocess.run(command,cwd=folder,check=True)
        records[name]={'wasm':str(folder/'odometry.wasm'),'sha256':sha(folder/'odometry.wasm'),
                       'host_sha256':sha(folder/'host.so'),'weights_sha256':sha(folder/'weights.f32'),
                       'flags':extra,'commands':commands}
        (out/'build.json').write_text(json.dumps({'status':'built; validation pending; unscored','variants':records,
            'canonical_archive_sha256':sha(archive),'source_sha256':{f.name:sha(f) for f in snapshot.iterdir() if f.is_file()},
            'base':'N2 kf_grid_native seed217; frozen model inputs; integration-only structural ablations'},indent=2)+'\n')
        print(name,records[name]['sha256'],flush=True)
    (out/'score.sh').write_text('#!/usr/bin/env bash\nset -euo pipefail\n: "${EPISODES:?Set EPISODES to your frozen scoring dataset}"\n: "${SCORES:?Set SCORES to a fresh output directory}"\n'+
        f'exec /data/backups/rganapa/Sebastian/venv-teacher/bin/python {HERE}/score.py --suite {out}/ready.json '+
        '--episodes "$EPISODES" --out "$SCORES" --workers "${WORKERS:-8}"\n')

if __name__=='__main__': main()
