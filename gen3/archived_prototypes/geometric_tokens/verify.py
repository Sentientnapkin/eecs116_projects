import time,json,torch,numpy as np
from pathlib import Path
from train import DeepSet,SetAttention
O=Path(__file__).resolve().parent; torch.set_num_threads(2); dev='cuda'; dat=np.load(O/'val.npz'); x=torch.tensor(dat['x'][:256].astype('float32'),device=dev); v=torch.tensor(dat['v'][:256].astype('float32'),device=dev); perm=torch.randperm(48,device=dev)
rows=[]
for name,cls in [('deepsets',DeepSet),('attention',SetAttention)]:
 ck=torch.load(O/f'{name}_seed17.pt',map_location=dev,weights_only=False); n=cls().to(dev); n.load_state_dict(ck['state_dict']); norm=ck['normalization']; xm=norm['x_mean'].to(dev); xs=norm['x_std'].to(dev); vm=norm['imu_mean'].to(dev); vs=norm['imu_std'].to(dev); a=(x-xm)/xs; b=(v-vm)/vs; n.eval()
 with torch.no_grad():
  p1,l1=n(a,b); p2,l2=n(a[:,perm],b)
  for _ in range(10): n(a,b)
  torch.cuda.synchronize(); t=time.perf_counter()
  for _ in range(100): n(a,b)
  torch.cuda.synchronize(); ms=(time.perf_counter()-t)*10
 rows.append({'model':name,'permutation_max_abs_mu_delta':float((p1-p2).abs().max()),'permutation_max_abs_lv_delta':float((l1-l2).abs().max()),'batch256_forward_ms':ms})
print(json.dumps(rows,indent=2)); (O/'verify.json').write_text(json.dumps(rows,indent=2))
