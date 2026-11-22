import json,sys,os,numpy as np
for n in sys.argv[1:]:
    p=os.path.expanduser(f"~/ws_m/ev_{n}_hf.json")
    if not os.path.exists(p): print(n,"missing"); continue
    r=json.load(open(p)); a=np.array([x["ate"] for x in r]); f=np.array([x["fuel"] for x in r])
    print(f"{n:6s} n={len(r)} ate {np.nanmean(a):.3f} >3m {int(np.sum(a>3))} | fuel max {np.nanmax(f)/1e6:.2f}M p50 {np.nanmedian(f)/1e6:.2f}M p90 {np.nanpercentile(f,90)/1e6:.2f}M")
