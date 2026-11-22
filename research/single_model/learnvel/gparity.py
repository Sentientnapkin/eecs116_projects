import sys, re, glob, json, numpy as np, torch
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench'); sys.path.insert(0, '../learned_c'); sys.path.insert(0, '../learned')
import prep2, train as T
from viobench.tools.datasets.storage import read_episode
run, ep, zp, err = sys.argv[1:5]
a = json.load(open(f'runs/{run}/result.json'))['args']; net = T.Net(64, a['width'], 1, 7); net.load_state_dict(torch.load(f'runs/{run}/best.pt', map_location='cpu')); net.eval()
E = read_episode(zp, frames='lazy'); t = E.frame_times; imu = E.imu; cam = E.config['camera']; K0 = cam['fx'] * 128 / E.resolution[0]
G = np.load(f'/data/backups/rganapa/Sebastian/tmp/lv_grav/{ep}.npz')['gb0']
rows = [l for l in open(err) if l.startswith('G apply')][:12]
for l in rows:
    m = re.match(r'G apply frame (\d+) cap (\d+) mu (\S+) (\S+) (\S+)', l); cap = int(m.group(2)); muC = np.array([float(m.group(i)) for i in (3, 4, 5)])
    fr = cap  # gr_frame counts steps after init -> video frame index
    g = prep2.gray128(E.frames[fr]).astype(np.float32)
    X = torch.tensor(g)[None, None]; X = (X - X.mean()) / (X.std() + 5.0)
    ca = torch.linspace(-1, 1, 128).view(1, 1, 1, 128).expand(1, 1, 96, 128); cb = torch.linspace(-1, 1, 96).view(1, 1, 96, 1).expand(1, 1, 96, 128)
    img = torch.nn.functional.avg_pool2d(torch.cat([X, ca, cb], 1), 2)
    i1 = np.searchsorted(imu[:, 0], t[fr] + 1e-6, side='right'); i0 = np.searchsorted(imu[:, 0], t[fr] - 0.05 + 1e-6, side='right')
    vec = torch.tensor(np.concatenate([imu[i0:i1, 1:4].mean(0) / 9.81, imu[i0:i1, 4:7].mean(0), [K0 / 100]]), dtype=torch.float32)[None]
    with torch.no_grad(): mu, lv = net(img, vec)
    mu = mu[0, 0].numpy(); mu /= np.linalg.norm(mu)
    print('cap %4d C-vs-torch %.3f deg | C-vs-truth %.2f deg (anchor %d)' % (cap, np.degrees(np.arccos(np.clip(mu @ muC, -1, 1))), np.degrees(np.arccos(np.clip(muC @ G[cap // 5], -1, 1))), cap // 5))
