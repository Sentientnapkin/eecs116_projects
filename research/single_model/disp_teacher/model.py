"""Displacement teacher: gyro-derotated three-view metric displacement network.

Inputs (all 96x128, camera frame at t):
  img  [B,3,H,W] float in [0,1]: frame t, frame t-L/2 and frame t-L, the past frames warped into frame t's
                                  orientation by the (gyro/filter) relative rotation (rotation-only homography)
  mask [B,3,H,W] 1 where the warped pixel came from inside the source image (frame t: all ones)
  aux  [B,10] gravity unit vector in the camera frame at t (3), fx/width (1), acceleration-only displacement
              a_far = R_c(t)^T (p(t)-p(t-L) - v(t-L) tau) and a_mid (same over L/2) (IMU preintegration, invariant
              under time scaling; gives the images metric scale)
Outputs [B,12]: mean displacement over L (3), log Laplace scale (3), same for L/2 (6); camera frame at t, metres,
  d = R_c(t)^T (p(t) - p(t-L)).
Layer types are limited to conv3x3 (+folded BN) + ReLU, correlation, concat, linear: all ported to plain C.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

ENC = [(2, 32, 2), (32, 32, 1), (32, 64, 2), (64, 64, 1), (64, 96, 2), (96, 96, 1)]
RADIUS = 3
AUX = 10  # gravity (3), fx/width, accel-only displacement over L (3) and over L/2 (3), camera frame at t


def cbr(i, o, s):
    return nn.Sequential(nn.Conv2d(i, o, 3, s, 1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True))


def correlation(a, b, r=RADIUS):
    """out[:, k] = mean_c a(y,x) * b(y+dy, x+dx), k = (dy+r)*(2r+1) + (dx+r), zero outside."""
    B, C, H, W = a.shape
    bp = F.pad(b, (r, r, r, r))
    outs = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            outs.append((a * bp[:, :, r + dy:r + dy + H, r + dx:r + dx + W]).mean(1, keepdim=True))
    return torch.cat(outs, 1)


class Teacher(nn.Module):
    def __init__(self, enc=ENC, head=128, fc=256, h2=64):
        super().__init__()
        self.enc = nn.Sequential(*[cbr(i, o, s) for i, o, s in enc])
        c = enc[-1][1]
        k = (2 * RADIUS + 1) ** 2
        self.head = nn.Sequential(cbr(3 * c + 2 * k, head, 1), cbr(head, head, 2), cbr(head, h2, 1))
        self.fc1 = nn.Linear(h2 * 6 * 8 + AUX, fc)
        self.fc2 = nn.Linear(fc, fc)
        self.out = nn.Linear(fc, 12)
        with torch.no_grad():
            self.out.weight.mul_(0.1); self.out.bias.zero_()
            self.out.bias[3:6] = -1.0; self.out.bias[9:12] = -1.5

    def forward(self, img, mask, aux, feats=False):
        B = img.shape[0]
        x = torch.stack([img, mask], 2).reshape(B * 3, 2, img.shape[2], img.shape[3])  # (frame, [img,mask])
        f = self.enc(x).reshape(B, 3, -1, 12, 16)
        f0, fm, ff = f[:, 0], f[:, 1], f[:, 2]
        h = torch.cat([f0, fm, ff, correlation(f0, fm), correlation(f0, ff)], 1)
        h = self.head(h).flatten(1)
        h = F.relu(self.fc1(torch.cat([h, aux], 1)))
        h = F.relu(self.fc2(h))
        o = self.out(h)
        return (o, h) if feats else o


def warp(src, Hinv, ones=None):
    """Inverse bilinear warp, zero padding, align_corners=True pixel convention (pixel centres at integers).
    src [N,1,H,W]; Hinv [N,3,3] maps destination pixel (u,v,1) to source pixel. Returns (warped, mask)."""
    N, _, H, W = src.shape
    dev = src.device
    v, u = torch.meshgrid(torch.arange(H, device=dev, dtype=torch.float32),
                          torch.arange(W, device=dev, dtype=torch.float32), indexing="ij")
    pix = torch.stack([u, v, torch.ones_like(u)], -1).reshape(1, -1, 3)
    s = pix @ Hinv.transpose(1, 2)
    z = s[..., 2:3]
    z = torch.where(z.abs() < 1e-9, torch.full_like(z, 1e-9), z)
    xy = s[..., :2] / z
    bad = (s[..., 2] <= 0).reshape(N, H, W, 1)
    gx = xy[..., 0] / (W - 1) * 2 - 1; gy = xy[..., 1] / (H - 1) * 2 - 1
    grid = torch.stack([gx, gy], -1).reshape(N, H, W, 2)
    grid = torch.where(bad, torch.full_like(grid, -10.0), grid)
    out = F.grid_sample(src, grid, mode="bilinear", padding_mode="zeros", align_corners=True)
    if ones is None:
        ones = torch.ones_like(src)
    m = F.grid_sample(ones, grid, mode="bilinear", padding_mode="zeros", align_corners=True)
    return out, (m > 0.999).float()


STUDENT_ENC = [(2, 16, 2), (16, 16, 1), (16, 32, 2), (32, 32, 1), (32, 48, 2), (48, 48, 1)]


def student():
    return Teacher(enc=STUDENT_ENC, head=64, fc=128, h2=32)


def arch_of(state):
    """rebuild the right module from a checkpoint's state dict"""
    if "enc.5.0.weight" not in state:
        return TeacherV3() if state["enc.3.0.weight"].shape[0] == 64 else student3()
    if state["enc.5.0.weight"].shape[0] == 48:
        return student()
    return Teacher()


