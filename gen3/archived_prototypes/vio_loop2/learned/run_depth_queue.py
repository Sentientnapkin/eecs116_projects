#!/usr/bin/env python3
"""Finite paired screen for oracle-depth geometry hypotheses; confirm best only.

The depth is triangulated from GT poses and existing tracks (not renderer depth).
Every arm has a matched OR=1/no-intervention control on identical episodes.
"""
import hashlib, json, os, shutil, statistics, subprocess, sys, time
from pathlib import Path
import re

ROOT=Path('/data/backups/rganapa/Sebastian/eecs116_projects')
GEN=ROOT.parent/'gen3'; I3=GEN/'research/i3'; WORK=Path('/tmp/vio_loop2/learned')
OUT=Path('/dev/shm/vio_loop2/learned'); TOOL=ROOT.parent/'tmp/viobench-toolchain'
NATIVE=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')
CM=ROOT/'research/single_model/linejac/CMakeLists.txt'
BASE='PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0'
TIMEOUT=7200

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build(name, source, defs):
    dst=OUT/'builds'/name; wasm=dst/'solution.wasm'
    prov=dst/'provenance.json'; wanted={'source_sha256':sha(source),'defines':defs}
    if wasm.exists() and prov.exists() and json.loads(prov.read_text())==wanted: return wasm
    if dst.exists(): shutil.rmtree(dst)
    src=dst/'src'; src.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,src/'solution.c'); shutil.copy2(CM,src/'CMakeLists.txt')
    flags=' '.join('-D'+x for x in defs.split())
    cfg=['cmake','-S',str(src),'-B',str(src/'build'),f'-DCMAKE_TOOLCHAIN_FILE={TOOL}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',f'-DVIOBENCH_NATIVE_DIR={NATIVE}',f'-DCMAKE_C_FLAGS={flags}']
    for cmd in (cfg,['cmake','--build',str(src/'build'),'-j2']):
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
        if p.returncode: raise RuntimeError((p.stdout+p.stderr)[-4000:])
    shutil.copy2(src/'build/solution.wasm',wasm)
    prov.write_text(json.dumps(wanted,indent=2)+'\n')
    return wasm

def instrument_or():
    out=OUT/'src_or_instrumented.c'; s=(I3/'src_or.c').read_text()
    s=s.replace('#ifndef OR_DEP\n#define OR_DEP 0\n#endif', '#ifndef OR_DEP\n#define OR_DEP 0\n#endif\n#ifndef OR_DEP_EVERY\n#define OR_DEP_EVERY 1\n#endif')
    s=s.replace('static double or_s[40]; static long or_cnt; static long or_tri_h[8];',
                'static double or_s[40]; static long or_cnt; static long or_tri_h[8]; static long or_dep_seen, or_dep_valid, or_dep_rows;')
    s=s.replace('memset(or_s, 0, sizeof or_s); or_cnt = 0; memset(or_tri_h, 0, sizeof or_tri_h);',
                'memset(or_s, 0, sizeof or_s); or_cnt = 0; memset(or_tri_h, 0, sizeof or_tri_h); or_dep_seen = or_dep_valid = or_dep_rows = 0;')
    s=s.replace('fprintf(stderr, "\\n");\n        }\n    }\n}\n/* GT-pose triangulation',
                'fprintf(stderr, "\\nORDEP %ld %ld %ld\\n", or_dep_seen, or_dep_valid, or_dep_rows);\n        }\n    }\n}\n/* GT-pose triangulation')
    s=s.replace('#if OR_DEP_ON\n    if (rms < 0 || rms > OR_DEP_REJ) return 0;',
                '#if OR_DEP_ON\n    or_dep_seen++;\n    if (OR_DEP_EVERY > 1 && ((unsigned)o->tid % OR_DEP_EVERY) != 0) return 0;\n    if (rms < 0 || rms > OR_DEP_REJ) return 0;\n    or_dep_valid++;')
    s=s.replace('*dz = dt * (1 + or_scale + e); or_dsd = OR_DEP * dt;\n        return 1;',
                '*dz = dt * (1 + or_scale + e); or_dsd = OR_DEP * dt;\n        or_dep_rows++;\n        return 1;')
    if not all(x in s for x in ('ORDEP %ld %ld %ld','or_dep_valid++;','or_dep_rows++;')):
        raise RuntimeError('instrumentation insertion failed')
    out.write_text(s); return out

