"""Twin matching.  python match.py shortlist K   -> shortlist.txt (srcs to featurize, metadata distance, top K per episode)
                 python match.py final [WEIGHTS.json] -> twin24.txt, twin120.txt, coverage.txt, match_table.json
Candidates: every flight in gen3/out/up except the v3 test (s3v3te*) and v1 test (s3te*) splits."""
import json, glob, os, sys
import numpy as np


def linear_sum_assignment(a):
    """min-cost assignment, rows <= cols (e-maxx Hungarian, O(n^2 m)); returns (rows, cols)."""
    a = np.asarray(a, float); n, m = a.shape
    u = np.zeros(n + 1); v = np.zeros(m + 1); p = np.zeros(m + 1, int); way = np.zeros(m + 1, int)
    for i in range(1, n + 1):
        p[0] = i; j0 = 0; minv = np.full(m + 1, np.inf); used = np.zeros(m + 1, bool)
        while True:
            used[j0] = True; i0 = p[j0]
            cur = a[i0 - 1] - u[i0] - v[1:]
            free = ~used[1:]
            upd = free & (cur < minv[1:])
            minv[1:][upd] = cur[upd]; way[1:][upd] = j0
            cand = np.where(free, minv[1:], np.inf); j1 = int(np.argmin(cand)) + 1; delta = cand[j1 - 1]
            u[p[used]] += delta; v[used] -= delta; minv[1:][free] -= delta
            j0 = j1
            if p[j0] == 0: break
        while True:
            j1 = way[j0]; p[j0] = p[j1]; j0 = j1
            if j0 == 0: break
    rows, cols = [], []
    for j in range(1, m + 1):
        if p[j]: rows.append(p[j] - 1); cols.append(j - 1)
    o = np.argsort(rows)
    return np.array(rows)[o], np.array(cols)[o]

T = '/data/backups/rganapa/Sebastian/gen3/twin'
G = '/data/backups/rganapa/Sebastian/gen3'
SRV = json.load(open('/data/backups/rganapa/Sebastian/eecs116_projects/eecs116_vio/stage3/probe_decoded.json'))
CLS = ['room'] * 12 + ['warehouse'] * 6 + ['forest'] * 6
HF = {os.path.basename(p)[:-4]: p for p in open(f'{T}/hf_zips.txt').read().split()}
LOG = {'distance', 'rms_dist_from_start', 'rms_spread', 'tilt_rms', 'yaw_rms', 'jerk_rms', 'start_gyro_rms', 'grad2_mean', 'mean_speed'}


def server_feats(e):
    dy, im = e['dynamics'], e['image']
    bx, by = e['blur_ratio_x_by_px_speed'], e['blur_ratio_y_by_px_speed']
    return dict(hover=float(abs(e['start_forward_speed']) < 0.005), start_forward_speed=e['start_forward_speed'],
                start_gyro_rms=e['start_1s']['gyro_rms'], hfov_deg=e['camera']['hfov_deg'],
                blur_x0=bx[0], blur_x1=bx[1], blur_y0=by[0], blur_y1=by[1],
                mean_speed=e['path']['mean_speed'], distance=e['path']['distance'],
                rms_dist_from_start=e['path']['rms_dist_from_start'], rms_spread=e['path']['rms_spread'],
                tilt_rms=float(np.sqrt(max(dy['gyro_rms'] ** 2 - dy['yaw_rms'] ** 2, 1e-4))), yaw_rms=dy['yaw_rms'],
                jerk_rms=dy['jerk_rms'], Y_mean=im['Y_mean'], grad2_mean=im['grad2_mean'], chroma_b=im['chroma_b'],
                chroma_g=im['chroma_g'], Y_tb=im['Y_top'] - im['Y_bottom'])


def meta_feats(m):
    # recorded metadata -> probe definitions: gyro from raw rows includes white noise (sigma 0.07/axis, frame mean removes 90 %),
    # jerk summed over axes (probe: per-axis RMS -> /sqrt 3)
    corr = 3 * 0.07 ** 2 * 0.9
    g2 = max(m['gyro_rms'] ** 2 - corr, 1e-4); y2 = max(m['yaw_rms'] ** 2 - corr / 3, 1e-4)
    return dict(hover=float(m['start'] == 'hover'), start_forward_speed=m['start_fwd_speed'], hfov_deg=m['fov_deg'],
                mean_speed=m['mean_speed'], distance=m['path_m'], rms_dist_from_start=m['rms_dist_from_start'],
                rms_spread=m['rms_spread'], tilt_rms=float(np.sqrt(max(g2 - y2, 1e-4))), yaw_rms=float(np.sqrt(y2)),
                jerk_rms=m['jerk_rms'] / np.sqrt(3), Y_mean=m['luma_mean'], exposure_s=m['exposure_s'])


