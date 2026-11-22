"""mkpool.py : symlink st1 flights into tmp/st_pools/st1dev and st1conf (scene md5 % 3 == 0 -> conf)"""
import json, glob, hashlib, os
R = '/data/backups/rganapa/Sebastian/gen/raw-servertail/bench'; O = '/data/backups/rganapa/Sebastian/tmp/st_pools'
import sys; PFX = sys.argv[1] if len(sys.argv) > 1 else 'st1'; n = {PFX + 'dev': 0, PFX + 'conf': 0}
for f in sorted(glob.glob(R + '/' + PFX + '*.json')):
    d = json.load(open(f)); z = f[:-5] + '.zip'
    if not os.path.exists(z): continue
    p = PFX + 'conf' if int(hashlib.md5(d['scene'].encode()).hexdigest(), 16) % 3 == 0 else PFX + 'dev'
    os.makedirs(f'{O}/{p}', exist_ok=True)
    for s in (f, z):
        t = f'{O}/{p}/' + os.path.basename(s)
        if not os.path.exists(t): os.symlink(s, t)
    n[p] += 1
print(n)
