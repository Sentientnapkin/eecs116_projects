import json, sys, numpy as np
R=[r for r in json.load(open(sys.argv[1])) if 'error' not in r]
R.sort(key=lambda r:-r['ate'])
ks=['ate','vrmse','pv_sd','yaw_rms','yaw_sd','nfire','np_all','nv_all','nvm_all','rv_all','nv_starv','rv_starv','f_starv','nv_good','rv_good','nv_t1_5','ny_all']
print(' '.join('%8s'%k for k in ks))
for r in R[:int(sys.argv[2]) if len(sys.argv)>2 else 12]:
    print(' '.join('%8.3f'%r.get(k,np.nan) for k in ks), r['ep'][:40])
for grp,sel in (('ate>1',[r for r in R if r['ate']>1]),('0.5-1',[r for r in R if 0.5<=r['ate']<=1]),('ate<0.5',[r for r in R if r['ate']<0.5])):
    print(grp,len(sel),' '.join('%s %.2f'%(k,np.nanmedian([r.get(k,np.nan) for r in sel])) for k in ks))
