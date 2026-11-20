"""Summarize probe results against matching pinned per-flight baselines."""
import json,re,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
BASE=Path('/data/backups/rganapa/Sebastian/baselines/bench-fast/selected')

def summarize(tag,guest):
    p=ROOT/'research/results/eval/guard-fusion'/tag
    if not (p/'scores.json').exists():return None
    reference={r['episode']:r for r in json.loads((BASE/guest/'scores.json').read_text())['rows']}
    d=json.loads((p/'scores.json').read_text());rows=[]
    for r in d['rows']:
        if 'ate_full' not in r:continue
        name=r['episode'];old=reference[name];entry={'episode':name,'before':old['ate_full'],'after':r['ate_full'],'completed':r['completed'],'failure':r['failure'],'peak_fuel':r['peak_fuel_per_frame']}
        logs=next((p/name/'report/logs').glob('*/estimate.tum')).parent; original=next((BASE/guest/name/'report/logs').glob('*/estimate.tum')).parent
        entry['pose_bytes_equal']=(logs/'estimate.tum').read_bytes()==(original/'estimate.tum').read_bytes()
        entry['twist_bytes_equal']=(logs/'twist.txt').read_bytes()==(original/'twist.txt').read_bytes()
        stdout=(logs/'stdout.txt').read_text(errors='replace');stderr=(logs/'stderr.txt').read_text(errors='replace')
        entry['recoveries_s']=[float(v) for v in re.findall(r'vins_recovery t=([\d.]+)',stderr)]
        entry['initializations_s']=[float(v) for v in re.findall(r'initialized at t=([\d.]+)',stdout)]
        if 'TEL ov ' in stderr:
            tel=[line for line in stderr.splitlines() if line.startswith('TEL ov ')]
            entry['telemetry_frames']=len(tel)
            entry['graph_guarded_frames']=sum('guarded=0/0' not in line for line in tel)
            for field in ['spread','cost','factors']:
                values=[float(v) for line in tel for v in re.findall(r'\b'+field+r'=([\d.e+-]+)',line)]
                if values:entry[field+'_range']=[min(values),max(values)]
        rows.append(entry)
    slices={}
    for name,pred in [('all',lambda r:True),('clean_under1',lambda r:r['before']<1),('baseline_over10',lambda r:r['before']>10)]:
        sub=[r for r in rows if pred(r)]
        if sub:slices[name]={'n':len(sub),'before_mean':float(np.mean([r['before'] for r in sub])),'after_mean':float(np.mean([r['after'] for r in sub])),'max_regression':max(r['after']-r['before'] for r in sub),'pose_bytes_equal':all(r['pose_bytes_equal'] for r in sub),'completed':sum(r['completed'] for r in sub)}
    return {'tag':tag,'planned':len(d['rows']),'scored':len(rows),'slices':slices,'rows':rows,'status':'exploratory'}

def main():
    names=[('vins-recovery-probe','vins_mono-f368cf2c'),('vins-recovery-v2-probe','vins_mono-f368cf2c'),('vins-recovery-v3-tails','vins_mono-f368cf2c'),('vins-recovery-fault20-v3','vins_mono-f368cf2c'),('openvins-physical-probe','openvins-c6cd96bc'),('openvins-telemetry-parity','openvins-c6cd96bc')]
    report={tag:summarize(tag,guest) for tag,guest in names};report={k:v for k,v in report.items() if v}
    target=ROOT/'research/results/eval/guard-fusion/vio-source-summary.json';target.write_text(json.dumps(report,indent=2)+'\n')
    for key,v in report.items():print(key,v['scored'],'/',v['planned'],json.dumps(v['slices']))
if __name__=='__main__':main()
