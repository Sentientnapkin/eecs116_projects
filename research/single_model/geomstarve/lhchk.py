"""lhchk.py RUNDIR POOL: truth-pose fit directions of horizontal lines: yaw angle mod 90 deg per flight (Manhattan check)"""
import sys, glob, numpy as np
sys.argv, A = sys.argv[:1], sys.argv[1:]
exec(open('lchk.py').read().split('RUN, POOL = sys.argv[1:3]')[0])
RUN, POOL = A
for d in sorted(glob.glob(RUN + '/*/')):
    ep = d.rstrip('/').split('/')[-1]; se = glob.glob(d + 'report/logs/*/stderr.txt')
    if not se: continue
    e = read_episode(f'{POOL}/{ep}.zip', frames='none'); C = np.asarray(e.camera_poses_world()); T = poses_to_matrices(np.concatenate([C, np.zeros((len(C), 6))], 1))
    ph = []
    for line in open(se[0]):
        if not line.startswith('LO '): continue
        v = line.split('|')[1].split(); m = len(v) // 6; fr = [int(v[6 * k]) for k in range(m)]; obs = [tuple(float(x) for x in v[6 * k + 1:6 * k + 6]) for k in range(m)]
        try: fit([T[f][:3, :3] for f in fr], [T[f][:3, 3] for f in fr], obs)
        except Exception: continue
        D = LASTD
        if abs(D[2]) < np.sin(np.radians(10)): ph.append(np.degrees(np.arctan2(D[1], D[0])) % 90)
    ph = np.array(ph); h = np.histogram(ph, bins=np.arange(0, 91, 5))[0]
    c = np.degrees(np.angle(np.mean(np.exp(1j * np.radians(ph) * 4)))) / 4 % 90
    dev = (ph - c + 45) % 90 - 45
    print(ep, 'n', len(ph), 'manhattan phi0 %.1f' % c, '|dev| med %.1f p90 %.1f frac<3deg %.2f' % (np.median(abs(dev)), np.percentile(abs(dev), 90), np.mean(abs(dev) < 3)), 'hist5deg', h.tolist())
