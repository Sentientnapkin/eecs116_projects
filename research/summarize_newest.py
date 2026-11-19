"""Audit complete actual-Wasm reports; report equal-flight unaligned means and dependence."""
import hashlib
import json
from pathlib import Path
import numpy as np
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states

root = Path(__file__).resolve().parent
base = root / 'results/loop/new-model-wasm'
records = json.loads(Path('/data/backups/rganapa/Sebastian/eecs116_projects/research/data/native-campaign/dev-records.json').read_text())['records']
mapping = {(r['flight_id'], r['crop_s']): r for r in records}


def group(rows):
    result = {'replays': len(rows), 'parents': len({r['parent'] for r in rows}), 'scenes': len({r['scene'] for r in rows}),
              'completed':sum(r['completed'] for r in rows), 'frames':sum(r['frames'] for r in rows),
              'filled':sum(r['filled_full'] for r in rows), 'peak_whole_guest_fuel':max(r['peak_fuel_per_frame'] for r in rows),
              'over5m':[r['episode'] for r in rows if r['ate_full']>5]}
    for metric in ['ate_full', 'ate_capped30', 'ate_eligible30', 'ate_eligible60']:
        values = [r[metric] for r in rows if r[metric] is not None]
        result[metric] = {'n': len(values), 'mean_m':float(np.mean(values)) if values else None}
    return result


results = {}
for name in ['public-seed217-opencv510', 'campaign-seed217-opencv510',
             'public-seed217-opencv510-isolated', 'campaign-seed217-opencv510-isolated']:
    directory = base / name
    saved = json.loads((directory / 'scores.json').read_text())
    guest = saved['guest']
    assert hashlib.sha256(Path(guest['wasm']).read_bytes()).hexdigest() == guest['sha256']
    rows = []
    for archive, original in zip(guest['archives'], saved['rows']):
        archive = Path(archive)
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == guest['archive_sha256'][str(archive)]
        crop = 5 if archive.stem.endswith('-crop5') else 0
        parent = archive.stem.removesuffix('-crop5')
        record = mapping.get((parent, crop))
        if name.startswith('campaign'): assert record is not None and record['split'] == 'dev'
        episode = read_episode(archive, frames='none')
        truth = episode.ground_truth_state()
        log = next((directory / archive.stem / 'report/logs').glob('*/estimate.tum'))
        estimates = fill_missing_states(load_estimates(log, episode.frame_times))
        errors = np.sum((truth[:, :3] - estimates[:, :3])**2, axis=1)
        rmse = lambda n:float(np.sqrt(np.mean(errors[:n])))
        elapsed = episode.frame_times - episode.frame_times[0]
        speed = float(np.mean(np.linalg.norm(truth[elapsed < .25, 7:10], axis=1)))
        row = {**original, 'archive_sha256':guest['archive_sha256'][str(archive)], 'crop_s':crop,
               'parent':record['parent_sha256'] if record else parent,
               'catalog':record['catalog'] if record else 'public-procthor',
               'historical_motion':'hard' if record and (record['backward_fraction']>.05 or record['lateral_fraction']>.1) else 'ordinary',
               'initial_speed_mps':speed, 'speed_bin':'static<=0.05' if speed<=.05 else 'moving>=0.2' if speed>=.2 else 'intermediate',
               'ate_full':rmse(len(errors)), 'ate_capped30':rmse(min(600,len(errors))),
               'ate_eligible30':rmse(600) if len(errors)>=600 else None,
               'ate_eligible60':rmse(1200) if len(errors)>=1200 else None}
        assert abs(row['ate_full'] - original['ate_reported_full']) < 1e-5
        rows.append(row)
    groups = {'all':group(rows)}
    for field in ['catalog', 'crop_s', 'historical_motion', 'speed_bin', 'scene', 'parent']:
        for value in sorted({str(r[field]) for r in rows}):
            groups[field+':'+value] = group([r for r in rows if str(r[field])==value])
    results[name] = {'guest':guest, 'groups':groups, 'rows':rows}
out = root/'results/eval/new-model-wasm'
out.mkdir(parents=True, exist_ok=True)
(out/'matched-results.json').write_text(json.dumps({'metric':'mean unaligned position RMSE',
    'prefixes':'continuous first600 capped/eligible; first1200 eligible; no resets at prefix boundaries',
    'historical_motion':'full-crop manifest fractions, retained for continuity', 'results':results},indent=2)+'\n')
for name,data in results.items():print(name,json.dumps(data['groups']['all']),flush=True)

reference = json.loads((root.parent.parent/'session-integration/research/results/eval/baseline-finish-audit.json').read_text())['results']
paired = {}
for roster, name in [('public', 'public-seed217-opencv510-isolated'), ('campaign', 'campaign-seed217-opencv510-isolated')]:
    previous = reference['public-b-d0' if roster == 'public' else 'campaign-b-d0']
    controls = {r['episode']:r for r in previous['rows']}
    rows = []
    for row in results[name]['rows']:
        control = controls[row['episode']]
        assert row['archive_sha256'] == control['archive_sha256']
        rows.append({'episode':row['episode'], 'scene':row['scene'], 'parent':row['parent'],
                     'old_ate':control['ate_full'], 'new_ate':row['ate_full'],
                     'difference':row['ate_full'] - control['ate_full']})
    groups = {}
    for field in ['scene', 'parent']:
        groups[field] = {key:float(np.mean([r['difference'] for r in rows if r[field]==key])) for key in sorted({r[field] for r in rows})}
    regressions = [r for r in rows if r['difference'] > 0]
    paired[roster] = {'control':'submitted B-D0 seed217; actual Wasm', 'candidate':'newest kf_grid INPUT model seed217; actual Wasm',
                      'interpretation':'matched artifact benchmark, not an isolated component/training ablation',
                      'mean_difference_m':float(np.mean([r['difference'] for r in rows])),
                      'improved':sum(r['difference'] < 0 for r in rows), 'regressed':len(regressions),
                      'largest_regression':max(regressions, key=lambda r:r['difference']) if regressions else None,
                      'groups':groups, 'rows':rows}
(out/'paired-submitted-control.json').write_text(json.dumps(paired,indent=2)+'\n')
