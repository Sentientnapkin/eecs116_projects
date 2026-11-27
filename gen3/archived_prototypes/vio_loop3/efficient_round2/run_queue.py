import json, shutil, subprocess, hashlib, statistics, time, sys, math
from pathlib import Path
TASK=Path('/tmp/vio_loop3/efficient_round2'); BULK=Path('/dev/shm/vio_loop3/efficient_round2')
G=Path('/data/backups/rganapa/Sebastian/gen3'); ROOT=G.parent/'eecs116_projects'; SRC=G/'agents/anchors/base_sn.c'
SRCSHA='b09f81004e37646f32df6f5ba9f0e802ee2a1b9a9caa6b94caf2164c0a37a777'; BASESHA='1a169f28916acd813f86a7b526efb8e8b646b3dda73e48cba51b12845c69b1b8'
SHARED=Path('/tmp/vio_loop2/shared'); CM=ROOT/'research/single_model/linejac/CMakeLists.txt'; TC=G.parent/'tmp/viobench-toolchain'; NAT=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')
FLAGS=Path('/tmp/vio_loop2/fuel/control.flags').read_text().strip()+' EDGE=1 EDGE_MYTH=10.0'
QUEUE=[{'id':f'gov{b}_{d}', 'budget':b*100000.0,'dec':d} for b in (21,27) for d in (0,4)]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def log(**d):
 with (TASK/'status.jsonl').open('a') as f: f.write(json.dumps({'utc':time.strftime('%FT%TZ',time.gmtime()),**d})+'\n')
def percentile(x,p):
 x=sorted(x)
 if not x:return None
 z=(len(x)-1)*p; lo=int(z); hi=min(lo+1,len(x)-1); return x[lo]+(x[hi]-x[lo])*(z-lo)
if sha(SRC)!=SRCSHA: raise RuntimeError('source hash mismatch')
if sha(G/'scratch_up/gslv_s3_snace6e1.wasm')!=BASESHA: raise RuntimeError('baseline wasm mismatch')
if not (SHARED/'inputs.ready').exists(): raise RuntimeError('complete verified inputs missing')
ready=json.loads((SHARED/'inputs.ready').read_text())
if ready.get('all_sha_verified') is not True: raise RuntimeError('inputs not fully verified')
base=json.loads((SHARED/'screen24_baseline.json').read_text())
if base.get('baseline_sha256')!=BASESHA: raise RuntimeError('full-current reference mismatch')
sys.path.insert(0,str(ROOT)); from research.single_model.run_variant import run_guest_fast
needle='''static void gov_take_track(int i, int *rw, int cap, int *nb) {
    Obs *o = &tracks[i].obs;
    if (*nb >= MAX_BATCH) return;
    int m = gov_fit(o, *rw, cap);'''
replacement='''#ifndef R5_DEC
#define R5_DEC 0
#endif
static void gov_take_track(int i, int *rw, int cap, int *nb) {
    Obs *o = &tracks[i].obs;
    if (*nb >= MAX_BATCH) return;
    if (R5_DEC >= 3 && o->n > R5_DEC) {
        Obs d = *o; int n = o->n;
        for (int j = 0; j < R5_DEC; j++) {
            int k = (int)((double)j * (n - 1) / (R5_DEC - 1) + 0.5);
            d.cid[j] = o->cid[k]; d.x[j] = o->x[k]; d.y[j] = o->y[k];
        }
        d.n = R5_DEC;
        if (*rw + 2 * d.n - 3 > cap) return;
        *rw += 2 * d.n - 3;
        batch[*nb] = d; batch[*nb].tid = i; batch[*nb].px = tracks[i].x; batch[*nb].py = tracks[i].y; (*nb)++;
        o->cid[0] = o->cid[n - 1]; o->x[0] = o->x[n - 1]; o->y[0] = o->y[n - 1]; o->n = 1;
        return;
    }
    int m = gov_fit(o, *rw, cap);'''
