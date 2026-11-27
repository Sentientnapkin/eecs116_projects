#!/usr/bin/env python3
"""Finite resumable temporal-window experiments against shared fresh panels."""
import os,sys,json,time,hashlib,shutil,subprocess,statistics
from pathlib import Path
ROOT=Path('/data/backups/rganapa/Sebastian/eecs116_projects'); GEN=ROOT.parent/'gen3'
BASE=GEN/'scratch_up/gslv_s3_snace6e1.wasm'; SRC=GEN/'agents/anchors/base_sn.c'
CM=ROOT/'research/single_model/linejac/CMakeLists.txt'; TC=ROOT.parent/'tmp/viobench-toolchain'
NAT=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')
PAN=Path('/tmp/vio_loop2/shared'); WORK=Path('/tmp/vio_loop2/extreme'); OUT=Path('/dev/shm/vio_loop2/extreme')
FLAGS=('PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0 SN=1 NS_GCOST=1 MAX_CLONES=8 MAX_OBS=10 AN_ACE=1 AN_DTH=4.0 AN_CEF=6 EDGE=1 EDGE_MYTH=10.0')
# All are distinct changes to physical clone baseline / feature lifetime. Same track/update stack.
EXPS=[('uniform_ce6','AN_ACE=0 CLONE_EVERY=6 MAX_CLONES=8 MAX_OBS=10'),
      ('uniform_ce8','AN_ACE=0 CLONE_EVERY=8 MAX_CLONES=8 MAX_OBS=10'),
      ('depth_adapt_4_8','AN_ACE=1 AN_DTH=6.0 AN_CEF=8 AN_DA=0.25 MAX_CLONES=8 MAX_OBS=10'),
      ('long_window_4x12','AN_ACE=0 CLONE_EVERY=12 MAX_CLONES=4 MAX_OBS=6'),
      ('long_window_3x18','AN_ACE=0 CLONE_EVERY=18 MAX_CLONES=3 MAX_OBS=6')]
LIMIT=7200; NWORK=4

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def log(s):
 with (WORK/'worker.log').open('a') as f: f.write(time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime())+' '+s+'\n'); f.flush()
def build(exp,extra):
 target=OUT/'builds'/exp/'solution.wasm'; target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists(): return target
 sd=OUT/'builds'/exp/'src'; sd.mkdir(parents=True,exist_ok=True)
 shutil.copy2(SRC,sd/'solution.c'); shutil.copy2(CM,sd/'CMakeLists.txt')
 defs=' '.join('-D'+x for x in (FLAGS+' '+extra).split())
 b=sd/'build'; cmd=['cmake','-S',str(sd),'-B',str(b),f'-DCMAKE_TOOLCHAIN_FILE={TC}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',f'-DVIOBENCH_NATIVE_DIR={NAT}',f'-DCMAKE_C_FLAGS={defs}']
 r=subprocess.run(cmd,capture_output=True,text=True)
 if r.returncode: raise RuntimeError('configure failed: '+r.stdout[-2000:]+r.stderr[-2000:])
 r=subprocess.run(['cmake','--build',str(b),'-j2'],capture_output=True,text=True)
 if r.returncode: raise RuntimeError('build failed: '+r.stdout[-2000:]+r.stderr[-2000:])
 shutil.copy2(b/'solution.wasm',target); return target
def panel_base(batch):
 path=PAN/f'{batch}_baseline.json'
 d=json.loads(path.read_text()); rows=d['rows']
 return {r['episode']:r['ate_full'] for r in rows if r.get('ate_full') is not None}
def evalone(exp,wasm,batch):
 marker=WORK/f'{batch}_{exp}.done.json'
 if marker.exists(): return json.loads(marker.read_text())
 sys.path.insert(0,str(ROOT)); from research.single_model.run_variant import run_guest_fast
 score=run_guest_fast(wasm,PAN/batch,OUT/'evals'/batch,workers=NWORK,name=f'extreme_{batch}_{exp}')
 rows=json.loads(Path(score).read_text())['rows']; vals=[r['ate_full'] for r in rows if r.get('ate_full') is not None]
 if len(vals)!=len(list((PAN/batch).glob('*.zip'))): raise RuntimeError(f'incomplete {batch}/{exp}: {len(vals)}')
 result={'experiment':exp,'batch':batch,'wasm_sha256':sha(wasm),'n':len(vals),'mean_ate':statistics.mean(vals),'median_ate':statistics.median(vals),'max_peak_fuel':max(r.get('peak_fuel_per_frame',0) or 0 for r in rows),'by_episode':{r['episode']:r['ate_full'] for r in rows}}
 marker.write_text(json.dumps(result,indent=2)+'\n'); log(f'complete {batch}/{exp} mean={result["mean_ate"]:.6f} median={result["median_ate"]:.6f} fuel={result["max_peak_fuel"]} sha={result["wasm_sha256"]}')
 return result
def main():
 WORK.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
 ctl=build('zero_change_control','')
 expected=sha(BASE); actual=sha(ctl)
 (WORK/'zero_change_control.json').write_text(json.dumps({'expected_baseline_sha256':expected,'control_sha256':actual,'verified':expected==actual},indent=2)+'\n')
 if expected!=actual: raise RuntimeError(f'zero-change build mismatch: {actual} != {expected}; refusing variant comparison')
 deadline=time.monotonic()+LIMIT; log('queue start')
 sb=panel_base('screen24'); pending=[]; summary={}
 for exp,extra in EXPS:
  if time.monotonic()>deadline: break
  w=build(exp,extra); rr=evalone(exp,w,'screen24'); dif=[rr['by_episode'][k]-sb[k] for k in sb]
  # Confirm if meaningful mean gain, no large individual regressions; include fuel gate only in reporting.
  fuel_save=1.0-rr['max_peak_fuel']/3849899.0
  # Confirm genuinely cheaper candidates with a bounded ATE cost, plus clear accuracy gains.
  improve=(statistics.mean(dif)<-0.005 and max(dif)<0.40) or (fuel_save>=0.08 and statistics.mean(dif)<=0.10 and max(dif)<1.00)
  summary[exp]={'screen':{k:v for k,v in rr.items() if k!='by_episode'},'mean_delta':statistics.mean(dif),'max_regression':max(dif),'fuel_saving_vs_panel_control':fuel_save,'confirm':improve}
  log(f'screen gate {exp}: mean_delta={statistics.mean(dif):.6f} maxreg={max(dif):.6f} confirm={improve}')
  if improve: pending.append(exp)
 (WORK/'screen_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 if pending:
  cb=panel_base('confirm48')
  for exp in pending:
   if time.monotonic()>deadline: break
   rr=evalone(exp,build(exp,dict(EXPS)[exp]),'confirm48')
   dif=[rr['by_episode'][k]-cb[k] for k in cb]
   summary[exp]['confirm_summary']={'mean_delta':statistics.mean(dif),'median_delta':statistics.median(dif),'max_regression':max(dif),'mean_ate':rr['mean_ate'],'median_ate':rr['median_ate'],'max_peak_fuel':rr['max_peak_fuel']}
   (WORK/'results.json').write_text(json.dumps(summary,indent=2)+'\n')
 (WORK/'results.json').write_text(json.dumps(summary,indent=2)+'\n')
 log('queue done' if len(summary)==len(EXPS) else 'queue stopped at deadline')
if __name__=='__main__':
 try: main()
 except Exception as e:
  import traceback; log('ERROR '+repr(e)+'\n'+traceback.format_exc()); raise
