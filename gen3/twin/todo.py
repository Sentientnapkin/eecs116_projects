"""python todo.py LIST -> srcs in LIST whose id has no successful row in any feat_*.jsonl"""
import sys,json,glob,os
ok=set()
for fn in glob.glob('/data/backups/rganapa/Sebastian/gen3/twin/feat_*.jsonl'):
    for l in open(fn):
        try: r=json.loads(l)
        except Exception: continue
        if 'error' not in r: ok.add(r['id'])
for s in open(sys.argv[1]).read().split():
    if os.path.basename(s)[:-4] not in ok: print(s)
