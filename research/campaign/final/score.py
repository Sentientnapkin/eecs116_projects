"""Pipeline one frozen guest evaluation over each new confirmation episode.

Intermediate snapshots are progress only. The final report requires the full
192-flight manifest; ungenerated episodes are explicit incomplete coverage,
never silently omitted or replaced by a favorable flight.
"""
import argparse,datetime,hashlib,json,os,shutil,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from research.guard_fusion.composite.score import run_guest,consolidate
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');p.add_argument('--workers',type=int,default=16);p.add_argument('--batch',type=int,default=16);p.add_argument('--workers-file',type=Path,default=HERE/'eval-workers.txt');a=p.parse_args()
    manifest=json.loads((HERE/'manifest.json').read_text());frozen=json.loads((HERE/'artifact-freeze.json').read_text())
    if sha(HERE/'manifest.json')!=frozen['manifest_sha256']:raise ValueError('Final manifest changed after artifact freeze')
    if sha(HERE/'roster.json')!=manifest['roster_sha256']:raise ValueError('Roster changed after freeze')
    if sha(frozen['artifact'])!=frozen['sha256']:raise ValueError('Frozen guest SHA mismatch')
    raw=Path(manifest['raw_root']);episodes=raw/'bench';out=HERE/'results'
    cached=HERE/'frozen-composite.wasm'
    if not cached.exists():shutil.copyfile(frozen['artifact'],cached)
    if sha(cached)!=frozen['sha256']:raise ValueError('Local frozen guest mismatch')
    roster=json.loads((HERE/'roster.json').read_text())['flights'];expected={f['id'] for f in roster}
    folder=out/('guard_median_final-'+frozen['sha256'][:8]);folder.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();last_count=0
    existing=folder/'scores.json'
    if existing.exists():last_count=len(json.loads(existing.read_text()).get('guest',{}).get('archives',[]))
    while True:
        present={f.stem for f in episodes.glob('*.zip')};unexpected=present-expected
        if unexpected:raise ValueError('Unexpected episodes in confirmation raw folder: '+repr(sorted(unexpected)))
        count=len(present)
        if count and (count-last_count>=a.batch or count==192 or not a.watch):
            workers=int(a.workers_file.read_text().strip()) if a.workers_file.exists() else a.workers
            if not 1<=workers<=32:raise ValueError('Evaluation workers must be1..32')
            print(json.dumps({'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'action':'score_snapshot','available':count,'total':192,'workers':workers,'artifact_sha256':frozen['sha256']}),flush=True)
            scores=run_guest(cached,episodes,out,workers=workers,name='guard_median_final')
            last_count=count
            # Videos are diagnostic renderings, not needed for ATE/fuel/parity.
            removed=0
            for video in folder.glob('*/report/logs/*/trajectory.mp4'):
                removed+=video.stat().st_size;video.unlink()
            report=consolidate(scores,episodes)
            report.update(manifest_sha256=frozen['manifest_sha256'],artifact_freeze=frozen,confirmation_status='complete' if count==192 else 'progress_only',declared_flights=192,generated_flights=count,missing_generation=sorted(expected-present),seconds_since_score_driver_start=round(time.monotonic()-started,1),deleted_video_bytes=removed)
            (folder/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
            # A partial progress statistic is never a final leaderboard row.
            print(json.dumps({'action':'snapshot_finished','available':count,'completed':report['completed_flights'],'status':report['confirmation_status'],'wall_seconds':round(time.monotonic()-started,1)}),flush=True)
            if count==192:break
        if not a.watch:break
        time.sleep(10)
if __name__=='__main__':main()
