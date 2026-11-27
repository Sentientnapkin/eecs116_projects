import os,sys,time
from huggingface_hub import HfApi,hf_hub_download
a=HfApi();RID='SentientNapkin/viobench-stage3';K='/data/backups/rganapa/Sebastian/gen3/out/keep'
fs=[f for f in a.list_repo_files(RID,repo_type='dataset') if f.startswith(('raw/val/','raw/test/')) and f.endswith('.zip')]
n=0
for f in fs:
    t=os.path.join(K,os.path.basename(f))
    if os.path.exists(t): continue
    p=hf_hub_download(RID,f,repo_type='dataset',local_dir=K+'/.dl');os.replace(p,t);n+=1
print('fetched',n,'of',len(fs),flush=True)
