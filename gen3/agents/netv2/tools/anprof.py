import sys, numpy as np
d = np.load(sys.argv[1], allow_pickle=True); nsteps = int(sys.argv[2]) if len(sys.argv) > 2 else 97
names = sorted(set(k[:-6] for k in d.files if k.endswith('_steps')))
S = np.concatenate([d[n + '_steps'] for n in names]); T = np.concatenate([d[n + '_tot'] for n in names])
print('flights', len(names), 'steps', len(S), 'frame fuel max %.2fM p99 %.2fM med %.2fM' % (T.max() / 1e6, np.percentile(T, 99) / 1e6, np.median(T) / 1e6))
ks = S[:, 1].astype(int); f = S[:, 2]
for lo, hi, nm in eval(sys.argv[3]) if len(sys.argv) > 3 else [(0, 16, 'gray0'), (16, 32, 'gray5'), (32, 56, 'prep'), (56, 60, 'var'), (60, 62, 'pool'), (62, 74, 'conv0'), (74, 86, 'conv1'), (86, 92, 'conv2'), (92, 95, 'conv3'), (95, 97, 'head')]:
    m = (ks >= lo) & (ks < hi)
    if m.any(): print(f'{nm:6s} steps {hi-lo:3d} fuel/step mean {f[m].mean()/1e3:7.1f}k max {f[m].max()/1e3:7.1f}k  total/run {f[m].mean()*(hi-lo)/1e6:.2f}M')
# latency: frames from k==0 to k==nsteps-1 per run
for n in names[:6]:
    s = d[n + '_steps']; st = s[s[:, 1] == 0, 0]; en = s[s[:, 1] == nsteps - 1, 0]
    per = np.bincount(s[:, 0].astype(int)); print(n, 'runs', len(en), 'latency frames', (en[:len(st)] - st[:len(en)]).astype(int)[:12], 'steps/frame (active) mean %.1f' % per[per > 0].mean())
