"""Freeze a fresh 192-flight confirmation roster before simulation or scoring."""
import argparse,datetime,hashlib,json,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def collect_seeds(value):
    if isinstance(value,dict):
        if isinstance(value.get('seed'),int):yield value['seed']
        for item in value.values():yield from collect_seeds(item)
    elif isinstance(value,list):
        for item in value:yield from collect_seeds(item)

def main():
    p=argparse.ArgumentParser();p.add_argument('--artifact',type=Path);a=p.parse_args()
    if a.artifact:
        freeze=HERE/'artifact-freeze.json'
        data={'declared_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifest_sha256':sha(HERE/'manifest.json'),'artifact':str(a.artifact.resolve()),'sha256':sha(a.artifact),'config_sha256':sha(HERE/'selected_config_median.json'),'rule':'frozen_v3_median_rule_with_v4_init_and_containment_fixes','status':'experimental_confirmation_only_not_G1_promotion'}
        with freeze.open('x') as f:json.dump(data,f,indent=2);f.write('\n')
        print(json.dumps(data,indent=2));return
    if (HERE/'manifest.json').exists():raise FileExistsError('Manifest already frozen; never rewrite it')
    config=ROOT/'research/guard_fusion/selected_config_median.json';(HERE/'selected_config_median.json').write_bytes(config.read_bytes())
    scanned=[];seeds=set();clean_hssd=set()
    for file in sorted((ROOT/'research/configs').glob('*.json')):
        try:data=json.loads(file.read_text())
        except (ValueError,UnicodeDecodeError):continue
        seeds.update(collect_seeds(data));scanned.append({'path':str(file.relative_to(ROOT)),'sha256':sha(file)})
        if file.name.startswith('server_'):
            clean_hssd.update(f['scene'] for f in data.get('flights',[]) if f.get('group')=='clean' and f.get('catalog','').startswith('hssd'))
    campaign=json.loads((ROOT/'research/configs/native_campaign.json').read_text())
    reserved={f['scene'] for f in campaign['flights'] if f['split']=='test'}
    clean_hssd-=reserved
    # The existing server rosters contain no clean HSSD scenes. No development,
    # training or reserved HSSD scene is silently relabeled as clean.
    if clean_hssd:raise RuntimeError('Unexpected eligible clean HSSD; revise design before freezing')
    scenes=[f'ProcTHOR-Train-{i}' for i in [*range(150,162),*range(176,180)]]
    assert not set(scenes)&reserved
    rng=random.Random(20261120013);flights=[];seed=9800000
    presets={}
    fast=json.loads((ROOT/'research/configs/server_fast_pool.json').read_text())['flights']
    for f in fast:presets[f['setting']]=f['task_overrides']
    assert 'K' in presets and 'K2' in presets
    for scene in scenes:
        for start in ['static','mid']:
            for setting in ['K','K2']:
                for index in range(3):
                    while seed in seeds:seed+=1
                    crop=round(rng.uniform(3.,40.)*20)/20 if start=='mid' else 0.
                    flights.append({'id':f'guardfinal-{scene}-{start}-{setting}-{index:02d}','split':'bench','group':'clean','catalog':'procthor','scene':scene,'seed':seed,'seconds':round(60.+crop,2),'output_seconds':60,'regime':'benchmark','hold_seconds':.2 if crop else 1.,'waypoints_per_second':.8,'task_overrides':presets[setting],'setting':setting,'start_type':start,**({'crop_start_s':crop} if crop else {})})
                    seeds.add(seed);seed+=1
    rng.shuffle(flights)
    roster={'seed':20261120013,'spec':'192 fresh confirmation flights; fixed K/K2 server-style settings, 96 static + 96 mid-start, 60 s after crop; 16 permitted ProcTHOR clean scenes balanced','flights':flights}
    manifest={'declared_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'sealed_confirmation_of_experimental_rule_not_G1_promotion','flights':192,'scene_count':16,'static':96,'mid':96,'output_seconds':60,'first_flight_seed':min(f['seed'] for f in flights),'last_flight_seed':max(f['seed'] for f in flights),'seed_collision_policy':'exclude every integer seed in all current research/configs JSON files before assigning','config_sha256':sha(config),'rule_config':'selected_config_median.json','artifact_policy':'artifact-freeze.json must be created with exact v4 wasm SHA before the first evaluation; generation may start after rule freeze','scope':'new seeds/flights in previously used clean scenes; flight-held-out confirmation, not scene-held-out validation','hssd_clean_scenes':[],'hssd_note':'No clean HSSD scene exists in the benchmark rosters; none relabeled','forbidden_procthor':[162,163,164,165,172,173,174,175],'reserved_campaign_scenes':sorted(reserved),'raw_root':'/data/backups/rganapa/Sebastian/gen/raw-guard-final','gpu':7,'generation_workers_max':32,'evaluation_workers_max':32,'allowed_retries':'same declared flight/seed only after infrastructure failure; no substitutions or dropping failures','selection_policy':'score the fixed guest exactly once on each generated episode; no result-dependent tuning or threshold changes','metrics':['mean_unaligned_ate_m','median_unaligned_ate_m','tail_counts','filled_frames','whole_guest_peak_fuel_per_frame'],'scanned_configs':scanned}
    roster_bytes=(json.dumps(roster,indent=2)+'\n').encode();manifest['roster_sha256']=hashlib.sha256(roster_bytes).hexdigest()
    with (HERE/'roster.json').open('xb') as f:f.write(roster_bytes)
    with (HERE/'manifest.json').open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ['scanned_configs','reserved_campaign_scenes']},indent=2))
if __name__=='__main__':main()
