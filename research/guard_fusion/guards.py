"""Causal, truth-free three-source guards in the common first-camera gauge.

The vector replay only uses current/past rows. ``OnlineGuard`` provides the same
rule one sample at a time; no fitted parameters or future-source status is used.
"""
from dataclasses import asdict, dataclass
import numpy as np

SOURCE_NAMES = ('vins', 'openvins', 'n2')


@dataclass(frozen=True)
class GuardConfig:
    name: str = 'absolute-consensus'
    mode: str = 'absolute'
    window_s: float = 2.0
    agreement_abs: float = 1.0
    agreement_rel: float = 0.2
    blend: float = 0.5  # OpenVINS share when VIOs agree
    referee: str = 'position'
    fallback_abs: float = 6.0
    fallback_rel: float = 1.0
    max_speed: float = 12.0
    max_accel: float = 100.0
    smooth_s: float = 0.0
    check_init: bool = True
    agreement_space: str = 'position'

    def to_dict(self):
        return asdict(self)


def features(times, sources, window_s=2.0, check_init=True, max_speed=12., max_accel=100.):
    """Compute strictly trailing-window motion and current source health."""
    t = np.asarray(times)
    T = np.stack([sources[s]['T'] for s in SOURCE_NAMES])
    p = T[:, :, :3, 3]
    R = T[:, :, :3, :3]
    n = len(t)
    past = np.searchsorted(t, t - window_s, side='left')
    dp = p - p[:, past]
    local = np.einsum('snji,snj->sni', R[:, past], dp)
    dt = np.diff(t, prepend=t[0] - (t[1]-t[0] if n > 1 else .05))
    velocity = np.diff(p, axis=1, prepend=p[:, :1]) / dt[None, :, None]
    accel = np.diff(velocity, axis=1, prepend=velocity[:, :1]) / dt[None, :, None]
    healthy = (np.isfinite(T).all(axis=(2, 3)) &
               (np.linalg.norm(velocity, axis=2) <= max_speed) &
               (np.linalg.norm(accel, axis=2) <= max_accel))
    for i, s in enumerate(SOURCE_NAMES):
        valid = sources[s].get('valid')
        if valid is not None:
            healthy[i] &= np.asarray(valid, bool)
        if check_init and i < 2:
            init = sources[s].get('init_s')
            healthy[i] &= False if init is None else t >= init - 1e-6
    # N2 remains the bounded fallback; invalid N2 rows become identity in replay.
    return dict(T=T, p=p, R=R, local=local, healthy=healthy, past=past, velocity=velocity)


def _selection(f, c):
    p, d, healthy = f['p'], f['local'], f['healthy']
    signal = p if c.agreement_space == 'position' else d
    vo = np.linalg.norm(signal[0] - signal[1], axis=1)
    magnitude = np.maximum(np.linalg.norm(signal[0], axis=1), np.linalg.norm(signal[1], axis=1))
    agree = healthy[0] & healthy[1] & (vo <= c.agreement_abs + c.agreement_rel*magnitude)
    if c.referee == 'position':
        distance = np.linalg.norm(p[:2] - p[2], axis=2)
        size = np.linalg.norm(p[2], axis=1)
    elif c.referee == 'motion':
        distance = np.linalg.norm(d[:2] - d[2], axis=2)
        size = np.linalg.norm(d[2], axis=1)
    elif c.referee == 'hybrid':
        distance = np.linalg.norm(p[:2]-p[2], axis=2) + 2*np.linalg.norm(d[:2]-d[2], axis=2)
        size = np.linalg.norm(p[2], axis=1) + 2*np.linalg.norm(d[2], axis=1)
    else:
        raise ValueError(f'unknown referee {c.referee}')
    distance = np.where(healthy[:2], distance, np.inf)
    best = np.argmin(distance, axis=0)
    best_d = np.min(distance, axis=0)
    selected = np.where(best_d <= c.fallback_abs + c.fallback_rel*size, best, 2)
    weights = np.eye(3)[selected]
    weights[agree] = (1-c.blend, c.blend, 0)
    return selected, weights, agree


def _integrate(T, weights):
    """Compose selected source-local motions, preserving the deployed splice rule."""
    n = T.shape[1]
    out = np.broadcast_to(np.eye(4), (n,4,4)).copy()
    for k in range(1, n):
        s = int(np.argmax(weights[k]))
        prev = T[s,k-1]
        delta_R = prev[:3,:3].T @ T[s,k,:3,:3]
        delta_p = prev[:3,:3].T @ (T[s,k,:3,3]-prev[:3,3])
        out[k,:3,3] = out[k-1,:3,3] + out[k-1,:3,:3] @ delta_p
        out[k,:3,:3] = out[k-1,:3,:3] @ delta_R
    return out


