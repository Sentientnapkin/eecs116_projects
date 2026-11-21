"""Hard-example mining report -> scene weights for the next generation batch.
  mine.py run_name [--pow 1.5]   reads runs/<run>/result.json (train_cells, train_scene_err); writes gen/weights_<run>.json {catalog|scene: weight} and prints the hardest cells."""
import json, sys
import numpy as np
run = sys.argv[1]; pw = float(sys.argv[sys.argv.index('--pow') + 1]) if '--pow' in sys.argv else 1.5
r = json.load(open(f'runs/{run}/result.json'))
cells = r['train_cells']; tot = sum(c['n'] for c in cells.values()); base = r['train_err_all']
print('train err all %.3f' % base); print('hardest cells (speed bin s0..3 = <0.3,0.3-1,1-1.5,>1.5 m/s; angle a-1 = slow, a0..a4 = 0-30,30-60,60-90,90-135,135-180):')
for k, c in sorted(cells.items(), key=lambda kv: -kv[1]['err'] * kv[1]['n'] ** 0.0)[:8]: print(f"  {k:7s} n {c['n']:6d} ({100*c['n']/tot:4.1f}%) err {c['err']:.3f}")
se = r['train_scene_err']; v = np.array(list(se.values())); m = v.mean()
w = {k: float((e / m) ** pw) for k, e in se.items()}
json.dump(w, open(f'gen/weights_{run}.json', 'w'), indent=1); print('scenes', len(w), 'weight range %.2f-%.2f' % (min(w.values()), max(w.values())))