for exp in QUEUE:
 name=exp['id']; w=BULK/'builds'/name/'solution.wasm'; d=FLAGS+f" GOV_B={exp['budget']} R5_DEC={exp['dec']}"
 if not w.exists():
  s=SRC.read_text()
  if s.count(needle)!=1: raise RuntimeError(f'{name}: insertion anchor count {s.count(needle)}')
  sd=w.parent/'src'; bd=w.parent/'build'; sd.mkdir(parents=True,exist_ok=True)
  (sd/'solution.c').write_text(s.replace(needle,replacement)); shutil.copy2(CM,sd/'CMakeLists.txt'); (w.parent/'flags.txt').write_text(d+'\n')
  cf=' '.join('-D'+x for x in d.split())
  for cmd in [['cmake','-S',str(sd),'-B',str(bd),f'-DCMAKE_TOOLCHAIN_FILE={TC}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',f'-DVIOBENCH_NATIVE_DIR={NAT}',f'-DCMAKE_C_FLAGS={cf}'],['cmake','--build',str(bd)]]:
   p=subprocess.run(cmd,capture_output=True,text=True)
   if p.returncode: raise RuntimeError(f'{name} build failed: {p.stderr[-3000:]}')
  shutil.copy2(bd/'solution.wasm',w)
 log(event='built',id=name,wasm_sha256=sha(w),flags=d,bytes=w.stat().st_size)
 score_path=run_guest_fast(w,SHARED/'screen24',BULK/'evals'/name,workers=4,name='eff2_'+name)
 rows=json.loads(Path(score_path).read_text())['rows']; bm={r['episode']:r for r in base['rows']}; rec=[]
 for r in rows:
  b=bm.get(r.get('episode'),{}); rec.append({'episode':r.get('episode'),'ate':r.get('ate_full'),'base_ate':b.get('ate_full'),'peak_fuel':r.get('peak_fuel_per_frame'),'base_peak_fuel':b.get('peak_fuel_per_frame'),'failure':r.get('failure')})
 good=[r for r in rec if isinstance(r['ate'],(int,float)) and isinstance(r['base_ate'],(int,float)) and isinstance(r['peak_fuel'],(int,float)) and isinstance(r['base_peak_fuel'],(int,float))]
 ds=[r['ate']-r['base_ate'] for r in good]; peaks=[r['peak_fuel'] for r in good]
 byscene={}
 for r in good:
  scene=r['episode'].split('-')[1] if r['episode'] and '-' in r['episode'] else 'unknown'; byscene.setdefault(scene,[]).append(r['ate']-r['base_ate'])
 summary={'id':name,'budget':exp['budget'],'dec':exp['dec'],'n':len(good),'wasm_sha256':sha(w),'flags':d,'mean_ate':statistics.mean([r['ate'] for r in good]) if good else None,'median_ate':statistics.median([r['ate'] for r in good]) if good else None,'paired_delta_mean_vs_full_current':statistics.mean(ds) if ds else None,'paired_delta_median_vs_full_current':statistics.median(ds) if ds else None,'paired_delta_p95_vs_full_current':percentile(ds,.95),'paired_delta_worst_vs_full_current':max(ds) if ds else None,'peak_wasm_fuel_max':max(peaks) if peaks else None,'peak_wasm_fuel_p95':percentile(peaks,.95),'full_current_peak_wasm_fuel_max':max([r['base_peak_fuel'] for r in good],default=None),'per_scene_delta_vs_full_current':{k:statistics.mean(v) for k,v in byscene.items()},'records':rec}
 (TASK/(name+'.summary.json')).write_text(json.dumps(summary,indent=2)+'\n'); log(event='screen24',id=name,n=len(good),paired_delta=summary['paired_delta_mean_vs_full_current'],peak=summary['peak_wasm_fuel_max'])
(TASK/'COMPLETE').write_text('queue exhausted\n');log(event='complete')
