"""Export N nets (runs) into one header with per-net arrays and a pointer table: export_multi.py out.h run1 [run2 ...]  (all nf=2, res 64, width 1)"""
import sys
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'learned'))
import train as T
out, runs = sys.argv[1], sys.argv[2:]
lines = [f'#define LC_NN {len(runs)}']; tot = 0
for n, run in enumerate(runs):
    net = T.Net(64, 1.0, 2, 19); net.load_state_dict(torch.load(Path(run) / 'best.pt', map_location='cpu')); net.eval()
    arrs = {}; mods = list(net.cnn); chs = []
    for i in range(0, len(mods), 3):
        conv, bn = mods[i], mods[i + 1]; s = bn.weight / torch.sqrt(bn.running_var + bn.eps)
        arrs[f'W{i // 3}'] = (conv.weight * s[:, None, None, None]).permute(2, 3, 1, 0).detach().numpy(); arrs[f'B{i // 3}'] = (bn.bias - bn.running_mean * s).detach().numpy(); chs.append(conv.out_channels)
    assert chs == [16, 24, 32, 48]
    arrs['FW0'] = net.fv[0].weight.detach().t().numpy(); arrs['FB0'] = net.fv[0].bias.detach().numpy()
    W1 = net.head[0].weight.detach(); cnn = W1[:, :48 * 12].reshape(128, 48, 3, 4).permute(0, 2, 3, 1).reshape(128, 576)
    arrs['H1W'] = torch.cat([cnn, W1[:, 576:]], 1).t().numpy(); arrs['H1B'] = net.head[0].bias.detach().numpy()
    arrs['H2W'] = net.head[2].weight.detach().t().numpy(); arrs['H2B'] = net.head[2].bias.detach().numpy()
    for k, a in arrs.items():
        a = np.ascontiguousarray(a, dtype=np.float32).ravel(); tot += a.size
        lines.append(f'static const float LC_{k}_{n}[{a.size}] = {{')
        for i in range(0, a.size, 8): lines.append(','.join(f'{x:.9g}' for x in a[i:i + 8]) + ',')
        lines.append('};')
names = ['W0', 'B0', 'W1', 'B1', 'W2', 'B2', 'W3', 'B3', 'FW0', 'FB0', 'H1W', 'H1B', 'H2W', 'H2B']
lines.append('static const float *const lc_wt[LC_NN][14] = {')
for n in range(len(runs)): lines.append('  {' + ','.join(f'LC_{k}_{n}' for k in names) + '},')
lines.append('};')
Path(out).write_text('\n'.join(lines) + '\n'); print('nets', len(runs), 'bytes', tot * 4)
