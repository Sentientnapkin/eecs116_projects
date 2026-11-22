import argparse,json,sys,importlib.util
from pathlib import Path
import numpy as np,torch
H=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('stlong_train',H/'train.py');S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--out',required=True);a=p.parse_args();r=Path(a.run)
if (r/'config.json').exists():c=json.load(open(r/'config.json'))
else:c=json.load(open(r/'result.json'))['args'];c.update(deep=False,hidden=128)
c=argparse.Namespace(**c);net=S.model(c).cuda();net.load_state_dict(torch.load(r/'best.pt',map_location='cuda',weights_only=True));net.eval();out={}
for pool,files in [('st2dev',sorted((S.BASE/'tmp/lv_cache').glob('st2*.npz'))),('st3',sorted((S.BASE/'tmp/sl_cache_st3').glob('*.npz')))]:
 D=S.EvalData(files,'cuda');st=D.valid_starts(c.nf,c.gap);mu,lv,y=S.T.predict(net,D,st,c.nf,c.gap,c.res,bs=256);out[pool]=S.stats(mu,lv,y)
 np.savez(H/'tables'/f'{a.out}_{pool}_pred.npz',mu=mu[:,1].cpu(),lv=lv[:,1].cpu(),y=y[:,1].cpu())
 del D
(H/'tables'/f'{a.out}_direct.json').write_text(json.dumps(out,indent=1));print(json.dumps(out),flush=True)
