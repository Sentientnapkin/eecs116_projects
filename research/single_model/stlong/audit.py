"""Metadata-only exclusions followed by allowlisted cache access; no sealed payloads."""
import collections, hashlib, json, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; SM=HERE.parent; ROOT=SM.parents[1]; BASE=ROOT.parent
fold=lambda c,s:int(hashlib.sha256(f'{c}:{s}'.encode()).hexdigest()[:8],16)%5

def manifests():
    bad={f['scene'] for f in json.load(open(SM/'servertail/gen/st2.json'))['flights']}
    bad|={f['scene'] for f in json.load(open(SM/'learnvel/gen/st3.json'))['flights']}
    # Holdout filenames and sidecar metadata only, never episode contents.
    ho=set()
    for z in (BASE/'gen/raw-holdout/final').glob('*.zip'):
        for sub in ['bench','final','partial']:
            p=z.parent.parent/sub/(z.stem+'.json')
            if p.exists():
                d=json.load(open(p)); ho.add((d['catalog'],d['scene'])); break
        else: raise RuntimeError('Holdout metadata missing '+z.stem)
    selected={p.stem for p in (BASE/'gen/raw-fast/selected').glob('*.zip')}
    rows=[]; excluded=collections.Counter()
    # Only inspect metadata for existing train/val cache files, never open a fold-4 payload.
    cache=BASE/'tmp/lc_cache'
    new=json.load(open(SM/'learned_c/gen/new_rows.json'))
    for p in sorted(cache.glob('*.npz')):
        n=p.stem
        if n in new: r=dict(new[n]); r['pool']='new'
        else:
            pool='fast' if n.startswith(('fast','fastmid')) else 'speed'
            raw=BASE/f'gen/raw-{pool}/bench'; side=raw/(n+'.json')
            if not side.exists(): excluded['unknown_cache']+=1; continue
            d=json.load(open(side)); r=dict(name=n,catalog=d['catalog'],scene=d['scene'],pool=pool,dir=str(raw))
        fo=fold(r['catalog'],r['scene']); r['fold']=fo
        if fo==4: excluded['sealed_metadata_only']+=1; continue
        r['role']='val' if fo==3 else 'search_sel' if n in selected else 'train'
        r['cache']=str(p)
        if r['role']=='train' and (r['scene'] in bad or (r['catalog'],r['scene']) in ho): excluded['forbidden_old_scene']+=1; continue
        if r['role'] in ('train','val'): rows.append(r)
    for n,r0 in json.load(open(SM/'learnvel/gen/lv_rows.json')).items():
        r=dict(r0); p=BASE/'tmp/lv_cache_train'/f'{n}.npz'; fo=fold(r['catalog'],r['scene'])
        assert fo in (0,1,2) and r['scene'] not in bad and (r['catalog'],r['scene']) not in ho
        if not p.exists(): excluded['lv_missing']+=1; continue
        r.update(role='train',pool='lv',cache=str(p)); rows.append(r)
    return rows,bad,ho,excluded

if __name__=='__main__':
    rows,bad,ho,excluded=manifests()
    tr=[r for r in rows if r['role']=='train']; va=[r for r in rows if r['role']=='val']
    out=dict(train=tr,val=va,forbidden_scenes=sorted(bad),holdout_scenes=sorted(ho),excluded=dict(excluded),ntrain=len(tr),nscenes=len({(r['catalog'],r['scene']) for r in tr}),pools=dict(collections.Counter(r['pool'] for r in tr)))
    (HERE/'tables/data_audit.json').write_text(json.dumps(out,indent=1))
    print({k:v for k,v in out.items() if k not in ['train','val','forbidden_scenes','holdout_scenes']},'val',len(va))
