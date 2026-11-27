"""i6 shared code: dense maps (derotated / raw frames, pyramidal Lucas-Kanade flow), input-ablation sample builder,
generic ablation net, translation-direction estimator from derotated flow. Reuses lv4 (copied read-only from agents/netv2)."""
import sys, json
from pathlib import Path
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F
sys.path.insert(0, str(Path(__file__).parent))
import lv4
from lv4 import T, D, H0, W0

SV = [1., -1., 1.]; SA = [-1., 1., -1.]   # mirror (body y -> -y) signs: vector / pseudo-vector


def warp_pair(Dd, a, b, derot=True):
    """frames a,b (96x128) -> X (B,2,H,W) normalised [frame a, frame b warped by gyro rotation], mask M (B,1,H,W), K parts"""
    dev = a.device; B = len(a)
    u, v = T.pixel_grid(dev)
    fx, fy, cx, cy = [Dd.K[a, i].view(B, 1, 1) for i in range(4)]
    idx = torch.stack([a, b], 1).cpu()
    fr = Dd.frames[idx.view(-1)].to(dev, non_blocking=True).view(B, 2, H0, W0).float()
    if derot:
        ds = torch.stack([(u - cx) / fx, (v - cy) / fy, torch.ones(B, H0, W0, device=dev)], -1)
        Rb = Dd.R[a].transpose(1, 2) @ Dd.R[b]; Rc = Dd.Rbc.T @ Rb @ Dd.Rbc
        dk = torch.einsum('bji,bhwj->bhwi', Rc, ds); z = dk[..., 2].clamp(min=1e-3)
        uk = fx * dk[..., 0] / z + cx; vk = fy * dk[..., 1] / z + cy
        gx = (uk + 0.5) / W0 * 2 - 1; gy = (vk + 0.5) / H0 * 2 - 1
        out = F.grid_sample(fr[:, 1:2], torch.stack([gx, gy], -1), mode='bilinear', padding_mode='zeros', align_corners=False)[:, 0]
        ok = ((gx.abs() <= 1) & (gy.abs() <= 1) & (dk[..., 2] > 1e-3)).float()
    else:
        out = fr[:, 1]; ok = torch.ones(B, H0, W0, device=dev)
    X = torch.stack([fr[:, 0], out], 1); M = ok[:, None]
    allm = torch.cat([torch.ones(B, 1, H0, W0, device=dev), M], 1)
    mean = (X * allm).sum((2, 3), keepdim=True) / allm.sum((2, 3), keepdim=True).clamp(min=1)
    var = (((X - mean) * allm) ** 2).sum((2, 3), keepdim=True) / allm.sum((2, 3), keepdim=True).clamp(min=1)
    X = (X - mean) / (var.sqrt() + 5.0) * allm
    return X, M, (fx, fy, cx, cy)


def _grad(I):
    gx = F.pad(I[..., :, 2:] - I[..., :, :-2], (1, 1, 0, 0), mode='replicate') * 0.5
    gy = F.pad(I[..., 2:, :] - I[..., :-2, :], (0, 0, 1, 1), mode='replicate') * 0.5
    return gx, gy


def _warp(I, fl):
    B, _, H, W = I.shape
    v, u = torch.meshgrid(torch.arange(H, device=I.device, dtype=I.dtype), torch.arange(W, device=I.device, dtype=I.dtype), indexing='ij')
    gx = (u + fl[:, 0] + 0.5) / W * 2 - 1; gy = (v + fl[:, 1] + 0.5) / H * 2 - 1
    return F.grid_sample(I, torch.stack([gx, gy], -1), mode='bilinear', padding_mode='border', align_corners=False)