def eval_arm(name, wasm, panel, workers):
    marker=WORK/f'{name}_{panel.name}.done.json'
    if marker.exists() and json.loads(marker.read_text()).get('wasm_sha256')==sha(wasm): return json.loads(marker.read_text())
    sys.path.insert(0,str(ROOT)); from research.single_model.run_variant import run_guest_fast
    sp=run_guest_fast(wasm,panel,OUT/'evals'/name,workers=workers,name=name)
    d=json.loads(Path(sp).read_text()); rows=[r for r in d['rows'] if r.get('ate_full') is not None]
    expected=len(list(panel.glob('*.zip')))
    if len(rows)!=expected: raise RuntimeError(f'{name}/{panel.name}: got {len(rows)}/{expected} completed')
    counts={}
    if name.startswith('depth_'):
        folder=Path(sp).parent
        for episode in (p.stem for p in panel.glob('*.zip')):
            logs=list((folder/episode/'report/logs').glob('*/stderr.txt'))
            txt='\n'.join(p.read_text(errors='replace') for p in logs)
            m=re.findall(r'ORDEP\s+(\d+)\s+(\d+)\s+(\d+)',txt)
            if not m or int(m[-1][2])<=0: raise RuntimeError(f'{name}/{episode}: depth hook had zero rows or no counter')
            counts[episode]={'seen':int(m[-1][0]),'valid':int(m[-1][1]),'rows':int(m[-1][2])}
    vals=[float(r['ate_full']) for r in rows]
    r={'name':name,'panel':panel.name,'n':len(vals),'mean_ate':statistics.mean(vals),'median_ate':statistics.median(vals),
       'p90_ate':sorted(vals)[int(.9*(len(vals)-1))], 'max_ate':max(vals),
       'tail_gt_1m':sum(v>1 for v in vals),'tail_gt_2m':sum(v>2 for v in vals),
       'peak_fuel':max(int(x.get('peak_fuel_per_frame') or 0) for x in rows),
       'wasm_sha256':sha(wasm),'episode_ate':{x['episode']:x['ate_full'] for x in rows},'scores_file':str(sp),
       'depth_rows_per_episode':counts}
    marker.write_text(json.dumps(r,indent=2)+'\n')
    with (WORK/'results.tsv').open('a') as f:
        f.write(f"{name}\t{panel.name}\t{r['n']}\t{r['mean_ate']:.6f}\t{r['median_ate']:.6f}\t{r['p90_ate']:.6f}\t{r['tail_gt_1m']}\t{r['tail_gt_2m']}\t{r['peak_fuel']}\t{r['wasm_sha256']}\n")
    return r

def paired(cand, control):
    a=cand['episode_ate']; b=control['episode_ate']; keys=sorted(set(a)&set(b))
    dif=[float(a[k])-float(b[k]) for k in keys]
    return {'n':len(dif),'mean_delta':statistics.mean(dif),'median_delta':statistics.median(dif),
            'wins':sum(x<0 for x in dif),'ties':sum(x==0 for x in dif),'losses':sum(x>0 for x in dif),
            'episode_delta':{k:float(a[k])-float(b[k]) for k in keys}}

