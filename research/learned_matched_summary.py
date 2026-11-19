"""Aggregate complete matched learned replay results, preserving seed and parent dependence."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT/'results/loop/provided-comparison'
OUT = ROOT/'results/eval/provided-comparison'


def load(name, count):
    rows = [json.loads(p.read_text()) for p in sorted((DATA/name).glob('*/result.json'))]
    return rows if len(rows)==count else None


def summary(rows):
    result = dict(replays=len(rows), parents=len({r['archive'] for r in rows}),
                  scenes=len({r['scene'] for r in rows}),
                  mean_unaligned_ate_m=float(np.mean([r['mean_unaligned_ate_m'] for r in rows])),
                  completed=sum(r['completed'] for r in rows), filled_frames=sum(r['filled_frames'] for r in rows),
                  metered_wasm=all(r['metered_wasm'] for r in rows))
    fuels=[r['peak_fuel_per_frame'] for r in rows if r['peak_fuel_per_frame'] is not None]
    if fuels: result['peak_fuel_per_frame']=max(fuels)
    result['prefixes']={str(n):dict(replays=len(vals),mean_unaligned_ate_m=float(np.mean(vals)))
                        for n in (600,601,1200)
                        if (vals:=[r['prefix_frames'][str(n)] for r in rows if str(n) in r.get('prefix_frames',{})])}
    return result


def paired(candidate, control):
    bykey=lambda rows:{(r['archive'],r['crop_s']):r for r in rows}
    c,b=bykey(candidate),bykey(control)
    assert c.keys()==b.keys()
    keys=sorted(c)
    scenes=sorted({c[k]['scene'] for k in keys})
    deltas={s:[c[k]['mean_unaligned_ate_m']-b[k]['mean_unaligned_ate_m'] for k in keys if c[k]['scene']==s] for s in scenes}
    rng=np.random.default_rng(217)
    draws=[]
    for _ in range(5000):
        sample=rng.choice(scenes,size=len(scenes),replace=True)
        draws.append(np.mean([v for s in sample for v in deltas[s]]))
    return dict(mean_difference_m=float(np.mean([v for d in deltas.values() for v in d])),
                scene_bootstrap_interval90_m=np.quantile(draws,[.05,.95]).tolist(),
                per_scene={s:float(np.mean(d)) for s,d in deltas.items()},
                per_parent={a:float(np.mean([c[k]['mean_unaligned_ate_m']-b[k]['mean_unaligned_ate_m'] for k in keys if k[0]==a])) for a in sorted({k[0] for k in keys})},
                caution='Single-scene public interval has no generalization meaning; scene bootstrap does not model training seed variation.')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for roster,count in [('public',10),('campaign-native',120)]:
        control=load('bd0-'+roster+'-217',count)
        if control is None:continue
        report={'control':summary(control),'control_rows':control,'seeds':{}}
        for seed in (217,218,219):
            rows=load('n2-'+roster+'-'+str(seed),count)
            if rows is None:continue
            groups={'all':rows}
            for catalog in sorted({r['catalog'] for r in rows}):groups['catalog:'+catalog]=[r for r in rows if r['catalog']==catalog]
            for start in ('nominal','crop5','speed_gt_0.1','speed_le_0.1'):
                selected=[r for r in rows if (r['crop_s']==0 if start=='nominal' else r['crop_s']==5 if start=='crop5' else r.get('start_speed_mps',0)>.1 if start=='speed_gt_0.1' else r.get('start_speed_mps',0)<=.1)]
                if selected:groups['start:'+start]=selected
            for regime in sorted({r.get('regime','public') for r in rows}):groups['regime:'+regime]=[r for r in rows if r.get('regime','public')==regime]
            report['seeds'][str(seed)]={'summary':summary(rows),'groups':{k:summary(v) for k,v in groups.items()},'paired_vs_submitted_seed217':paired(rows,control),'rows':rows}
        (OUT/(roster+'-learned-matched.json')).write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