def student3():
    return TeacherV3(enc=[(2, 16, 2), (16, 16, 1), (16, 32, 2), (32, 32, 1)], c1=64, fc=128, h2=32)


# ---------------- v3: correlation at 1/4 resolution (24x32, radius 4 = +-16 px at 128 px width) ----------------
ENC3 = [(2, 32, 2), (32, 32, 1), (32, 64, 2), (64, 64, 1)]
R3 = 4


class TeacherV3(nn.Module):
    def __init__(self, enc=ENC3, c1=128, fc=256, h2=64):
        super().__init__()
        self.v3 = True
        self.enc = nn.Sequential(*[cbr(i, o, s) for i, o, s in enc])
        c = enc[-1][1]; k = (2 * R3 + 1) ** 2
        self.head = nn.Sequential(cbr(3 * c + 2 * k, c1, 2), cbr(c1, c1, 1), cbr(c1, c1, 2), cbr(c1, h2, 1))
        self.fc1 = nn.Linear(h2 * 6 * 8 + AUX, fc)
        self.fc2 = nn.Linear(fc, fc)
        self.out = nn.Linear(fc, 12)
        with torch.no_grad():
            self.out.weight.mul_(0.1); self.out.bias.zero_()
            self.out.bias[3:6] = -1.0; self.out.bias[9:12] = -1.5

    def forward(self, img, mask, aux, feats=False):
        B = img.shape[0]
        # per-frame brightness normalisation over valid pixels (same in C)
        s = mask.sum((2, 3), keepdim=True).clamp(min=1)
        mean = (img * mask).sum((2, 3), keepdim=True) / s
        img = (img - mean) * mask
        x = torch.stack([img, mask], 2).reshape(B * 3, 2, img.shape[2], img.shape[3])
        f = self.enc(x).reshape(B, 3, -1, 24, 32)
        f0, fm, ff = f[:, 0], f[:, 1], f[:, 2]
        h = torch.cat([f0, fm, ff, correlation(f0, fm, R3), correlation(f0, ff, R3)], 1)
        h = self.head(h).flatten(1)
        h = F.relu(self.fc1(torch.cat([h, aux], 1)))
        h = F.relu(self.fc2(h))
        o = self.out(h)
        return (o, h) if feats else o
