"""i5 re-render harness: replay a stored flight's GT poses through a standalone hyperlux renderer with extra outputs.
python rr.py ZIP OUTDIR [mode]   modes: test (timing/convention checks + throughput)
Writes OUTDIR/<id>.json (results). GPU via CUDA_VISIBLE_DEVICES."""
import sys, os, json, time, zipfile, math, io
import numpy as np, cv2
cv2.setNumThreads(2)
import conta, hyperlux
from hyperlux.camera import CameraSpec, RGB, Depth, Normals, Segmentation, Flow, FlowStatus

def qmat(w, x, y, z):
    return np.array([[1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)], [2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)], [2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)]])

class Flight:
    def __init__(s, zp):
        s.z = zipfile.ZipFile(zp); n = s.z.namelist(); s.root = n[0].split('/')[0]
        s.ep = json.loads(s.z.read(f'{s.root}/episode.json')); s.cfg = s.ep['config']; s.meta = s.ep['meta']
        g = np.loadtxt(io.StringIO(s.z.read(f'{s.root}/mav0/state_groundtruth_estimate0/data.csv').decode()), delimiter=',', comments='#')
        s.gt_t = g[:, 0]*1e-9; s.gt_p = g[:, 1:4]; s.gt_q = g[:, 4:8]  # w x y z
        c = np.loadtxt(io.StringIO(s.z.read(f'{s.root}/mav0/cam0/data.csv').decode()), delimiter=',', comments='#', dtype=str)
        s.ft = c[:, 0].astype(np.int64)*1e-9; s.fn = list(c[:, 1])
        s.T_bc = np.array(s.cfg['imu']['T_imu_cam']).reshape(4, 4)  # camera in body (cols right, down, forward)
        sp = s.meta['spawn']; s.t_sc = np.array(sp['scene_translation']); cy, sy = sp['scene_yaw']; s.Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
        s.fov = s.cfg['camera']['horizontal_fov_degrees']; c_ = s.cfg['camera']; s.K = np.array([[c_['fx'], 0, c_['cx']], [0, c_['fy'], c_['cy']], [0, 0, 1]])
        s.k = int(s.meta.get('sub_frames', 1)); fl = s.meta.get('flight', {}); s.scene = fl.get('glb') or ('conta:' + sp['scene'])
        s.gain = float(s.meta.get('linear_gain', 1.0)); s.bs = float(s.meta.get('brightness_scale', 1.0))
    def frame(s, i):
        return cv2.imdecode(np.frombuffer(s.z.read(f'{s.root}/mav0/cam0/data/{s.fn[i]}'), np.uint8), cv2.IMREAD_GRAYSCALE)
    def pose(s, t):
        """GT body pose at time t (linear p, nlerp q); returns R_wb, p_wb (gravity-aligned state frame)."""
        j = int(np.clip(np.searchsorted(s.gt_t, t) - 1, 0, len(s.gt_t)-2)); a = (t - s.gt_t[j])/(s.gt_t[j+1]-s.gt_t[j])
        q = (1-a)*s.gt_q[j] + a*s.gt_q[j+1]*np.sign(np.dot(s.gt_q[j], s.gt_q[j+1])); q /= np.linalg.norm(q)
        return qmat(*q), (1-a)*s.gt_p[j] + a*s.gt_p[j+1]
    def cam_world(s, t):
        """camera pose in the GT (state) frame: R_wc (OpenCV axes), p_wc."""
        R, p = s.pose(t); return R @ s.T_bc[:3, :3], p + R @ s.T_bc[:3, 3]
    def cam_row(s, r, t):
        Rwc, pwc = s.cam_world(t); pos = s.Rz @ pwc + s.t_sc; fwd = s.Rz @ Rwc[:, 2]; up = -(s.Rz @ Rwc[:, 1])
        return np.asarray(r.camera(tuple(pos), tuple(pos + fwd), up=tuple(up), fov=s.fov), dtype=np.float32).reshape(-1)

def make_renderer(W, H, B, outs, fid='high'):
    return hyperlux.HyperLux(width=W, height=H, batch_size=B, num_probes=0, cameras=(CameraSpec('camera', tuple(outs)),), fidelity=fid, anti_aliasing_grid=1)

def gray_of(rgb):  # float sRGB (H,W,3|4) -> uint8 gray
    x = np.clip(rgb[..., :3]*255+.5, 0, 255).astype(np.uint8); return cv2.cvtColor(x, cv2.COLOR_RGB2GRAY)