def py_feats(p):
    bx, by, nx, ny = p['blur_x'], p['blur_y'], p['blur_nx'], p['blur_ny']
    return dict(hover=float(abs(p['start_forward_speed']) < 0.005), start_forward_speed=p['start_forward_speed'],
                start_gyro_rms=min(p['start_gyro_rms'], 2.0), hfov_deg=p['hfov_deg'],
                blur_x0=bx[0] if nx[0] >= 3 else None, blur_x1=bx[1] if nx[1] >= 3 else None,
                blur_y0=by[0] if ny[0] >= 3 else None, blur_y1=by[1] if ny[1] >= 3 else None,
                mean_speed=p['mean_speed'], distance=p['distance'], rms_dist_from_start=p['rms_dist_from_start'],
                rms_spread=p['rms_spread'], tilt_rms=max(p['tilt_rms'], 1e-2), yaw_rms=max(p['yaw_rms'], 1e-2),
                jerk_rms=p['jerk_rms'], Y_mean=p['Y_mean'], grad2_mean=max(p['grad2_mean'], 1e-2), chroma_b=p['chroma_b'],
                chroma_g=p['chroma_g'], Y_tb=p['Y_top'] - p['Y_bottom'], exposure_s=p.get('exposure_s'))


# weights: start state, FoV, blur highest; then speed / extent / rotation / jerk; then luminance / texture
W_META = dict(hover=4, start_forward_speed=4, hfov_deg=4, mean_speed=2, rms_dist_from_start=2, rms_spread=2, tilt_rms=2,
              yaw_rms=2, jerk_rms=2, Y_mean=0.5)
W_FULL = dict(hover=4, start_forward_speed=4, start_gyro_rms=3, hfov_deg=4, blur_x0=2, blur_y0=2, blur_x1=1, blur_y1=1,
              mean_speed=2, rms_dist_from_start=2, rms_spread=2, tilt_rms=2, yaw_rms=2, jerk_rms=2,
              Y_mean=0.5, grad2_mean=0.5, chroma_b=0.25, Y_tb=0.25)


def candidates():
    C = {}
    for p in glob.glob(f'{G}/out/up/*.json'):
        i = os.path.basename(p)[:-5]
        if i == 'shards' or i.startswith('s3v3te') or i.startswith('s3te'): continue
        try: m = json.load(open(p))
        except Exception: continue
        if m.get('frames') != 1200 or 'rms_spread' not in m: continue
        k = f'{G}/out/keep/{i}.zip'
        src = k if os.path.exists(k) else ('hf:' + HF[i] if i in HF else None)
        if src: C[i] = dict(meta=m, src=src, cls=m['setting_class'])
    return C


def tr(f, x):
    return np.log(x) if f in LOG else x


def scales(rows, W):
    """robust per-class scale (1.4826 MAD of the candidate pool, in transformed units), floored."""
    S = {}
    for f in W:
        if f == 'hover': S[f] = 1 / 3.0; continue   # a hover mismatch counts as a 3-sigma gap
        v = np.array([tr(f, r[f]) for r in rows if r.get(f) is not None], float)
        S[f] = max(1.4826 * np.median(np.abs(v - np.median(v))), 1e-3) if len(v) > 5 else 1.0
    return S


def zgaps(s, c, S, W):
    z = {}
    for f in W:
        a, b = s.get(f), c.get(f)
        if a is None or b is None: continue
        if f == 'start_gyro_rms' and a >= 1.99: b = min(b, 2.0)
        z[f] = (tr(f, b) - tr(f, a)) / S[f]
    return z


def dist(z, W):
    wsum = sum(W[f] for f in z)
    return float(np.sqrt(sum(W[f] * z[f] ** 2 for f in z) / max(wsum, 1e-9))) if z else 9e9


