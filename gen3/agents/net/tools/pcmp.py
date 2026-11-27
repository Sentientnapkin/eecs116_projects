"""pcmp.py BEST.json NEW.json -> prints paired mean difference (NEW-BEST) on common flights, its bootstrap 95% CI, n."""
import sys,json,random,statistics as s
L=lambda p:{r['id']:r['ate'] for r in json.load(open(p)) if r.get('ate') is not None}
a,b=L(sys.argv[1]),L(sys.argv[2]);ids=sorted(set(a)&set(b));d=[b[i]-a[i] for i in ids]
r=random.Random(0);bs=sorted(s.mean(r.choices(d,k=len(d))) for _ in range(2000))
print(f"{s.mean(d):+.4f} {bs[50]:+.4f} {bs[1949]:+.4f} {len(ids)}")
