"""Build isolated C++ VIO variants; never change the pinned examples.

Example: python build.py --guest vins_mono --out /path/vins_recovery.wasm
Fault:   python build.py --guest vins_mono --fault-reset 20 --out /path/fault.wasm
OV:      python build.py --guest openvins --guard --out /path/guarded.wasm
"""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
from prepare import PIN, vins, openvins, telemetry_only
RUNTIME=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')

def main():
    p=argparse.ArgumentParser();p.add_argument('--guest',choices=['vins_mono','openvins'],required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--guard',action='store_true');p.add_argument('--telemetry-only',action='store_true');p.add_argument('--fault-reset',type=float);p.add_argument('--jobs',type=int,default=24);p.add_argument('--work',type=Path,default=Path('/dev/shm/sebastian-vio/guard-fixes-build'));a=p.parse_args()
    source=PIN/a.guest; variant=a.guest+('-telemetry' if a.telemetry_only else '')+('-guard' if a.guard else '')+('-fault'+str(a.fault_reset) if a.fault_reset is not None else '')
    work=a.work/variant;work.mkdir(parents=True,exist_ok=True)
    for child in source.iterdir():
        if child.name=='build':continue
        dest=work/child.name
        if child.is_dir():shutil.copytree(child,dest,dirs_exist_ok=True)
        else:shutil.copy2(child,dest)
    original=(source/'solution.cpp').read_text();patched=(vins if a.guest=='vins_mono' else openvins)(original)
    if a.telemetry_only:
        if a.guard or a.fault_reset is not None:raise ValueError('telemetry-only cannot alter estimator behavior')
        patched=telemetry_only(a.guest,original,patched)
    (work/'solution.cpp').write_text(patched)
    defs=['VIO_TELEMETRY']
    if a.guard:defs+=['VIO_OUTPUT_GUARD']
    if a.fault_reset is not None:
        if a.guest!='vins_mono':raise ValueError('reset injection is VINS-only')
        defs+=['VIO_FAULT_RESET_SECONDS='+str(a.fault_reset)]
    with (work/'CMakeLists.txt').open('a') as f:f.write('\ntarget_compile_definitions(solution PRIVATE '+' '.join(defs)+')\n')
    # Reuse content-addressed downloaded sources, but never a relocated CMake tree.
    cache=Path('/dev/shm/sebastian-vio')/('viobench-vins' if a.guest=='vins_mono' else 'viobench')/'viobench/solution/examples/native'/a.guest/'build'
    for part in ['downloads','src']:
        if (cache/part).exists() and not (work/'build'/part).exists():shutil.copytree(cache/part,work/'build'/part)
    env={'HOME':'/data/backups/rganapa/Sebastian','TMPDIR':'/dev/shm/sebastian-vio/tmp','PATH':'/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin:/usr/bin:/bin','CMAKE_BUILD_PARALLEL_LEVEL':str(a.jobs),'MAKEFLAGS':'-j'+str(a.jobs)}
    subprocess.run(['bash',str(RUNTIME/'build.sh'),str(work)],env=env,check=True)
    a.out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(work/'build/solution.wasm',a.out)
    digest=lambda x:hashlib.sha256(x).hexdigest()
    provenance={'wasm':str(a.out.resolve()),'sha256':digest(a.out.read_bytes()),'upstream_commit':'9b1b07906aff5a3e6f00155e7aecf967d90aa960','source_sha256':digest(original.encode()),'patched_source_sha256':digest(patched.encode()),'definitions':defs,'source_dir':str(work),'status':'exploratory'}
    a.out.with_suffix('.json').write_text(json.dumps(provenance,indent=2)+'\n');print(json.dumps(provenance,indent=2))
if __name__=='__main__':main()
