"""usage: flights.py arm [thr]  list search/val flights where f0 or arm > thr with both values."""
import sys, json; sys.path.insert(0, '.')
from research.single_model.run_variant import OUT, slice_of
def load(n): return {x['e']: x for x in json.loads((OUT / f'{n}/report.json').read_text())['rows_visible']}
ref = load('final_f0'); new = load(sys.argv[1]); thr = float(sys.argv[2]) if len(sys.argv) > 2 else 3
for e in sorted(new, key=lambda e: -max(new[e]['new'], ref[e]['new'])):
    if max(new[e]['new'], ref[e]['new']) > thr or abs(new[e]['new'] - ref[e]['new']) > 1.0:
        print(f"{e:42s} {new[e]['start']:6s} f{new[e]['fold']} f0 {ref[e]['new']:6.2f} arm {new[e]['new']:6.2f}")
