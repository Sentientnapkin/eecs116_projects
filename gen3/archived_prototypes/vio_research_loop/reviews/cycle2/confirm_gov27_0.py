import hashlib, json, pathlib, sys, time
import numpy as np

ROOT=pathlib.Path('/data/backups/rganapa/Sebastian/eecs116_projects')
SHARED=pathlib.Path('/tmp/vio_loop2/shared')
TASK=pathlib.Path('/tmp/vio_research_loop/reviews/cycle2')
TASK.mkdir(parents=True,exist_ok=True)
wasm=pathlib.Path('/dev/shm/vio_loop3/efficient_round2/builds/gov27_0/solution.wasm')
baseline=pathlib.Path('/tmp/vio_loop2/shared/confirm48_baseline.json')
source=pathlib.Path('/data/backups/rganapa/Sebastian/gen3/agents/anchors/base_sn.c')
flags=pathlib.Path('/dev/shm/vio_loop3/efficient_round2/builds/gov27_0/flags.txt').read_text().strip()
expected_source='b09f81004e37646f32df6f5ba9f0e802ee2a1b9a9caa6b94caf2164c0a37a777'
expected_wasm='2608945c0ed985eeb02938ab131072672c4022b02ddca13286d01d680c9969fb'
expected_base='1a169f28916acd813f86a7b526efb8e8b646b3dda73e48cba51b12845c69b1b8'
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(source)==expected_source, 'source SHA mismatch'
assert sha(wasm)==expected_wasm, 'existing gov27_0 WASM SHA mismatch'
assert pathlib.Path('/tmp/vio_loop2/shared/inputs.ready').exists()
ready=json.loads(pathlib.Path('/tmp/vio_loop2/shared/inputs.ready').read_text())
assert ready.get('all_sha_verified') is True, 'shared inputs not fully verified'
base=json.loads(baseline.read_text())
assert base['baseline_sha256']==expected_base and len(base['rows'])==48
assert all(r.get('completed') and not r.get('failure') for r in base['rows']), 'baseline incomplete'
sys.path.insert(0,str(ROOT))
from research.single_model.run_variant import run_guest_fast
out=TASK/'eval'
score=run_guest_fast(wasm,SHARED/'confirm48',out,workers=2,name='gov27_0_confirm48')
sc=json.loads(score.read_text())
rows=sc['rows']; bm={r['episode']:r for r in base['rows']}
assert len(rows)==48, f'expected 48 returned records, got {len(rows)}'
assert len({r['episode'] for r in rows})==48, 'duplicate/missing episode ids'
assert {r['episode'] for r in rows}==set(bm), 'episode panel mismatch; no rows may be dropped'
rec=[]
for r in rows:
    b=bm[r['episode']]
    assert not r.get('error') and r.get('failure') is None and isinstance(r.get('ate_full'),(float,int)), f"failed evaluation {r['episode']}: {r}"
    assert isinstance(r.get('peak_fuel_per_frame'),(float,int)), f"missing fuel {r['episode']}"
    rec.append({'episode':r['episode'],'scene':b['scene'],'ate':r['ate_full'],'base_ate':b['ate_full'],
                'delta':r['ate_full']-b['ate_full'],'peak_fuel':r['peak_fuel_per_frame'],
                'base_peak_fuel':b['peak_fuel_per_frame'],'failure':r.get('failure')})
d=np.array([r['delta'] for r in rec]); rng=np.random.default_rng(20261127)
boots=np.empty(10000)
for i in range(len(boots)): boots[i]=rng.choice(d,size=len(d),replace=True).mean()
scene_names=sorted({r['scene'] for r in rec}); scene_groups={s:[r['delta'] for r in rec if r['scene']==s] for s in scene_names}
cb=np.empty(10000)
for i in range(len(cb)):
    chosen=rng.choice(scene_names,size=len(scene_names),replace=True)
    cb[i]=np.concatenate([np.array(scene_groups[s]) for s in chosen]).mean()
per_scene={s:{'n':len(v),'mean_delta':float(np.mean(v)),'median_delta':float(np.median(v)),
              'max_delta':float(np.max(v))} for s,v in scene_groups.items()}
result={'id':'gov27_0_confirm48','n':48,'episodes':len(rows),'scene_count':len(scene_names),
 'wasm_sha256':sha(wasm),'source_sha256':sha(source),'baseline_sha256':expected_base,'flags':flags,
 'active_parameters':{'GOV_B':2700000,'R5_DEC':0},'workers':2,'validation':'shared disjoint confirm48; exact 48 episode match; no row removal',
 'mean_ate':float(np.mean([r['ate'] for r in rec])),'median_ate':float(np.median([r['ate'] for r in rec])),
 'mean_delta_vs_full_current':float(d.mean()),'median_delta_vs_full_current':float(np.median(d)),
 'p95_delta_vs_full_current':float(np.percentile(d,95)),'worst_delta_vs_full_current':float(d.max()),
 'paired_bootstrap_flight_mean_delta_95ci':[float(x) for x in np.percentile(boots,[2.5,97.5])],
 'paired_bootstrap_scene_cluster_mean_delta_95ci':[float(x) for x in np.percentile(cb,[2.5,97.5])],
 'max_fuel':int(max(r['peak_fuel'] for r in rec)),'p95_fuel':float(np.percentile([r['peak_fuel'] for r in rec],95)),
 'full_current_max_fuel':int(max(r['base_peak_fuel'] for r in rec)),
 'fuel_reduction_fraction':float(1-max(r['peak_fuel'] for r in rec)/max(r['base_peak_fuel'] for r in rec)),
 'per_scene':per_scene,'records':rec,'finished_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
(TASK/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('n','mean_ate','median_ate','mean_delta_vs_full_current','median_delta_vs_full_current','worst_delta_vs_full_current','paired_bootstrap_flight_mean_delta_95ci','paired_bootstrap_scene_cluster_mean_delta_95ci','max_fuel','p95_fuel','full_current_max_fuel','fuel_reduction_fraction','per_scene')},indent=2),flush=True)