def ncc(a, b):
    a = cv2.Laplacian(a.astype(np.float32), cv2.CV_32F, ksize=3); b = cv2.Laplacian(b.astype(np.float32), cv2.CV_32F, ksize=3)
    a -= a.mean(); b -= b.mean(); return float((a*b).sum()/np.sqrt((a*a).sum()*(b*b).sum()+1e-9))

def test(zp, od):
    F = Flight(zp); fid = F.ep['name']; res = dict(id=fid, k=F.k, fov=F.fov, scene=F.scene, n_frames=len(F.ft))
    t0 = time.time(); path = F.scene if F.scene.endswith('.glb') else conta.resolve(F.scene); sc = hyperlux.load_scene(path, fidelity='high', preserve_instances=True); res['scene_load_s'] = time.time()-t0
    W, H = F.cfg['image']['width'], F.cfg['image']['height']; B = 16
    outs = [RGB('float32'), Depth(), Normals(), Segmentation(), Flow('backward'), FlowStatus('backward'), Flow('forward'), FlowStatus('forward')]
    t0 = time.time(); r = make_renderer(W, H, B, outs); r.init(sc); res['build_init_s'] = time.time()-t0
    res['layouts'] = {repr(d): [list(h.layout.shape), h.layout.dtype] for d, h in r.outputs.items()}
    O = {type(d).__name__ + getattr(d, 'direction', ''): h for d, h in r.outputs.items()}
    row = F.cam_row(r, F.ft[0]); d00, du, dv = row[3:6], row[6:9], row[9:12]
    res['cam_row_check'] = dict(fx_from_du=float(W/np.linalg.norm(du)*np.linalg.norm(d00 + du/2 + dv/2)), fy_from_dv=float(H/np.linalg.norm(dv)*np.linalg.norm(d00 + du/2 + dv/2)), fx_episode=F.K[0, 0])
    dt = 0.005
    # (a) timing alignment: NCC of rendered (k=1 mid-exposure sub-render) vs stored frame at offsets of whole IMU steps
    idx = np.linspace(40, len(F.ft)-2, B, dtype=int); offs = [-3, -2, -1, 0, 1, 2, 3]; tab = {}
    for o in offs:
        r.set_cameras(np.stack([F.cam_row(r, F.ft[i] + o*dt) for i in idx])); r.render(); r.synchronize()
        rgb = O['RGB'].read(); tab[o] = float(np.mean([ncc(gray_of(rgb[j]), F.frame(i)) for j, i in enumerate(idx)]))
    res['ncc_vs_offset_steps'] = tab
    # (b) exposure reproduction: average the k sub-renders (linear light) -> photometric match to the stored frame
    sub = []
    for j in range(F.k):
        r.set_cameras(np.stack([F.cam_row(r, F.ft[i] + (j-(F.k-1)/2)*dt) for i in idx])); r.render(); r.synchronize(); sub.append(O['RGB'].read()[..., :3].copy())
    sub = np.stack(sub); lin = np.where(sub <= .04045, sub/12.92, ((sub+.055)/1.055)**2.4).mean(0)
    enc = lambda l: np.where(l <= .0031308, 12.92*l, 1.055*np.power(np.clip(l, 1e-9, 1), 1/2.4)-.055)
    res['photometric_means'] = {nm: float(np.mean([gray_of(enc(lin[j]*m)).mean() for j in range(4)])) for nm, m in (('none', 1.0), ('gain', F.gain), ('gain_x_bs', F.gain*F.bs), ('bs', F.bs))}
    res['photometric_means']['stored'] = float(np.mean([F.frame(i).mean() for i in idx[:4]]))
    srgb = enc(lin*F.gain)
    st = []; ph = []
    for j, i in enumerate(idx):
        g = gray_of(srgb[j]); f = F.frame(i); st.append(ncc(g, f)); m = (f > 5) & (f < 250)
        ph.append(float(np.corrcoef(g[m].astype(float), f[m].astype(float))[0, 1]) if m.sum() > 100 else float('nan'))
        if j < 2: cv2.imwrite(f'{od}/{fid}_f{i}_cmp.png', np.hstack([f, g]))
    res['blur_repro'] = dict(ncc_laplacian=float(np.mean(st)), pixel_corr=float(np.nanmean(ph)), stored_mean=float(np.mean([F.frame(i).mean() for i in idx])), render_mean=float(np.mean([gray_of(srgb[j]).mean() for j in range(len(idx))])))
    # (c) conventions: depth z vs ray, flow direction; analytic flow from depth+GT poses vs renderer flow
    i0 = idx[:8]; prev = np.stack([F.cam_row(r, F.ft[i-1]) for i in idx]); cur = np.stack([F.cam_row(r, F.ft[i]) for i in idx])
    r.set_cameras(prev); r.render(); r.advance_flow(); r.set_cameras(cur); r.render(); r.synchronize()
    D = O['Depth'].read().copy(); N = O['Normals'].read().copy(); S = O['Segmentation'].read().copy()
    FB = O['Flowbackward'].read().copy(); SB = O['FlowStatusbackward'].read().copy(); FF = O['Flowforward'].read().copy(); SF = O['FlowStatusforward'].read().copy()
    res['shapes'] = dict(D=D.shape, N=N.shape, S=S.shape, FB=FB.shape, SB=SB.shape)
    Ki = np.linalg.inv(F.K); u, v = np.meshgrid(np.arange(W), np.arange(H)); pix = np.stack([u, v, np.ones_like(u)], -1).reshape(-1, 3).astype(float)
    conv = []
    for j, i in enumerate(idx):
        Rc1, pc1 = F.cam_world(F.ft[i]); Rc0, pc0 = F.cam_world(F.ft[i-1]); d = D[j].reshape(-1).astype(float); ok = np.isfinite(d) & (d > 0)
        ray = pix @ Ki.T
        out = {}
        for name, Xc in (('z', ray*d[:, None]), ('ray', ray/np.linalg.norm(ray, axis=1, keepdims=True)*d[:, None])):
            Xw = Xc @ Rc1.T + pc1; X0 = (Xw - pc0) @ Rc0; q = X0 @ F.K.T; q = q[:, :2]/q[:, 2:3]; fl = q - pix[:, :2]
            for fn, Fl, Sx in (('bwd', FB[j], SB[j]), ('fwd', FF[j], SF[j])):
                fr = Fl.reshape(-1, Fl.shape[-1])[:, :2].astype(float); m = ok & (Sx.reshape(-1) == 0) & (X0[:, 2] > 0.05)
                e = np.linalg.norm(fl[m] - fr[m], axis=1); out[f'{name}_{fn}'] = [float(np.median(e)), float(np.percentile(e, 95)), int(m.sum())]
        out['flow_mag_med'] = float(np.median(np.linalg.norm(FB[j].reshape(-1, FB.shape[-1])[:, :2], axis=1)))
        out['status_counts_bwd'] = np.bincount(SB[j].reshape(-1).astype(np.int64), minlength=5).tolist()
        out['valid_depth_frac'] = float(ok.mean()); out['depth_med'] = float(np.median(d[ok])) if ok.any() else None
        out['n_instances'] = int(len(np.unique(S[j]))); out['normal_norm_med'] = float(np.median(np.linalg.norm(N[j].reshape(-1, N.shape[-1])[:, :3], axis=1)))
        conv.append(out)
    res['conventions'] = conv
    np.savez_compressed(f'{od}/{fid}_sample.npz', depth=D[:2].astype(np.float16), normals=N[:2].astype(np.float16), seg=S[:2], flow_bwd=FB[:2].astype(np.float16), status_bwd=SB[:2].astype(np.uint8))
    # (d) throughput: whole flight at mid-exposure poses, depth-only / all outputs, at native res and 320x240
    for tag, outs2, (w2, h2), B2 in (('depth_640', [Depth()], (W, H), 32), ('all_640', outs, (W, H), 32), ('depth_320', [Depth()], (320, 240), 64), ('rgbdepth_320', [RGB('float32'), Depth()], (320, 240), 64)):
        r2 = r if tag == 'all_640' else None
        if r2 is None:
            t0 = time.time(); r2 = make_renderer(w2, h2, B2, outs2); r2.init(sc); bt = time.time()-t0
        else: bt = 0.0; r2 = make_renderer(w2, h2, B2, outs2); r2.init(sc)
        hs = list(r2.outputs.values()); n = len(F.ft); t0 = time.time(); tr = 0.0
        for a in range(0, n - n % B2, B2):
            r2.set_cameras(np.stack([F.cam_row(r2, F.ft[i]) for i in range(a, a+B2)])); r2.render(); r2.synchronize(); t1 = time.time()
            for h in hs: h.read()
            tr += time.time()-t1
        el = time.time()-t0; res[f'thru_{tag}'] = dict(frames=n - n % B2, s=el, fps=(n - n % B2)/el, readback_s=tr, build_s=bt); del r2
    json.dump(res, open(f'{od}/{fid}.json', 'w'), indent=1, default=str)

if __name__ == '__main__':
    test(sys.argv[1], sys.argv[2])