def main():
    WORK.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    # Fresh development panels are disjoint from the previous current-system screens.
    sp=Path('/tmp/vio_loop2/shared/screen24'); cp=Path('/tmp/vio_loop2/shared/confirm48')
    srcbase=I3/'src_base.c'; srcor=instrument_or()
    # Sparse hypothesis is deterministic: only one in four triangulated track IDs gets a row.
    sparse=OUT/'src_or_sparse.c'
    s=srcor.read_text(); sparse.write_text(s)
    # Controls: exact baseline and oracle-enabled zero-depth-row control.
    meta=json.loads((I3/'data/or_meta.json').read_text()); truth={x['id'] for x in meta['flights']}
    panels={'screen24':sorted(p.stem for p in sp.glob('*.zip')),'confirm48':sorted(p.stem for p in cp.glob('*.zip'))}
    coverage={k:len(set(v)&truth) for k,v in panels.items()}
    if coverage!={'screen24':24,'confirm48':48}: raise RuntimeError(f'OR truth coverage mismatch {coverage}')
    specs=[('oldbase',srcbase,BASE),('orcontrol',srcor,BASE+' OR=1')]
    # 1) Independent fractional depth noise; 2) sparse one-in-four constraints to
    # reduce repeated correlated priors; 3) heavy-tail robust-noise stress test.
    specs += [('depth_iid10',srcor,BASE+' OR=1 OR_DEP=0.10 OR_DEP_ON=1 OR_NT=0'),
              ('depth_shared10',srcor,BASE+' OR=1 OR_DEP=0.10 OR_DEP_ON=1 OR_NT=2 OR_NK=1.0 OR_SCALE=0'),
              ('depth_shared10_cov2x',srcor,BASE+' OR=1 OR_DEP=0.20 OR_DEP_ON=1 OR_NT=2 OR_NK=0.5 OR_SCALE=0'),
              ('depth_sparse4_shared10',sparse,BASE+' OR=1 OR_DEP=0.10 OR_DEP_ON=1 OR_NT=2 OR_NK=1.0 OR_SCALE=0 OR_DEP_EVERY=4'),
              ('depth_outlier10',srcor,BASE+' OR=1 OR_DEP=0.10 OR_DEP_ON=1 OR_NT=3 OR_OUTK=6 OR_SCALE=0')]
    manifest={'panels':panels,
      'hypotheses':['sparse geometry reduces repeated correlated metric priors while retaining scale information','heavy-tailed depth noise changes robustness/tail vs Gaussian depth noise'],
      'depth_semantics':'GT-pose triangulated from existing tracked pixels; rejection on reprojection RMS; not renderer-exact depth',
      'noise':'iid Gaussian sigma=0.10 (OR_NT=0); shared episode Gaussian fractional bias actual sigma=OR_DEP*OR_NK=0.10, modeled sigma=OR_DEP=0.10; covariance-inflation arm keeps actual sigma=0.10 via OR_DEP=.20, OR_NK=.5 while modeled sigma doubles; sparse arm selects 1/4 tracks with actual/model sigma=.10; outlier arm has 1% contamination at 6x scale. OR_SCALE=0 in all arms.',
      'controls':'matched old A160ft Ze0 baseline and OR=1/no intervention on identical fresh panel',
      'gt_coverage_checked':True,'gt_coverage_counts':coverage,
      'deadline_seconds':TIMEOUT,'workers_per_eval':2,'max_arms':7}
    unit={n:dict(OR_DEP=float(d.split('OR_DEP=')[1].split()[0]),OR_NK=float(next((x.split('=')[1] for x in d.split() if x.startswith('OR_NK=')),'1')),OR_NT=int(next((x.split('=')[1] for x in d.split() if x.startswith('OR_NT=')),'0'))) for n,_,d in specs if n.startswith('depth_')}
    if any(v['OR_DEP']<=0 or v['OR_NK']<=0 for v in unit.values()): raise RuntimeError(f'nonpositive sigma configuration {unit}')
    manifest['noise_unit_check']={'positive_sigma':True,'per_arm':unit}
    (WORK/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    deadline=time.monotonic()+TIMEOUT
    metrics={}
    # Screen four fixed arms; controls are retained for explicit pairing.
    for name,src,defs in specs:
        if time.monotonic()>=deadline: raise TimeoutError('queue wall deadline')
        wasm=build(name,src,defs); metrics[name]=eval_arm(name,wasm,sp,2)
    control=metrics['orcontrol']
    scores={k:paired(metrics[k],control) for k in ('depth_iid10','depth_shared10','depth_shared10_cov2x','depth_sparse4_shared10','depth_outlier10')}
    (WORK/'screen_paired.json').write_text(json.dumps(scores,indent=2)+'\n')
    # Select by mean paired ATE with no worse >1m tail; only that candidate earns confirmation.
    eligible=[k for k in scores if metrics[k]['tail_gt_1m']<=control['tail_gt_1m']]
    if eligible:
        best=min(eligible,key=lambda k:scores[k]['mean_delta'])
        if scores[best]['mean_delta']<0:
            if time.monotonic()>=deadline: raise TimeoutError('before confirmation')
            confirm_control=eval_arm('orcontrol',build('orcontrol',srcor,BASE+' OR=1'),cp,2)
            conf=eval_arm(best,build(best,dict((n,(s,d)) for n,s,d in specs)[best][0],dict((n,(s,d)) for n,s,d in specs)[best][1]),cp,2)
            (WORK/'confirmation_paired.json').write_text(json.dumps({'selected':best,'candidate':conf,'control':confirm_control,'paired':paired(conf,confirm_control)},indent=2)+'\n')
    (WORK/'queue.done').write_text('screen and any eligible independent confirmation completed\n')

if __name__=='__main__':
    main()
