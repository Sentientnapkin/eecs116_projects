"""Uploader for SentientNapkin/viobench-stage3: raw episodes (verified by LFS sha256, then local zip deleted), gray shards, manifest."""
import os,sys,json,time,glob,io,csv,tarfile,collections as C
from pathlib import Path
from huggingface_hub import HfApi,CommitOperationAdd as Add
RID='SentientNapkin/viobench-stage3';OUT=Path('/data/backups/rganapa/Sebastian/gen3/out');EP=OUT/'ep';UP=OUT/'up';SH=OUT/'shards'
KEEP=OUT/'keep'
for d in(UP,SH,KEEP): d.mkdir(parents=True,exist_ok=True)
a=HfApi();a.create_repo(RID,repo_type='dataset',private=False,exist_ok=True)
def log(*x): print(time.strftime('%F %T'),*x,flush=True)
def commit(ops,msg):
    for k in range(300):
        try: return a.create_commit(RID,ops,commit_message=msg,repo_type='dataset')
        except Exception as e:
            s=str(e);log('WAIT',type(e).__name__,s[:900].replace('\n',' '));time.sleep(1200 if '429' in s or 'rate limit' in s.lower() else 90)
    raise SystemExit('too many retries')
def verify(paths):
    for k in range(20):
        try: return {p.path:(p.lfs.sha256 if p.lfs else None,p.size) for p in a.get_paths_info(RID,paths,repo_type='dataset',expand=True)}
        except Exception as e: log('VERIFY WAIT',repr(e)[:150]);time.sleep(60)
    return {}
# HF limits 10k files per directory: flights not already in raw/<split>/<class>/ go to raw/<split>/<class>_b/ (2026-11-27)
_OLD={f for f in a.list_repo_files(RID,repo_type='dataset') if f.startswith('raw/')}
def rp(r):
    o=f"raw/{r['split']}/{r['setting_class']}/{r['id']}"
    return o if (o+'.zip') in _OLD else f"raw/{r['split']}/{r['setting_class']}_b/{r['id']}"
def push_raw():
    ready=[]
    for j in sorted(EP.glob('*.json')):
        i=j.name[:-5]
        if (EP/(i+'.zip')).exists() and (EP/(i+'.mini.tar')).exists(): ready.append(json.loads(j.read_text()))
    for b in range(0,len(ready),30):
        L=ready[b:b+30];ops=[]
        for r in L: ops+=[Add(path_in_repo=rp(r)+'.zip',path_or_fileobj=str(EP/(r['id']+'.zip'))),Add(path_in_repo=rp(r)+'.json',path_or_fileobj=str(EP/(r['id']+'.json')))]
        commit(ops,f"add {len(L)} flights");h=verify([rp(r)+'.zip' for r in L]);ok=0
        for r in L:
            if h.get(rp(r)+'.zip',(None,))[0]==r['sha256']:
                (UP/(r['id']+'.json')).write_text(json.dumps(r));(UP/(r['id']+'.done')).touch();(os.rename(EP/(r['id']+'.zip'),KEEP/(r['id']+'.zip')) if r['split'] in('val','test') else os.remove(EP/(r['id']+'.zip')));os.remove(EP/(r['id']+'.json'));ok+=1
            else: log('VERIFY MISMATCH',r['id'],h.get(rp(r)+'.zip'))
        log('raw',ok,'/',len(L),'verified+freed; total up',len(list(UP.glob('*.done'))))
