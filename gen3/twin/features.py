"""Probe-equivalent statistics of one flight, in python (definitions ported from eecs116_vio/probe/probe.c + decode.py).

    python -I features.py OUT.jsonl SRC [SRC ...]     SRC = local zip path, or hf:raw/<split>/<class>/<id>.zip (range reads)

Image stats use NS frames evenly sampled in 0..1129 (probe uses all), resized to 320x240 with viobench's own adapt()
(INTER_AREA). IMU/dynamics/start stats use the exact per-frame IMU windows; path stats use ground_truth_relative().
"""
import json, os, sys, time, zipfile
import numpy as np

sys.path.insert(0, '/data/backups/rganapa/Sebastian/venv-teacher/lib/python3.12/site-packages')
from viobench.tools.datasets import storage as ST
from viobench.tools.geometry import invert

NS = int(os.environ.get('TW_NS', 40))
REPO = 'SentientNapkin/viobench-stage3'
_fs = None


class _RemoteArchive(ST._Archive):
    def __init__(self, url):
        global _fs
        if _fs is None:
            from huggingface_hub import HfFileSystem
            _fs = HfFileSystem()
        self.fh = _fs.open(f'datasets/{REPO}/{url}', 'rb', block_size=2 ** 20, cache_type='none')
        self.archive = zipfile.ZipFile(self.fh)
        self.members = set(self.archive.namelist())
        m = [n for n in self.members if n.endswith('/episode.json') and n.count('/') == 1] or ['episode.json']
        self.prefix = m[0][:-len('episode.json')]


_orig_open = ST._open


def _open(path):
    s = str(path)
    if s.startswith('hf:'):
        return _RemoteArchive(s[3:])
    return _orig_open(path)


ST._open = _open


def image_stats(f):
    f = f.astype(np.int64)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    d1x = g[:, 1:-1] - g[:, :-2]; d2x = g[:, 2:] - g[:, :-2]
    e1x, e2x = (d1x ** 2).sum(), (d2x ** 2).sum()
    d1y = g[1:-1, :] - g[:-2, :]; d2y = g[2:, :] - g[:-2, :]
    e1y, e2y = (d1y ** 2).sum(), (d2y ** 2).sum()
    yy = r + 2 * g + b
    IH, IW = g.shape
    return dict(R=r.sum(), G=g.sum(), B=b.sum(), top=yy[:60].sum(), bot=yy[-60:].sum(), tex=e1x / (IH * (IW - 2)),
                Rx=(e1x + 1.0) / (e2x + 1.0), Ry=(e1y + 1.0) / (e2y + 1.0), Y=yy.sum() / (4.0 * IW * IH))


def stats(src):
    ep = ST.read_episode(src if str(src).startswith('hf:') else src, frames='lazy')
    cfg, frames = ep.adapt((320, 240))
    T_ci = invert(ep.T_body_camera)
    Rci = T_ci[:3, :3]
    fx = ep.config['camera']['fx'] * 320 / ep.resolution[0]
    fy = ep.config['camera']['fy'] * 240 / ep.resolution[1]
    N = ep.num_frames
    nf = min(1130, N)
    W = [ep.imu_window(k) for k in range(N)]
    gm = np.array([w[:, 4:7].mean(0) for w in W]); am = np.array([w[:, 1:4].mean(0) for w in W])
    G, A = gm[:nf], am[:nf]
    g2 = (G ** 2).sum(1)
    jd = np.vstack([np.zeros((1, 3)), np.diff(A, axis=0) / 0.05])
    S = A[:20]
    av = max((S ** 2).sum(1).mean() - (S.mean(0) ** 2).sum(), 0)
    out = dict(frames=N, fx_320=fx, hfov_deg=float(np.degrees(2 * np.arctan(160 / fx))),
               start_gyro_rms=float(np.sqrt(g2[:20].mean())), start_accel_dev_rms=float(np.sqrt(av)),
               gyro_rms=float(np.sqrt(g2.mean())), yaw_rms=float(np.sqrt((G[:, 2] ** 2).mean())),
               accel_xy_rms=float(np.sqrt((A[:, :2] ** 2).sum(1).mean())), jerk_rms=float(np.sqrt((jd ** 2).sum() / (3.0 * nf))))
    out['tilt_rms'] = float(np.sqrt(max(out['gyro_rms'] ** 2 - out['yaw_rms'] ** 2, 0)))
    # path (ground truth, all frames)
    st = ep.ground_truth_state()
    p = st[:, :3]
    dist = float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum())
    ft = ep.frame_times
    j = np.searchsorted(ft, ft + 1.0 - 0.025); i = np.flatnonzero(j < N); j = j[i]
    out.update(distance=dist, mean_speed=dist / float(ft[-1] - ft[0]), rms_dist_from_start=float(np.sqrt(((p - p[0]) ** 2).sum(1).mean())),
               rms_spread=float(np.sqrt(((p - p.mean(0)) ** 2).sum(1).mean())), rms_1s_displacement=float(np.sqrt(((p[j] - p[i]) ** 2).sum(1).mean())),
               start_forward_speed=float(st[0, 9]))
    out['centroid_dist_from_start'] = float(np.sqrt(max(out['rms_dist_from_start'] ** 2 - out['rms_spread'] ** 2, 0)))
    # images
    idx = np.unique(np.linspace(0, nf - 1, NS).round().astype(int))
    acc = dict(R=0, G=0, B=0, top=0, bot=0, tex=0.0)
    bx = [[], [], []]; by = [[], [], []]; dark = 0
    for k in idx:
        s = image_stats(np.asarray(frames[k]))
        for a in acc: acc[a] += s[a]
        wc = Rci @ gm[k]
        u, v = fx * abs(wc[1]), fy * abs(wc[0])
        bx[int(u >= 60) + int(u >= 200)].append(s['Rx']); by[int(v >= 60) + int(v >= 200)].append(s['Ry'])
        dark += s['Y'] < 8
    n = len(idx); npix = n * 320 * 240; sm = acc['R'] + acc['G'] + acc['B'] + 1.0
    out.update(Y_mean=(acc['R'] + 2 * acc['G'] + acc['B']) / (4.0 * npix), chroma_g=acc['G'] / sm, chroma_b=acc['B'] / sm,
               grad2_mean=acc['tex'] / n, Y_top=acc['top'] / (4.0 * n * 320 * 60), Y_bottom=acc['bot'] / (4.0 * n * 320 * 60),
               blur_x=[float(np.mean(b)) if b else None for b in bx], blur_y=[float(np.mean(b)) if b else None for b in by],
               blur_nx=[len(b) for b in bx], blur_ny=[len(b) for b in by], dark_sampled=int(dark), n_img=n,
               exposure_s=ep.config.get('episode', {}).get('exposure_seconds'))
    return out


def main():
    outp = sys.argv[1]
    done = set()
    if os.path.exists(outp):
        for l in open(outp):
            try: done.add(json.loads(l)['src'])
            except Exception: pass
    for src in sys.argv[2:]:
        if src in done: continue
        t = time.time()
        try:
            r = stats(src); r['src'] = src
        except Exception as e:
            r = dict(src=src, error=repr(e)[:300])
        r['id'] = os.path.basename(src)[:-4]; r['sec'] = round(time.time() - t, 1)
        with open(outp, 'a') as f: f.write(json.dumps(r) + '\n')


if __name__ == '__main__':
    main()
