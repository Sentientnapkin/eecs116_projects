"""Parity of the C net against the PyTorch model.
 (1) net-only: C forward on the C-built input tensors vs torch Net on the same tensors (max abs diff of mean/logvar outputs).
 (2) pipeline: C preprocessing from raw 320x240 frames + IMU rows (as the harness delivers them) vs build_batch on the prep2 cache (anchor 0, phase 0): tensors and outputs.
 usage: parity.py <run dir> <weights dir> [n windows]   windows = anchor 0 of validation flights (fold 3) + shifted anchors where the flight is mid-air"""
import sys, subprocess, struct, json
from pathlib import Path
import numpy as np, torch, cv2
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'learned')); sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
import train as T, split2, train2
from viobench.tools.datasets.storage import read_episode

def dump(rows, path, anchors):
    with open(path, 'wb') as f:
        f.write(struct.pack('i', len(rows) * len(anchors)))
        for r in rows:
            ep = read_episode(Path(r['dir']) / f"{r['name']}.zip", frames='lazy')
            cam = ep.config['camera']; Rbc = np.asarray(ep.T_body_camera)[:3, :3]
            for a in anchors:
                f.write(np.array([cam['fx'] * 0.5, 159.5, 119.5, *Rbc.ravel()], np.float64).tobytes())
                for k in range(6):
                    j = a + 5 * k if k else a
                    j = a if k == 0 else a + k   # frames a, a+1 ... a+5 : filter steps 0..5 (consecutive frames)
                    fr = cv2.resize(ep.frames[j], (320, 240), interpolation=cv2.INTER_AREA)
                    w = np.asarray(ep.imu_window(j), np.float64)
                    f.write(np.ascontiguousarray(fr).tobytes()); f.write(struct.pack('i', len(w))); f.write(w.tobytes())

def main():
    run, wdir = sys.argv[1], sys.argv[2]; nw = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    allr = [r for r in split2.load_rows() if r['role'] == 'val' and r['pool'] == 'fast']   # fold 3 only
    rows = [r for r in allr if r['start'] == 'mid'][:nw // 2] + [r for r in allr if r['start'] == 'static'][:nw // 2]
    exe = HERE / 'lc_test.bin'
    subprocess.check_call(['gcc', '-O2', '-I', wdir, '-I', str(HERE), '-o', str(exe), str(HERE / 'lc_test.c'), '-lm'])
    anchors = [0, 40, 100]
    dump(rows, HERE / 'lc_dump.bin', anchors)
    subprocess.check_call([str(exe), str(HERE / 'lc_dump.bin'), str(HERE / 'lc_out.bin')])
    raw = np.fromfile(HERE / 'lc_out.bin', np.uint8); per = 4 * (48 * 64 * 5 + 19 + 12) + 2 * 96 * 128
    n = len(rows) * len(anchors); assert len(raw) == n * per, (len(raw), n * per)
    img = np.zeros((n, 48, 64, 5), np.float32); vec = np.zeros((n, 19), np.float32); out = np.zeros((n, 12), np.float32); g = []
    ANCH = [(i // len(anchors), anchors[i % len(anchors)]) for i in range(n)]
    for i in range(n):
        b = raw[i * per:(i + 1) * per]; fl = np.frombuffer(b[:4 * (15360 + 19 + 12)].tobytes(), np.float32)
        img[i] = fl[:15360].reshape(48, 64, 5); vec[i] = fl[15360:15379]; out[i] = fl[15379:]
        g.append(np.frombuffer(b[4 * (15360 + 31):].tobytes(), np.uint8).reshape(2, 96, 128))
    net = T.Net(64, 1.0, 2, 19); net.load_state_dict(torch.load(Path(run) / 'best.pt', map_location='cpu')); net.eval()
    with torch.no_grad():
        mu, lv = net(torch.from_numpy(img).permute(0, 3, 1, 2).contiguous(), torch.from_numpy(vec))
    ref = torch.cat([mu[:, 0], lv[:, 0], mu[:, 1], lv[:, 1]], 1).numpy()
    out[:, [3,4,5,9,10,11]] = np.clip(out[:, [3,4,5,9,10,11]], -7, 4)
    d1 = np.abs(ref - out)
    print('(1) net-only: windows', n, '(rows', len(rows), 'anchors', anchors, ')', 'max abs diff mean outputs %.2e, logvar %.2e' % (np.abs(d1[:, [0, 1, 2, 6, 7, 8]]).max(), np.abs(d1[:, [3, 4, 5, 9, 10, 11]]).max()))
    # (2) pipeline vs prep2 cache + build_batch
    D = train2.Data2(['val'], 'cpu', ('fast',), (0,)); names = [r['name'] for r in D.rows]
    idx = [int(torch.nonzero((D.fid == names.index(r['name'])) & (D.pos == a // 5))[0]) for r in rows for a in anchors]
    gi = torch.tensor(idx)
    im2, vec2, tgt, _ = T.build_batch(D, gi, 2, 1, 64, False)
    with torch.no_grad():
        mu2, lv2 = net(im2, vec2)
    ref2 = torch.cat([mu2[:, 0], lv2[:, 0], mu2[:, 1], lv2[:, 1]], 1).numpy()
    cache_g0 = D.frames[gi].numpy(); gd = np.abs(cache_g0.astype(int) - np.stack([x[0] for x in g]).astype(int))
    print('(2) pipeline: gray128 frame0 C vs cache: max diff %d levels, mean %.4f, frac !=0 %.4f' % (gd.max(), gd.mean(), (gd > 0).mean()))
    print('    input tensor max abs diff', np.abs(im2.permute(0, 2, 3, 1).numpy() - img).max(), ' vec diff', np.abs(vec2.numpy() - vec).max(axis=0).round(4).tolist())
    d2 = np.abs(ref2 - out)
    print('    outputs: max abs diff mean %.2e (headK %.2e) logvar %.2e' % (d2[:, [0, 1, 2, 6, 7, 8]].max(), d2[:, [6, 7, 8]].max(), d2[:, [3, 4, 5, 9, 10, 11]].max()))
    vtrue = tgt[:, 1].numpy(); print('    headK error vs truth: C %.3f m/s, torch-on-cache %.3f m/s' % (np.linalg.norm(out[:, 6:9] - vtrue, axis=1).mean(), np.linalg.norm(ref2[:, 6:9] - vtrue, axis=1).mean()))

main()
