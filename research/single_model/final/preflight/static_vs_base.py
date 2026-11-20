import sys,json,glob
sys.path.insert(0,'.')
from research.single_model.run_variant import tags,fold,slice_of,BASELINE
import numpy as np
tg=tags()
a={r['episode']:r['ate_full'] for r in json.load(open(glob.glob('research/results/single_model/final_f0/eval/*/scores.json')[0]))['rows']}
b={r['episode']:r['ate_full'] for r in json.load(open(BASELINE))['rows']}
for st in('static','mid'):
    e=[x for x in a if tg[x]['start']==st and slice_of(fold(tg[x]))!='sealed']
    d=np.array([a[x]-b[x] for x in e]);print(st,len(e),'f0 mean',np.mean([a[x] for x in e]),'base mean',np.mean([b[x] for x in e]),'identical flights',int((d==0).sum()),'max|d|',abs(d).max())
