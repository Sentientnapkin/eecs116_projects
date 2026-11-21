import json,sys,hashlib,numpy as np
tags=json.load(open('../fresh/tags.json'))
fold={e:int(hashlib.sha256((t['catalog']+':'+t['scene']).encode()).hexdigest()[:8],16)%5 for e,t in tags.items()}
for n in sys.argv[1:]:
    R=[r for r in json.load(open(f'dg_{n}.json')) if fold[r['episode']]<=3]
    a=np.array([r['ate'] for r in R]); print(n,'n',len(R),'mean %.3f'%a.mean(),'minus-trans %.3f'%np.mean([r['ate_mt'] for r in R]))
    for k in ['acc0','acc3','acc10','acc20','live10','live20','pv10','pv15','pv25','first5']:
        f=np.array([r['f_'+k] for r in R]); c=np.array([r['cf_'+k] for r in R])
        print(f'  {k:7s} frac frames {f.mean():.3f}  oracle-zero-vel-err mean {c.mean():.3f} (gain {a.mean()-c.mean():+.3f})  tails>1m {(a>1).sum()}->{(c>1).sum()} >3 {(a>3).sum()}->{(c>3).sum()}')
    # worst flights
    R.sort(key=lambda r:-r['ate'])
    tot=a.sum(); print('  top20 share %.2f'%(sum(r['ate'] for r in R[:20])/tot))
    for r in R[:15]: print('   %-45s %5.2f mt %4.2f acc3 %.2f/%4.2f pv15 %.2f/%4.2f live20 %.2f first5 %4.2f fires %d'%(r['episode'],r['ate'],r['ate_mt'],r['f_acc3'],r['cf_acc3'],r['f_pv15'],r['cf_pv15'],r['f_live20'],r['cf_first5'],r['nfire']))
