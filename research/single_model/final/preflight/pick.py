import sys,json,glob
sys.path.insert(0,'.')
from research.single_model.run_variant import tags,fold,slice_of
tg=tags()
a=json.load(open(glob.glob('research/results/single_model/final_f0/eval/*/scores.json')[0]))
rows=[]
for r in a['rows']:
    t=tg[r['episode']];f=fold(t)
    rows.append((r['episode'],t['start'],f,r['ate_full']))
vis=[x for x in rows if x[2]!=4]
import collections
print(collections.Counter((x[1],x[2]==4) for x in rows))
vis.sort(key=lambda x:-x[3])
print('worst visible');[print(x) for x in vis[:8]]
for st in('static','mid'):
    s=[x for x in vis if x[1]==st];print(st,len(s),'median-ish',s[len(s)//2],'best',s[-1])
json.dump(vis,open('research/single_model/final/preflight/visible_flights.json','w'))