def main():
    mode = sys.argv[1]
    C = candidates()
    server = [server_feats(e) for e in SRV]
    if mode == 'shortlist':
        K = int(sys.argv[2])
        out = set();
        for cls in ('room', 'warehouse', 'forest'):
            ids = [i for i in C if C[i]['cls'] == cls]
            F = {i: meta_feats(C[i]['meta']) for i in ids}
            S = scales(list(F.values()), W_META)
            for e in [j for j in range(24) if CLS[j] == cls]:
                d = sorted((dist(zgaps(server[e], F[i], S, W_META), W_META), i) for i in ids)
                out |= {i for _, i in d[:K]}
        locs = [i for i in C if C[i]['src'].startswith('/')]
        out |= set(locs)
        open(f'{T}/shortlist.txt', 'w').write('\n'.join(C[i]['src'] for i in sorted(out)) + '\n')
        print('candidates', len(C), 'shortlist', len(out), 'local', len(locs), 'remote', sum(not C[i]['src'].startswith('/') for i in out))
        return
    W = dict(W_FULL)
    if len(sys.argv) > 2: W.update(json.load(open(sys.argv[2])))
    W = {f: w for f, w in W.items() if w > 0}
    P = {}
    for fn in glob.glob(f'{T}/feat_*.jsonl'):
        for l in open(fn):
            r = json.loads(l)
            if 'error' not in r and r['id'] in C and r.get('frames') == 1200: P[r['id']] = r
    feats = {i: py_feats(P[i]) for i in P}
    D = {}; Z = {}
    S_all = {}
    for cls in ('room', 'warehouse', 'forest'):
        ids = sorted(i for i in feats if C[i]['cls'] == cls)
        S = scales([feats[i] for i in ids], W); S_all[cls] = S
        for e in [j for j in range(24) if CLS[j] == cls]:
            for i in ids:
                z = zgaps(server[e], feats[i], S, W); Z[e, i] = z; D[e, i] = dist(z, W)
    ids = sorted(feats)
    M = np.full((24, len(ids)), 1e6)
    for (e, i), d in D.items(): M[e, ids.index(i)] = d
    r, c = linear_sum_assignment(M)
    twin24 = [ids[c[list(r).index(e)]] for e in range(24)]
    M5 = np.repeat(M, 5, axis=0)
    r5, c5 = linear_sum_assignment(M5)
    twin120 = [[] for _ in range(24)]
    for a, b in zip(r5, c5): twin120[a // 5].append(ids[b])
    for e in range(24): twin120[e].sort(key=lambda i: D[e, i])
    tag = sys.argv[3] if len(sys.argv) > 3 else ''
    open(f'{T}/twin24{tag}.txt', 'w').write(''.join(f'{e + 1}\t{twin24[e]}\t{C[twin24[e]]["src"]}\n' for e in range(24)))
    open(f'{T}/twin120{tag}.txt', 'w').write(''.join(f'{e + 1}\t{i}\t{C[i]["src"]}\n' for e in range(24) for i in twin120[e]))
    json.dump(dict(weights=W, scales=S_all, twin24=twin24, twin120=twin120, server=server,
                   feats={i: feats[i] for i in set(twin24) | {x for t in twin120 for x in t}},
                   dist={f'{e + 1}:{i}': D[e, i] for e in range(24) for i in twin120[e] + [twin24[e]]},
                   z={f'{e + 1}:{i}': Z[e, i] for e in range(24) for i in twin120[e] + [twin24[e]]}),
              open(f'{T}/match_table{tag}.json', 'w'), indent=0)
    # coverage table
    fl = ['start_forward_speed', 'start_gyro_rms', 'hfov_deg', 'blur_x0', 'blur_y0', 'mean_speed', 'rms_dist_from_start', 'tilt_rms', 'yaw_rms', 'jerk_rms', 'Y_mean', 'grad2_mean']
    ab = dict(start_forward_speed='v0z', start_gyro_rms='g0', hfov_deg='fov', blur_x0='bx0', blur_y0='by0', mean_speed='spd',
              rms_dist_from_start='ext', tilt_rms='tilt', yaw_rms='yaw', jerk_rms='jerk', Y_mean='Y', grad2_mean='tex')
    L = [f'pool: {len(feats)} featurized candidates (room {sum(C[i]["cls"] == "room" for i in feats)}, warehouse {sum(C[i]["cls"] == "warehouse" for i in feats)}, forest {sum(C[i]["cls"] == "forest" for i in feats)})',
         'ep cls  v0z    | twin24 d | twin120 d(mean,max) | twin24 z-gaps: ' + ' '.join(f'{ab[f]:>5s}' for f in fl) + ' | flag']
    for e in range(24):
        i = twin24[e]; z = Z[e, i]; d5 = [D[e, j] for j in twin120[e]]
        big = [ab[f] for f in fl if abs(z.get(f, 0)) > 1.5]
        flag = 'POOR' if D[e, i] > 0.8 or np.mean(d5) > 1.0 else ('weak' if D[e, i] > 0.5 or np.mean(d5) > 0.7 else '')
        L.append(f'{e + 1:2d} {CLS[e][:4]} {server[e]["start_forward_speed"]:+5.2f} | {D[e, i]:8.2f} | {np.mean(d5):6.2f} {max(d5):6.2f}      | '
                 + ' '.join(f'{z[f]:+5.1f}' if f in z else '    -' for f in fl) + f' | {flag} {",".join(big)}')
    L.append(f'mean d: twin24 {np.mean([D[e, twin24[e]] for e in range(24)]):.3f}  twin120 {np.mean([D[e, j] for e in range(24) for j in twin120[e]]):.3f}')
    open(f'{T}/coverage{tag}.txt', 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))


if __name__ == '__main__':
    main()
