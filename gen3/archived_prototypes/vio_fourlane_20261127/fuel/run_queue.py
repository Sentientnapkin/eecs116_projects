import json, os, subprocess, sys, time, hashlib, statistics, glob
from pathlib import Path
ROOT=Path('/data/backups/rganapa/Sebastian/gen3')
TASK=Path('/tmp/vio_fourlane_20261127/fuel')
BULK=Path('/dev/shm/vio_fourlane_20261127/fuel')
SRC=ROOT/'agents/anchors/base_sn.c'
CM=Path('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/linejac/CMakeLists.txt')
TC=Path('/data/backups/rganapa/Sebastian/tmp/viobench-toolchain')
NAT=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')
PY=Path('/data/backups/rganapa/Sebastian/venv-teacher/bin/python')
BASE_WASM=ROOT/'scratch_up/gslv_s3_snace6e1.wasm'
BASE_SHA='1a169f28916acd813f86a7b526efb8e8b646b3dda73e48cba51b12845c69b1b8'
QUEUE=TASK/'queue.jsonl'; STATUS=TASK/'status.jsonl'; LOG=TASK/'runner.log'
def log(kind, **kw):
    row={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'kind':kind,**kw}
    with STATUS.open('a') as f: f.write(json.dumps(row,sort_keys=True)+'\n')
    with LOG.open('a') as f: f.write(json.dumps(row,sort_keys=True)+'\n')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pause_load():
    while True:
        la=float(open('/proc/loadavg').read().split()[0])
        if la <= 170: return la
        log('pause_load',loadavg=la); time.sleep(60)
def build(j):
    name=j['id']; out=BULK/'builds'/name; srcdir=out/'src'; builddir=srcdir/'build'; wasm=out/'solution.wasm'
    if wasm.exists(): return wasm
    srcdir.mkdir(parents=True,exist_ok=True); (out/'flags.txt').write_text(j['defs']+'\n')
    import shutil
    shutil.copy2(SRC,srcdir/'solution.c'); shutil.copy2(CM,srcdir/'CMakeLists.txt')
    flags=' '.join('-D'+d for d in j['defs'].split())
    cmds=[['cmake','-S',str(srcdir),'-B',str(builddir),f'-DCMAKE_TOOLCHAIN_FILE={TC}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',f'-DVIOBENCH_NATIVE_DIR={NAT}',f'-DCMAKE_C_FLAGS={flags}'],['cmake','--build',str(builddir)]]
    for c in cmds:
        p=subprocess.run(c,capture_output=True,text=True)
        if p.returncode: raise RuntimeError('BUILD_FAIL '+name+' '+p.stdout[-2000:]+' '+p.stderr[-2000:])
    wasm.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(builddir/'solution.wasm',wasm)
    log('built',id=name,sha256=sha(wasm),bytes=wasm.stat().st_size,defs=j['defs'])
    return wasm
def eval_one(name,wasm):
    out=BULK/'evals'/name
    summary=out/'summary.json'
    if summary.exists(): return json.load(open(summary))
    la=pause_load(); log('eval_start',id=name,wasm_sha256=sha(wasm),pool='panel12',workers=4,loadavg=la)
    env=os.environ.copy(); env['VIOBENCH_PNG_CACHE']='0'
    code=r'''import sys,json,glob,statistics
from pathlib import Path
sys.path.insert(0,'/data/backups/rganapa/Sebastian/eecs116_projects')
from research.single_model import run_variant as RV
name,wasm,pool,out=sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3]),Path(sys.argv[4])
sc=RV.run_guest_fast(wasm,pool,out,workers=4,name=name)
rows=json.load(open(sc))['rows']
Path(sys.argv[5]).write_text(json.dumps({'rows':rows,'scoring_path':str(sc)}))
print('EVAL',name,'n',sum(r.get('ate_full') is not None for r in rows),'/',len(rows),'ATE',statistics.mean(r['ate_full'] for r in rows if r.get('ate_full') is not None))'''
    cmd=[str(PY),'-B','-c',code,name,str(wasm),str(BULK/'pool12'),str(out),str(summary)]
    with (TASK/(name+'.eval.log')).open('w') as lf:
        p=subprocess.run(cmd,cwd=ROOT,env=env,stdout=lf,stderr=subprocess.STDOUT,timeout=1200)
    if p.returncode: raise RuntimeError('EVAL_FAIL '+name+' rc='+str(p.returncode))
    data=json.load(open(summary)); log('eval_done',id=name,scoring_path=data.get('scoring_path'),rows=len(data['rows']))
    return data
def main():
    if sha(BASE_WASM)!=BASE_SHA: raise RuntimeError('BASELINE_SHA_MISMATCH')
    log('runner_start',baseline_sha256=BASE_SHA,panel=(TASK/'panel12.tsv').read_text().split(),max_workers=4,load_pause=170)
    basefile=ROOT/'evals/an_snace6e1__v3val.json'
    base={r['id']:r for r in json.load(open(basefile))}
    queue=[json.loads(s) for s in QUEUE.read_text().splitlines() if s.strip()]
    for j in queue:
        name=j['id']
        if (TASK/(name+'.done')).exists():
            continue
        wasm=BASE_WASM if name=='current_best' else build(j)
        data=eval_one(name,wasm)
        rows=data['rows']; rec=[]
        for r in rows:
            bid=r.get('episode') or r.get('id')
            b=base.get(bid,{})
            rec.append({'id':bid,'ate':r.get('ate_full'),'base_ate':b.get('ate'),'peak':r.get('peak_fuel_per_frame'),'base_peak':b.get('peak'),'error':r.get('error') or r.get('failure')})
        good=[x for x in rec if x['ate'] is not None and x['base_ate'] is not None]
        summary={'id':name,'wasm_sha256':sha(wasm),'n':len(good),'ate_mean':statistics.mean(x['ate'] for x in good) if good else None,'base_ate_mean':statistics.mean(x['base_ate'] for x in good) if good else None,'paired_d':statistics.mean(x['ate']-x['base_ate'] for x in good) if good else None,'peak_max':max((x['peak'] or 0) for x in good) if good else None,'base_peak_max':max((x['base_peak'] or 0) for x in good) if good else None,'records':rec}
        p=TASK/(name+'.summary.json'); p.write_text(json.dumps(summary,indent=2)+'\n'); log('summary',**{k:v for k,v in summary.items() if k!='records'})
        (TASK/(name+'.done')).write_text('done\n')
    log('queue_done',jobs=len(queue))
if __name__=='__main__':
    try: main()
    except Exception as e:
        log('error',message=repr(e)); raise
