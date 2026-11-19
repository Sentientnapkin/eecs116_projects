"""Audit saved metered public/campaign-dev replays; never rerun inference or access reserved splits.
Run using venv-viobench-9b1b079/bin/python. Preserve historical eligible30, add capped30 for all crops.
"""
import argparse, hashlib, json, os, re, subprocess, sys
from pathlib import Path
import numpy as np
SRC=Path(os.environ.get('VIOBENCH_SRC','/dev/shm/sebastian-vio/viobench'));sys.path.insert(0,str(SRC))
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
ROOT=Path('/data/backups/rganapa/Sebastian');RUNS=ROOT/'baselines/runs'
def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def aggregate(rows):
 out={'replays':len(rows),'parents':len({r['parent'] for r in rows}),'scenes':len({r['scene'] for r in rows})}
 for k in ['ate_capped30','ate_eligible30','ate_eligible60','ate_full']:
  v=[r[k] for r in rows if r.get(k) is not None];out[k]={'n':len(v),'mean_m':float(np.mean(v)) if v else None}
 v=[r['init_delay_s'] for r in rows if r.get('init_delay_s') is not None]
 out.update(initialized=len(v),init_delay_range_s=[min(v),max(v)] if v else None,completed=sum(r['completed'] for r in rows),frames=sum(r['frames'] for r in rows),filled=sum(r['filled'] for r in rows),peak_step_fuel=max(r['peak_step_fuel'] for r in rows),peak_init_fuel=max(r['init_fuel'] for r in rows),over5m=sum(r['ate_full']>5 for r in rows))
 if not any(r['init_marker_applicable'] for r in rows):
  out['initialized']=None
  out['initialization_note']='Not applicable: learned guests do not emit the OpenVINS initialization marker.'
 return out
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',default='results/eval/baseline-finish-audit.json');a=p.parse_args()
 pin=subprocess.check_output(['git','-C',str(SRC),'rev-parse','HEAD'],text=True).strip()
 assert pin=='9b1b07906aff5a3e6f00155e7aecf967d90aa960',pin
 assert not subprocess.check_output(['git','-C',str(SRC),'diff','HEAD','--'],text=True),'Modified pinned evaluator source'
 recs=json.loads((ROOT/'eecs116_projects/research/data/native-campaign/dev-records.json').read_text())['records'];mapping={(r['flight_id'],r['crop_s']):r for r in recs};cache={};outputs={}
 names=['public-openvins','campaign-openvins','public-b-d0','campaign-b-d0','public-n2-218-ungated','campaign-n2-218-ungated','public-n2-218-gated','campaign-n2-218-gated','public-bd0-kfgrid','campaign-bd0-217-kfgrid']
 for name in names:
  run=RUNS/name;guest=json.loads((run/'scores.json').read_text())['guest'];assert digest(guest['wasm'])==guest['sha256'],name;rows=[]
  for archive in guest['archives']:
   archive=Path(archive);stem=archive.stem;crop=5 if stem.endswith('-crop5') else 0;parent=stem.removesuffix('-crop5');rec=mapping.get((parent,crop))
   if name.startswith('campaign'):assert rec is not None and rec['split']=='dev'
   if str(archive) not in cache:
    e=read_episode(archive,frames='none');truth=e.ground_truth_state();t=e.frame_times-e.frame_times[0];speed=np.linalg.norm(truth[:,7:10],axis=1)
    cache[str(archive)]={'truth':truth,'time':e.frame_times,'elapsed':t,'sha256':digest(archive),'start_speed':float(np.mean(speed[t<.25])),'scene':e.meta.get('scene')}
   c=cache[str(archive)];truth=c['truth'];t=c['elapsed'];work=run/stem/'report';report=json.loads((work/'report.json').read_text())['episodes'][0];log=next((work/'logs').glob('*/estimate.tum'));raw=load_estimates(log,c['time']);est=fill_missing_states(raw);err2=np.sum((truth[:,:3]-est[:,:3])**2,axis=1);m=re.search(r'initialized at t=([0-9.]+)',(log.parent/'stdout.txt').read_text());s=c['start_speed']
   r={'episode':stem,'parent':parent,'scene':c['scene'],'crop_s':crop,'catalog':rec['catalog'] if rec else 'public-procthor','regime':rec['regime'] if rec else 'public','historical_motion':'hard' if rec and (rec['backward_fraction']>.05 or rec['lateral_fraction']>.10) else 'ordinary','actual_start_speed_mps':s,'actual_start_bin':'static<=0.05' if s<=.05 else 'moving>=0.20' if s>=.20 else 'intermediate','archive_sha256':c['sha256'],'ate_capped30':float(np.sqrt(np.mean(err2[:600]))),'ate_eligible30':float(np.sqrt(np.mean(err2[:600]))) if len(err2)>=600 else None,'ate_eligible60':float(np.sqrt(np.mean(err2[:1200]))) if len(err2)>=1200 else None,'ate_full':float(np.sqrt(np.mean(err2))),'duration_s':float(t[-1]),'init_timestamp_s':float(m.group(1)) if m else None,'init_delay_s':float(m.group(1))-float(c['time'][0]) if m else None,'frames':report['frames'],'frames_attempted':report['frames_attempted'],'completed':report['completed'],'filled':report['metrics']['filled_frames'],'failure':report['failure'],'peak_step_fuel':report['fuel_per_frame_max'],'init_fuel':report['fuel_init']}
   r['init_marker_applicable']=name.endswith('openvins')
   assert abs(r['ate_full']-report['metrics']['ate_rmse'])<1e-5
   if rec and crop==0:assert c['sha256']==rec['parent_sha256']
   rows.append(r)
  groups={'all':aggregate(rows)}
  for field in ['catalog','crop_s','actual_start_bin','historical_motion','regime','scene','parent']:
   for value in sorted({str(r[field]) for r in rows}):groups[field+':'+value]=aggregate([r for r in rows if str(r[field])==value])
  outputs[name]={'guest':guest,'groups':groups,'rows':rows};print(name,groups['all'],flush=True)
 out={'source_pin':'9b1b07906aff5a3e6f00155e7aecf967d90aa960','scoring':'direct first-camera position RMSE; no alignment; pinned evaluator origin fill; all guests zero filled','criteria_unchanged':True,'historical_motion_labels':'manifest full-crop backward_fraction>.05 or lateral_fraction>.10; horizon-independent labels retained','actual_start_speed':'mean camera ground-truth speed over first 0.25 seconds; diagnostic only','results':outputs};dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(out,indent=1)+'\n')
if __name__=='__main__':main()