def replay(times, sources, config=GuardConfig(), return_diagnostics=False):
    """Return N×4×4 poses; all position decisions use observations through k only."""
    c = GuardConfig(**config) if isinstance(config, dict) else config
    f = features(times, sources, c.window_s, c.check_init, c.max_speed, c.max_accel)
    selected, weights, agree = _selection(f, c)
    if c.name.startswith('increment-report'):
        # Historical rule uses the larger V/O displacement for its fallback cap.
        d = f['local']
        magnitude = np.maximum(np.linalg.norm(d[0],axis=1),np.linalg.norm(d[1],axis=1))
        distance = np.linalg.norm(d[:2]-d[2],axis=2)
        best = np.argmin(distance,axis=0)
        selected = np.where(np.min(distance,axis=0) <= 3*(1+magnitude),best,2)
        weights = np.eye(3)[selected]
        weights[agree] = (1.,0.,0.)
        weights[np.asarray(times)-times[0] < c.window_s-1e-6] = (0.,0.,1.)
    if c.mode == 'increment':
        out = _integrate(f['T'], weights)
    elif c.mode == 'absolute':
        out = f['T'][np.argmax(weights,axis=1), np.arange(len(times))].copy()
        # Translation barycentre does not blend attitudes from inconsistent gauges.
        target = np.einsum('ns,snj->nj', weights, f['p'])
        if c.smooth_s > 0:
            # At every source-weight change, preserve continuity then exponentially
            # release the offset. This never rewrites previously emitted poses.
            offset = np.zeros(3)
            outp = np.empty_like(target)
            outp[0] = target[0]
            for k in range(1,len(times)):
                decay = np.exp(-(times[k]-times[k-1])/c.smooth_s)
                offset *= decay
                if not np.array_equal(weights[k], weights[k-1]):
                    if c.name.endswith('-safe'):
                        # Preserve previous emitted position plus the NEW healthy
                        # rule's current increment. Never consult rejected current
                        # source positions while building a continuity offset.
                        new_rule_previous = np.einsum('s,sj->j',weights[k],f['p'][:,k-1])
                        offset = outp[k-1] - new_rule_previous
                    else:
                        previous_rule_now = np.einsum('s,sj->j',weights[k-1],f['p'][:,k])
                        offset += previous_rule_now - target[k]
                outp[k] = target[k]+offset
            target = outp
        out[:,:3,3] = target
    else:
        raise ValueError(f'unknown mode {c.mode}')
    if return_diagnostics:
        return out, dict(selected=selected, weights=weights, agree=agree, healthy=f['healthy'])
    return out


class OnlineGuard:
    """Reference streaming API: only the observed prefix is ever retained/read.

    Increment mode uses exact sequential composition; absolute mode shares replay
    semantics. The reference API favours clarity; a C++ port can keep a ring buffer.
    """
    def __init__(self, config=GuardConfig()):
        self.config = config
        self.t = []
        self.sources = {s: {'T': [], 'valid': [], 'init_s':None} for s in SOURCE_NAMES}

    def step(self, t, observation):
        self.t.append(float(t))
        for s in SOURCE_NAMES:
            row = observation[s]
            self.sources[s]['T'].append(np.asarray(row['T']).copy())
            self.sources[s]['valid'].append(row.get('valid',True))
            self.sources[s]['init_s'] = row.get('init_s', self.sources[s]['init_s'])
        source = {s:dict(v,T=np.asarray(v['T']),valid=np.asarray(v['valid'])) for s,v in self.sources.items()}
        poses, info = replay(np.asarray(self.t),source,self.config,True)
        return int(np.argmax(info['weights'][-1])), poses[-1].copy()


def declared_candidates():
    """Small fixed grid, serialized before any new scoring by evaluate.py."""
    candidates = []
    # Main low-median hypothesis: compare and average absolute common-gauge poses.
    for space in ('position','motion'):
        for a,b in ((.5,.1),(1.,.2),(2.,.3)):
            for blend in (0.,.5,1.):
                for referee in ('position','motion','hybrid'):
                    name=f'abs-{space}-a{a}-b{b}-o{blend}-{referee}'
                    candidates.append(GuardConfig(name=name,agreement_space=space,agreement_abs=a,
                        agreement_rel=b,blend=blend,referee=referee))
    # Predeclared smoothing ablation; moderate 0.5 s release.
    candidates += [GuardConfig(**dict(c.to_dict(),name=c.name+'-smooth',smooth_s=.5))
                   for c in candidates if c.blend==.5]
    # Timestamp-window adaptation of the report's relative-increment baseline.
    # No init or speed gating; failed-source masks remain enforced. N2 provides
    # the first 2 s. Tiny timestamp differences distinguish this from fixed W=40.
    for a,b in ((.5,.1),(1.,.2),(2.,.3)):
        candidates.append(GuardConfig(name=f'increment-report-a{a}-b{b}',mode='increment',
            agreement_space='motion',agreement_abs=a,agreement_rel=b,blend=0.,referee='motion',
            fallback_abs=3.,fallback_rel=3.,check_init=False,max_speed=1e30,max_accel=1e30))
    return candidates
