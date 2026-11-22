"""lv_eval.py RUN OUT.npz EP_GLOB... : net predictions (head K, phase 0, every anchor) on eval-cache flights.
RUN = learned_c/runs/<name> or learnvel/runs/<name> (best.pt + result.json args). Saves per-anchor arrays: ep idx, anchor, mu, lv, truth, texture."""
import sys, json, glob
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'learned_c')); sys.path.insert(0, str(HERE.parent / 'learned'))
import train as T

class EvalData:
    def __init__(self, files, dev, phase=0):
        fr, Rc, Vi, fm, gm, vb, K, fx, fid, pos, ln = ([] for _ in range(11)); self.names = []
        for i, f in enumerate(files):
            d = np.load(f); self.Tbc = d['Tbc']; p = phase; A = len(d[f'frames{p}'])
            fr.append(d[f'frames{p}']); Rc.append(d[f'Rcum{p}']); Vi.append(d[f'Vint{p}']); fm.append(d[f'fmean{p}']); gm.append(d[f'gmean{p}'])
            vb.append(d[f'vb{p}']); K.append(np.tile(d['K'], (A, 1))); fx.append(np.full(A, float(d['fx320'])))
            fid.append(np.full(A, i)); pos.append(np.arange(A)); ln.append(np.full(A, A)); self.names.append(Path(f).stem)
        c = lambda x: torch.from_numpy(np.concatenate(x)).to(dev).float()
        self.frames = torch.from_numpy(np.concatenate(fr)).to(dev)
        self.R, self.V, self.f, self.g, self.vb, self.K, self.fx = c(Rc), c(Vi), c(fm), c(gm), c(vb), c(K), c(fx)
        self.fid = torch.from_numpy(np.concatenate(fid)).to(dev); self.pos = torch.from_numpy(np.concatenate(pos)).to(dev); self.len = torch.from_numpy(np.concatenate(ln)).to(dev)
        self.Rbc = torch.tensor(self.Tbc[:3, :3], dtype=torch.float32, device=dev)
    valid_starts = T.Data.valid_starts

def texture(frames):
    """per-frame texture: fraction of pixels with |grad| > 8 (gray128) and count of 8x8 cells with such pixels"""
    x = frames.float(); gx = (x[:, :, 2:] - x[:, :, :-2]).abs()[:, 1:-1]; gy = (x[:, 2:] - x[:, :-2]).abs()[:, :, 1:-1]
    g = torch.maximum(gx, gy) > 8
    return g.float().mean((1, 2))

def load_net(run, dev):
    a = json.load(open(Path(run) / 'result.json'))['args']
    net = T.Net(a['res'], a['width'], a.get('nf', 2), 19).to(dev); net.load_state_dict(torch.load(Path(run) / 'best.pt', map_location=dev)); net.eval()
    return net, a

if __name__ == '__main__':
    run, out = sys.argv[1], sys.argv[2]; files = sorted(sum([glob.glob(g) for g in sys.argv[3:]], []))
    dev = 'cuda'; D = EvalData(files, dev); net, a = load_net(run, dev)
    st = D.valid_starts(2, 1)
    mu, lv, y = T.predict(net, D, st, 2, 1, a['res'])
    tex = texture(D.frames)[st + 1]
    np.savez(out, names=np.array(D.names), fid=D.fid[st].cpu().numpy(), anchor=D.pos[st].cpu().numpy(), mu=mu[:, 1].cpu().numpy(), lv=lv[:, 1].cpu().numpy(),
             y=y[:, 1].cpu().numpy(), tex=tex.cpu().numpy())
    e = (mu[:, 1] - y[:, 1]).norm(dim=-1).cpu().numpy(); sp = y[:, 1].norm(dim=-1).cpu().numpy()
    print('n', len(e), 'err %.3f' % e.mean(), 'by speed', [('%.1f' % lo, '%.3f' % e[(sp >= lo) & (sp < hi)].mean(), int(((sp >= lo) & (sp < hi)).sum())) for lo, hi in [(0, .3), (.3, 1), (1, 2), (2, 3), (3, 9)] if ((sp >= lo) & (sp < hi)).any()])
