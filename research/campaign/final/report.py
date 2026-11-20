"""Audit full declared coverage and report frozen confirmation results."""
import argparse,datetime,hashlib,json,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from research.guard_fusion.composite.score import consolidate
from research.guard_fusion.evaluate import summary
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--require-complete',action='store_true');a=p.parse_args()
    manifest=json.loads((HERE/'manifest.json').read_text());freeze=json.loads((HERE/'artifact-freeze.json').read_text());roster=json.loads((HERE/'roster.json').read_text())['flights'];raw=Path(manifest['raw_root']);lookup={f['id']:f for f in roster}
    if sha(HERE/'manifest.json')!=freeze['manifest_sha256'] or sha(HERE/'roster.json')!=manifest['roster_sha256']:raise ValueError('Manifest or roster changed after freeze')
    folder=HERE/'results'/('guard_median_final-'+freeze['sha256'][:8]);scores=folder/'scores.json'
    generated={f.stem for f in (raw/'bench').glob('*.zip')};missing=sorted(set(lookup)-generated)
    invalid=[];metadata={}
    for name in sorted(generated):
        f=lookup[name];record=json.loads((raw/'bench'/f'{name}.json').read_text());metadata[name]=record
        if record['seed']!=f['seed'] or record['scene']!=f['scene'] or record['audit']['frames']!=1200 or record['audit']['truth_integration_rms_m']>.05:invalid.append(name)
    events=[]
    for file in (raw/'status').glob('*.json'):
        events.append(json.loads(file.read_text()))
    secs=[e['seconds'] for e in events if e['status']=='ok'];bytes_total=sum(e.get('bytes',0) for e in events if e['status']=='ok')
    generation={'declared':192,'generated':len(generated),'missing':missing,'invalid':invalid,'total_archive_bytes':bytes_total,'per_flight_seconds_mean':float(np.mean(secs)) if secs else None,'per_flight_seconds_median':float(np.median(secs)) if secs else None,'successful_status_files':len(secs),'failed_status_files':sum(e['status']!='ok' for e in events)}
    report={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'metric':'mean_unaligned_ate_m','status':'incomplete','manifest_sha256':sha(HERE/'manifest.json'),'artifact_freeze':freeze,'generation':generation,'scope':manifest['scope'],'promotion':False,'no_tuning':'Rule and artifact frozen before any final-set guest evaluation; no final-set threshold selection'}
    if scores.exists():
        result=consolidate(scores,raw/'bench');scored={r['episode'] for r in result['rows']}
        # There may be generated episodes not yet present in a scoring snapshot.
        unscored=sorted(set(lookup)-scored);report['missing_evaluation']=unscored;report['snapshot_episodes']=len(scored)
        for row in result['rows']:
            f=lookup[row['episode']];row.update(scene=f['scene'],group=f['group'],catalog=f['catalog'],start_type=f['start_type'],setting=f['setting'],seed=f['seed'])
        report.update(summary=result['summary'],completed_flights=result['completed_flights'],zero_filled_flights=result['zero_filled_flights'],peak_fuel_per_frame=result['peak_fuel_per_frame'],origin_substitutions=result['origin_substitutions'],rows=result['rows'])
        report['splits']={}
        for tag in ['start_type','setting','scene']:
            report['splits'][tag]={value:summary([r['ate_full'] for r in result['rows'] if r[tag]==value]) for value in sorted({r[tag] for r in result['rows']})}
        if not missing and not invalid and not unscored:
            report['status']='complete_experimental_flight_confirmation'
            # Bootstrap complete scene clusters, preserving all 12 flights per scene.
            scenes=sorted({f['scene'] for f in roster});clusters=np.array([[r['ate_full'] for r in result['rows'] if r['scene']==scene] for scene in scenes]);rng=np.random.default_rng(20261120013);draw=clusters[rng.integers(0,len(scenes),size=(10000,len(scenes)))].reshape(10000,-1)
            report['scene_bootstrap90']={'mean_m':list(map(float,np.percentile(draw.mean(axis=1),[5,95]))),'median_m':list(map(float,np.percentile(np.median(draw,axis=1),[5,95]))),'scenes':len(scenes),'draws':10000}
    (HERE/'confirmation-report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['rows','splits','artifact_freeze']},indent=2))
    if a.require_complete and report['status']!='complete_experimental_flight_confirmation':raise SystemExit('Confirmation still incomplete; no full-set headline allowed')
if __name__=='__main__':main()
