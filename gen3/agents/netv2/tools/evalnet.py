"""evalnet.py RUN... : direct head-K velocity error on the v3 val cache (agents/net/cache/val). RUN = path to best.pt dir or learnvel run name."""
import sys, json, torch
from pathlib import Path
import lv3, train as T
va = lv3.D(sorted((lv3.A / 'cache/val').glob('*.npz')), 'cuda', (0,)); vas = va.starts(); vm = lv3.val_meta()
print('val flights', len(va.names), 'anchors', len(vas))
for run in sys.argv[1:]:
    p = Path(run) if '/' in run else lv3.SM / 'learnvel/runs' / run
    net = T.Net(64, 1.0, 2, 19).cuda(); net.load_state_dict(torch.load(p / 'best.pt', map_location='cuda'))
    print(run, json.dumps(lv3.report(*lv3.predict(net, va, vas), va, vas, vm)), flush=True)