def lk_flow(I0, I1, levels=4, iters=4, win=7):
    """pyramidal Lucas-Kanade (dense, windowed least squares). I0,I1 (B,1,H,W). -> flow (B,2,H,W) in px (I1(x+f) ~ I0(x)), conf (B,1,H,W)=log min-eig"""
    P0, P1 = [I0], [I1]
    for _ in range(levels - 1): P0.append(F.avg_pool2d(P0[-1], 2)); P1.append(F.avg_pool2d(P1[-1], 2))
    fl = torch.zeros(I0.shape[0], 2, *P0[-1].shape[2:], device=I0.device)
    box = lambda x: F.avg_pool2d(F.pad(x, (win // 2,) * 4, mode='replicate'), win, 1)
    for L in range(levels - 1, -1, -1):
        A, Bm = P0[L], P1[L]
        if fl.shape[2:] != A.shape[2:]: fl = 2 * F.interpolate(fl, size=A.shape[2:], mode='bilinear', align_corners=False)
        Ix, Iy = _grad(A); sxx, syy, sxy = box(Ix * Ix), box(Iy * Iy), box(Ix * Iy)
        det = sxx * syy - sxy * sxy + 1e-3
        for _ in range(iters):
            It = _warp(Bm, fl) - A
            bx, by = -box(Ix * It), -box(Iy * It)
            du = (syy * bx - sxy * by) / det; dv = (sxx * by - sxy * bx) / det
            fl = fl + torch.cat([du, dv], 1).clamp(-3, 3)
    tr = sxx + syy; mn = 0.5 * (tr - torch.sqrt(((sxx - syy) ** 2 + 4 * sxy * sxy).clamp(min=0)))
    return fl, torch.log(mn.clamp(min=1e-4))


def imu_vec(Dd, a, b):
    """the 19-d lv4 vector (no time reversal)"""
    B = len(a); Rs = Dd.R[a]
    dv = torch.einsum('bji,bj->bi', Rs, Dd.V[b] - Dd.V[a]) / (0.05 * 5 * 9.81)
    return torch.cat([Dd.f[a] / 9.81, Dd.g[a], Dd.f[b] / 9.81, Dd.g[b], dv, T.rot_vec(Rs.transpose(1, 2) @ Dd.R[b]), (Dd.fx[a] / 100.0).view(B, 1)], 1)

VEC19_SIGN = SV + SA + SV + SA + SV + SA + [1.]

# variant -> (image kind, vec kind)
VARIANTS = {
    'all':        ('img2', 'imu'),        # reference = deployed input set (derotated 2 frames + IMU + fx)
    'imu_only':   (None, 'imu'),
    'orient_only': (None, 'orient'),      # gravity direction (from specific force) at a,b + relative rotation; no image, no dv / magnitudes
    'img_only':   ('img2', None),         # derotated 2 frames, no IMU at all
    'single_img': ('img1', 'imu'),        # frame a only + IMU
    'raw2':       ('raw2', 'imu'),        # 2 frames WITHOUT gyro derotation + IMU
    'no_intr':    ('img2', 'imu_nofx'),   # drop focal length scalar
    'rays':       ('img2r', 'imu'),       # coordinate channels = ray tangents (u-cx)/fx,(v-cy)/fy instead of linspace
    'seq3':       ('img3', 'imu2'),       # 3 frames (a-1, a, b) derotated to a + IMU of both intervals
    'flow_raw':   ('flowraw', 'imu'),     # LK flow of the raw pair (+conf), no appearance
    'flow_derot': ('flowder', 'imu'),     # LK flow of the derotated pair (+conf)
    'flow_derot_noimu': ('flowder', None),
    'tracks_imu': ('tracks', 'imu'),      # 48 sparse derotated flow vectors (best per 16x16 cell) + IMU, MLP
}


def sample(Dd, g, variant, train, mirror=None):
    """g: anchor indices with pos>=1 and pos+1<len.  -> img (B,C,48,64) or None, pts (B,48,5) or None, vec or None, tgt (B,2,3)"""
    ik, vk = VARIANTS[variant]; dev = g.device; B = len(g); a, b = g, g + 1
    if mirror is None: mirror = torch.zeros(B, dtype=torch.bool, device=dev)
    mf = mirror.view(B, 1, 1, 1)
    img = pts = vec = None
    ca = torch.linspace(-1, 1, W0, device=dev).view(1, 1, 1, W0).expand(B, 1, H0, W0)
    cb = torch.linspace(-1, 1, H0, device=dev).view(1, 1, H0, 1).expand(B, 1, H0, W0)
    flipW = lambda x: torch.where(mf, x.flip(3), x)
    if ik is not None:
        if ik in ('img2', 'img1', 'img2r', 'raw2', 'img3'):
            X, M, (fx, fy, cx, cy) = warp_pair(Dd, a, b, derot=(ik != 'raw2'))
            if train: X = X + 0.03 * torch.randn_like(X) * torch.cat([torch.ones_like(M), M], 1)
            if ik == 'img1': X = X[:, :1]; M = torch.ones_like(M)
            if ik == 'img3':  # previous frame a-1 warped into a (sample g-1 -> pair (a-1, a)): reverse warp = warp a-1 by R
                Xp, Mp, _ = warp_pair(Dd, a, a - 1, derot=True)
                if train: Xp = Xp + 0.03 * torch.randn_like(Xp) * torch.cat([torch.ones_like(Mp), Mp], 1)
                X = torch.cat([X, Xp[:, 1:2]], 1); M = torch.cat([M, Mp], 1)
            if ik == 'img2r':
                u, v = T.pixel_grid(dev); c1 = ((u - cx) / fx)[:, None]; c2 = ((v - cy) / fy)[:, None]
            else: c1, c2 = ca, cb
            img = torch.cat([flipW(torch.cat([X, M], 1)), c1, c2], 1)
        else:
            X, M, (fx, fy, cx, cy) = warp_pair(Dd, a, b, derot=(ik != 'flowraw'))
            with torch.no_grad():
                fl, cf = lk_flow(X[:, :1], X[:, 1:2])
            fl = fl * M; cf = (cf + 2.0) / 3.0 * M
            fl = torch.where(mf, fl.flip(3) * torch.tensor([-1., 1.], device=dev).view(1, 2, 1, 1), fl)
            cf, M = flipW(cf), flipW(M)
            if ik == 'tracks':
                u, v = T.pixel_grid(dev)
                rx = ((u - cx) / fx)[:, None]; ry = ((v - cy) / fy)[:, None]
                if train: cf = cf + 0.05 * torch.randn_like(cf)
                feat = torch.cat([rx, ry, fl[:, :1] / fx[:, None] * 10, fl[:, 1:] / fy[:, None] * 10, cf], 1)  # (B,5,96,128)
                fc = feat.unfold(2, 16, 16).unfold(3, 16, 16)  # B,5,6,8,16,16
                fc = fc.reshape(B, 5, 48, 256); k = fc[:, 4].argmax(-1)  # best conf per cell
                pts = torch.gather(fc, 3, k[:, None, :, None].expand(B, 5, 48, 1))[..., 0].transpose(1, 2)  # B,48,5
            else:
                img = torch.cat([fl / 4.0, cf, M, ca, cb], 1)
        if img is not None: img = F.avg_pool2d(img, 2)
    if vk is not None:
        sg = lambda s: torch.tensor(s, device=dev).view(1, -1)
        v19 = imu_vec(Dd, a, b)
        if vk == 'imu': vec, s = v19, VEC19_SIGN
        elif vk == 'imu_nofx': vec, s = v19[:, :18], VEC19_SIGN[:18]
        elif vk == 'imu2': vec, s = torch.cat([v19, imu_vec(Dd, a - 1, a)[:, :18]], 1), VEC19_SIGN + VEC19_SIGN[:18]
        elif vk == 'orient':
            fa = Dd.f[a] / Dd.f[a].norm(dim=-1, keepdim=True).clamp(min=1e-3); fb = Dd.f[b] / Dd.f[b].norm(dim=-1, keepdim=True).clamp(min=1e-3)
            vec, s = torch.cat([fa, fb, v19[:, 15:18]], 1), SV + SV + SA
        vec = torch.where(mirror.view(B, 1), vec * sg(s), vec)
    tgt = torch.stack([Dd.vb[a], Dd.vb[b]], 1)
    tgt = torch.where(mirror.view(B, 1, 1), tgt * torch.tensor(SV, device=dev).view(1, 1, 3), tgt)
    return img, pts, vec, tgt


class AblNet(nn.Module):
    """same layout as the deployed net (4 conv s2 16,24,32,48 + BN + ReLU, fv 32, head hidden 128 -> 12) with variable inputs.
    tracks: per-point MLP (5->32->32) on 48 points, concatenated (48*32) -> linear 192."""
    def __init__(self, cin, nvec, npts=0, chs=(16, 24, 32, 48), hidden=128):
        super().__init__()
        self.cnn = None; feat = 0
        if cin:
            layers = []; c = cin
            for co in chs: layers += [nn.Conv2d(c, co, 3, 2, 1, bias=False), nn.BatchNorm2d(co), nn.ReLU(inplace=True)]; c = co
            self.cnn = nn.Sequential(*layers); feat += c * 12
        self.pm = None
        if npts:
            self.pm = nn.Sequential(nn.Linear(5, 32), nn.ReLU(), nn.Linear(32, 32), nn.ReLU()); self.pp = nn.Sequential(nn.Linear(npts * 32, 192), nn.ReLU()); feat += 192
        self.fv = nn.Sequential(nn.Linear(nvec, 32), nn.ReLU()) if nvec else None
        if nvec: feat += 32
        self.head = nn.Sequential(nn.Linear(feat, hidden), nn.ReLU(), nn.Linear(hidden, 12))
    def forward(self, img, pts, vec):
        z = []
        if self.cnn is not None: z.append(self.cnn(img).flatten(1))
        if self.pm is not None: z.append(self.pp(self.pm(pts).flatten(1)))
        if self.fv is not None: z.append(self.fv(vec))
        o = self.head(torch.cat(z, 1)).view(-1, 2, 6)
        return o[..., :3], o[..., 3:].clamp(-7, 4)


def starts3(Dd):
    return torch.nonzero((Dd.pos >= 1) & (Dd.pos + 1 < Dd.len)).squeeze(1)


def trans_dir(Dd, a, b, conf_thr=0.0):
    """geometric translation direction a->b in BODY frame b from derotated LK flow (epipolar, pure translation after derotation).
    returns t (B,3) unit (sign arbitrary), quality = lambda_min/lambda_mid (small = well determined), parallax (median |flow| px)."""
    X, M, (fx, fy, cx, cy) = warp_pair(Dd, a, b, derot=True)
    fl, cf = lk_flow(X[:, :1], X[:, 1:2])
    B = len(a); u, v = T.pixel_grid(a.device)
    x1 = torch.stack([(u - cx) / fx, (v - cy) / fy, torch.ones(B, H0, W0, device=a.device)], -1)
    x2 = torch.stack([(u + fl[:, 0] - cx) / fx, (v + fl[:, 1] - cy) / fy, torch.ones(B, H0, W0, device=a.device)], -1)
    n = torch.cross(x1, x2, dim=-1).view(B, -1, 3)
    cfv = cf.view(B, -1).masked_fill(M.view(B, -1) <= 0, -1e9)
    thr = torch.quantile(cfv.float(), 0.7, dim=1, keepdim=True)   # top 30% structure-tensor confidence per sample
    res = (_warp(X[:, 1:2], fl) - X[:, :1]).abs()
    res = F.avg_pool2d(F.pad(res, (3, 3, 3, 3), mode='replicate'), 7, 1).view(B, -1)   # local photometric residual after flow
    rthr = torch.quantile(res.masked_fill(M.view(B, -1) <= 0, 1e9), 0.5, dim=1, keepdim=True)
    w = ((cfv >= thr) & (res <= rthr) & (M.view(B, -1) > 0)).float()
    par = (fl.norm(dim=1).view(B, -1) * w).sum(1) / w.sum(1).clamp(min=1)
    t = None
    for it in range(4):
        if t is not None:
            r = (n @ t.unsqueeze(-1)).squeeze(-1); s = (r.abs() * w).sum(1, keepdim=True) / w.sum(1, keepdim=True).clamp(min=1) + 1e-6
            ww = w / (1 + (r / (2 * s)) ** 2)
        else: ww = w
        A = torch.einsum('bn,bni,bnj->bij', ww, n, n)
        ev, V = torch.linalg.eigh(A)
        t = V[:, :, 0]
    q = ev[:, 0] / ev[:, 1].clamp(min=1e-12)
    # cam(a) translation direction -> body a -> body b
    Rbc = Dd.Rbc; Rab = Dd.R[a].transpose(1, 2) @ Dd.R[b]
    tb = torch.einsum('ij,bj->bi', Rbc, t)               # body a
    tb = torch.einsum('bji,bj->bi', Rab, tb)              # body b
    return tb, q, par
