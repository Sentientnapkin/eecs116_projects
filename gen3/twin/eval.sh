#!/bin/bash
# twin/eval.sh NAME WASM [WORKERS=14] : evaluate a build on the server-twin sets (gen3/pools/twin24, twin120) and print
# the twin means, per-episode table and the calibrated server prediction (calib.json). Results: gen3/evals/tw_NAME__twin*.json
T=/data/backups/rganapa/Sebastian/gen3/twin; G=/data/backups/rganapa/Sebastian/gen3; PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
N=$1; W=$(readlink -f $2); J=${3:-14}
for pool in twin24 twin120; do
  while [ $(cut -d. -f1 /proc/loadavg) -ge 170 ]; do echo "load high, waiting"; sleep 120; done
  $PY $T/seed_cache.py tw_$N $W $G/pools/$pool
  (cd $G && $PY -B evalpool.py tw_$N $W pools/$pool $J) | head -1
done
$PY - "$N" <<'PY'
import json,sys,numpy as np
T='/data/backups/rganapa/Sebastian/gen3/twin';G='/data/backups/rganapa/Sebastian/gen3';n=sys.argv[1]
t24=[l.split('\t')[1] for l in open(f'{T}/twin24.txt')];t120={}
for l in open(f'{T}/twin120.txt'): e,i=l.split('\t')[:2];t120.setdefault(int(e)-1,[]).append(i)
a={r['id']:(r['ate'] if r['ate'] is not None else np.nan) for f in ('twin24','twin120') for r in json.load(open(f'{G}/evals/tw_{n}__{f}.json'))}
pk=max([r['peak'] or 0 for f in ('twin24','twin120') for r in json.load(open(f'{G}/evals/tw_{n}__{f}.json'))])
e24=[a.get(i,np.nan) for i in t24];e120=[np.nanmean([a.get(i,np.nan) for i in t120[e]]) for e in range(24)]
c=json.load(open(f'{T}/calib.json'));k=c.get('calib',{})
print(f'{n}: twin24 {np.nanmean(e24):.3f}  twin120 {np.nanmean(e120):.3f}  (rooms {np.nanmean(e120[:12]):.3f} wh {np.nanmean(e120[12:18]):.3f} forest {np.nanmean(e120[18:]):.3f})  fails {int(np.isnan(list(a.values())).sum())}  peak fuel {pk/1e6:.2f} M')
if k: print(f'predicted server mean ATE: {np.nanmean(e120)*k["ratio120"]:.3f} m (twin120 x {k["ratio120"]:.3f}; LOO factor x{k["loo120"]:.2f})')
print('per-episode twin120 (mean of 5):',' '.join(f'{x:.2f}' for x in e120))
PY