def push_shards(final=False):
    st=json.loads((UP/'shards.json').read_text()) if (UP/'shards.json').exists() else {'n':{},'map':{}}
    by=C.defaultdict(list)
    for m in sorted(EP.glob('*.mini.tar')):
        i=m.name[:-9]
        if (UP/(i+'.done')).exists(): by[json.loads((UP/(i+'.json')).read_text())['split']].append(m)
    for s,L in by.items():
        while len(L)>=25 or (final and L):
            g,L=L[:25],L[25:];k=st['n'].get(s,0);name=f'{s}-{k:04d}.tar';p=SH/name
            with tarfile.open(str(p)+'.part','w') as t:
                for m in g:
                    with tarfile.open(m) as src:
                        for mem in src: t.addfile(mem,src.extractfile(mem))
            os.rename(str(p)+'.part',p);commit([Add(path_in_repo='shards/'+name,path_or_fileobj=str(p))],'shard '+name)
            h=verify(['shards/'+name])
            if h.get('shards/'+name,(0,0))[1]==p.stat().st_size:
                for m in g: st['map'][m.name[:-9]]='shards/'+name;os.remove(m)
                os.remove(p);st['n'][s]=k+1;(UP/'shards.json').write_text(json.dumps(st));log('shard',name,'ok')
            else: log('SHARD VERIFY FAIL',name);break
def manifest(final=False):
    st=json.loads((UP/'shards.json').read_text()) if (UP/'shards.json').exists() else {'map':{}}
    R=[json.loads(p.read_text()) for p in sorted(UP.glob('*.json')) if p.name!='shards.json']
    if not R: return
    cols=['id','roster_version','split','setting_class','catalog','scene','scene_variant','motion_style','regime','start','crop_start_s','seconds','frames','fov_deg','exposure_s','exposure_sampled_s','blur_space','brightness_scale','linear_gain','path_m','duration_s','mean_speed','gyro_rms','yaw_rms','tilt_rms','jerk_rms','rms_dist_from_start','rms_spread','start_speed','start_fwd_speed','luma_mean','dark_fraction','quality','seed','bytes','sha256','path','shard']
    b=io.StringIO();w=csv.DictWriter(b,cols,extrasaction='ignore');w.writeheader()
    for r in R: w.writerow({**r,'quality':'outside_scene' if (r['luma_mean']<25 or r['dark_fraction']>.3) else 'ok','roster_version':r.get('roster_version',1),'path':rp(r)+'.zip','shard':st['map'].get(r['id'],'')})
    c=C.Counter((r['split'],r['setting_class']) for r in R if r.get('roster_version',1)==3);c1=C.Counter(r['split'] for r in R if r.get('roster_version',1)!=3)
    tab='| split | room | warehouse | forest |\n|---|---|---|---|\n'+''.join(f"| {s} | {c[(s,'room')]} | {c[(s,'warehouse')]} | {c[(s,'forest')]} |\n" for s in('train','val','test'))+f"\nPlus earlier v1 flights (normal heading only, kept and labeled `roster_version`=1): {dict(c1)}\n"
    rd=open('/data/backups/rganapa/Sebastian/gen3/README_s3.md').read().replace('@@TABLE@@',tab).replace('@@STATE@@','Complete.' if final else f'Generation and upload in progress ({len(R)} flights so far); this table updates as flights land.')
    commit([Add(path_in_repo='manifest.csv',path_or_fileobj=b.getvalue().encode()),Add(path_in_repo='README.md',path_or_fileobj=rd.encode()),Add(path_in_repo='load_shards.py',path_or_fileobj='/data/backups/rganapa/Sebastian/tmp/vf/load_shards.py'),
            Add(path_in_repo='generator/g3.py',path_or_fileobj='/data/backups/rganapa/Sebastian/gen3/g3.py'),Add(path_in_repo='generator/roster.json',path_or_fileobj='/data/backups/rganapa/Sebastian/gen3/cfg/roster.json'),Add(path_in_repo='generator/mkroster.py',path_or_fileobj='/data/backups/rganapa/Sebastian/gen3/mkroster.py'),
            Add(path_in_repo='scenes/params.json',path_or_fileobj='/data/backups/rganapa/Sebastian/gen3/scenes/params.json')],'manifest');log('manifest',len(R),dict(c))
last=0
while True:
    push_raw();push_shards()
    if time.time()-last>1800: manifest();last=time.time()
    if (OUT/'GEN_DONE').exists() and not list(EP.glob('*.zip')):
        push_shards(final=True);manifest(final=True);log('UPLOAD FINISHED');break
    time.sleep(120)
