"""Aggregate complete matched records; never discard failures or infer fuel."""
import json
from pathlib import Path
import statistics

import numpy as np

ROOT = Path(__file__).resolve().parent
MAIN = Path('/data/backups/rganapa/Sebastian/eecs116_projects/research')
BASE = Path('/data/backups/rganapa/Sebastian/baselines')
DEST = ROOT / 'results/eval/fusion-completion'


def metrics(rows):
    result = {'replays': len(rows), 'completed': sum(r['completed'] for r in rows),
        'attempted_frames': sum(r['frames_attempted'] for r in rows),
        'filled_frames': sum(r.get('filled_full', 0) or 0 for r in rows),
        'peak_whole_guest_fuel': max(r['peak_fuel_per_frame'] for r in rows),
        'failures': [r['episode'] for r in rows if not r['completed']],
        'above5m': [r['episode'] for r in rows if r.get('ate_full', float('inf')) > 5]}
    for label in ('full', '30s', '60s'):
        valid = [r['ate_'+label] for r in rows if 'ate_'+label in r]
        result[label] = {'available_replays': len(valid),
                         'mean_unaligned_ate_m': statistics.mean(valid) if valid else None}
    return result


def main():
    records = json.loads((MAIN/'data/native-campaign/dev-records.json').read_text())['records']
    assert len(records) == 120 and all(r['split'] == 'dev' for r in records)
    meta = {}
    for r in records:
        episode = r['flight_id'] + ('-crop5' if r['crop_s'] else '')
        with np.load(MAIN/'data/native-campaign/shards'/r['file']) as data:
            speed = float(np.linalg.norm(data['v'][0]))
        meta[episode] = {'catalog': r['catalog'], 'scene': r['scene'], 'parent': r['parent_sha256'],
            'crop_origin': str(r['crop_s']), 'actual_start_speed': 'above0.1' if speed > .1 else 'at_most0.1',
            'motion': 'backward/lateral' if r['backward_fraction']>.05 or r['lateral_fraction']>.1 else 'ordinary',
            'regime': r['regime']}
    inputs = {name:BASE/'runs'/name/'scores.json' for name in (
        'public-bd0-217-kfgrid-rebuild', 'public-bd0-217-velfusion',
        'campaign-bd0-217-kfgrid-rebuild', 'campaign-bd0-217-velfusion')}
    inputs['public-bd0-217-staged6r'] = BASE/'fuel/runs/public-kf-k2-staged2r/scores.json'
    inputs['campaign-bd0-217-staged6r'] = DEST/'campaign-bd0-217-staged6r.json'
    inputs.update({p.stem:p for p in DEST.glob('public-*-parity-repair-trace.json')})
    result = {'decision_metric':'equal-replay mean unaligned position RMSE', 'comparisons':{}, 'paired':{}}
    all_rows = {}
    for name,path in inputs.items():
        d=json.loads(path.read_text());rows=d['rows'];all_rows[name]=rows
        assert all('ate_full' in r for r in rows), (name,'incomplete result retained for investigation')
        groups={}
        if name.startswith('campaign'):
            assert set(r['episode'] for r in rows)==set(meta), name
            for field in ('catalog','scene','parent','crop_origin','actual_start_speed','motion','regime'):
                for value in sorted({m[field] for m in meta.values()}):
                    sub=[r for r in rows if meta[r['episode']][field]==value]
                    groups[f'{field}:{value}']=metrics(sub)
        else:
            assert len(rows)==10
        result['comparisons'][name]={'guest':d['guest'], 'metrics':metrics(rows),'groups':groups}
        if path.parent!=DEST:
            (DEST/(name+'.json')).write_text(json.dumps(d,indent=1))
    for setname in ('public','campaign'):
        control={r['episode']:r for r in all_rows[f'{setname}-bd0-217-kfgrid-rebuild']}
        for arm in ('velfusion','staged6r'):
            rows=all_rows[f'{setname}-bd0-217-{arm}']
            assert set(control)=={r['episode'] for r in rows}
            pairs=[]
            for r in rows:
                c=control[r['episode']];assert c['frames']==r['frames']
                pairs.append({'episode':r['episode'],'control':c['ate_full'],'candidate':r['ate_full'],
                              'delta_m':r['ate_full']-c['ate_full']})
            result['paired'][f'{setname}-{arm}']={'flights':pairs,
                'regressed_flights':sum(r['delta_m']>1e-8 for r in pairs),
                'max_regression_m':max(r['delta_m'] for r in pairs),
                'mean_delta_m':statistics.mean(r['delta_m'] for r in pairs)}
    (DEST/'fusion-completion-summary.json').write_text(json.dumps(result,indent=2))
    for name,d in result['comparisons'].items():print(name,d['metrics'])


if __name__=='__main__':main()
