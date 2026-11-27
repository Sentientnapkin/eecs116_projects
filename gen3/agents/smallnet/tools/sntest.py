"""sntest.py RUN [N]: numeric check of the generated SN C block (mksn.gen) against the torch model + lv5 'lo' preprocessing.
Synthetic inputs from N val-cache anchors: 320x240 RGB built by repeating each 128x96 gray pixel (nearest 2.5x), so that the C box
gray and torch's pooled gray see the same image; the torch side recomputes gray from the same RGB. Compiles a WASI test (wasi-sdk,
-O3 -msimd128) and runs it with wasmtime (venv-viobench). Prints max |mu| difference."""
import sys, os, json, subprocess, struct, tempfile
from pathlib import Path
import numpy as np, torch, torch.nn.functional as F
sys.path.insert(0, str(Path(__file__).parent)); import mksn, lv5, lv4
run = Path(sys.argv[1]); N = int(sys.argv[2]) if len(sys.argv) > 2 else 8
c = json.load(open(run / 'result.json'))['cfg']; net = lv5.SNet(c); net.load_state_dict(torch.load(run / 'best.pt', map_location='cpu')); net.eval()
blk, info = mksn.gen(run, q16=int(os.environ.get("Q16", "0")))
W = int(c['res']); H = W * 3 // 4; FB = 320 // W
vf = sorted((lv4.A / 'cache/val').glob('*.npz'))[3]; d = np.load(vf)
fr = d['frames0']; K = d['K']; Tbc = d['Tbc']; Rbc = Tbc[:3, :3]
rng = np.random.default_rng(0); idx = rng.choice(len(fr) - 1, N, replace=False)
ui = (np.arange(320) * 128 // 320); vi = (np.arange(240) * 96 // 240)
tmp = Path(tempfile.mkdtemp(dir='/data/backups/rganapa/Sebastian/tmp/claude-1000'))
recs = []; ref = []
for i in idx:
    g0 = fr[i][vi][:, ui]; g5 = fr[i + 1][vi][:, ui]
    rgb0 = np.repeat(g0[..., None], 3, 2).astype(np.uint8); rgb5 = np.repeat(g5[..., None], 3, 2).astype(np.uint8)
    # random small rotation, intrinsics from cache (128 res -> 320)
    ang = rng.normal(0, 0.05, 3); th = np.linalg.norm(ang); kx = np.array([[0, -ang[2], ang[1]], [ang[2], 0, -ang[0]], [-ang[1], ang[0], 0]]) / th
    Rb = np.eye(3) + np.sin(th) * kx + (1 - np.cos(th)) * kx @ kx
    Rc = Rbc.T @ Rb @ Rbc
    fx320 = K[0] * 320 / 128; cx320 = (K[2] + 0.5) * 320 / 128 - 0.5; cy320 = (K[3] + 0.5) * 320 / 128 - 0.5
    vec = rng.normal(0, 0.5, 19).astype(np.float32)
    recs.append((rgb0, rgb5, Rc, fx320, cx320, cy320, vec))
    # torch reference
    def lowg(rgb): return torch.from_numpy(rgb.astype(np.float32).mean(2)).view(1, 1, 240, 320).pipe if False else F.avg_pool2d(torch.from_numpy(rgb.astype(np.float32).mean(2)).view(1, 1, 240, 320), FB)[0, 0]
    a0, a5 = lowg(rgb0), lowg(rgb5)
    s = W / 320.0; f_ = fx320 * s; cx_ = (cx320 + 0.5) * s - 0.5; cy_ = (cy320 + 0.5) * s - 0.5
    v_, u_ = torch.meshgrid(torch.arange(H, dtype=torch.float32), torch.arange(W, dtype=torch.float32), indexing='ij')
    ds = torch.stack([(u_ - cx_) / f_, (v_ - cy_) / f_, torch.ones(H, W)], -1)
    dk = torch.einsum('ji,hwj->hwi', torch.from_numpy(Rc).float(), ds); z = dk[..., 2].clamp(min=1e-3)
    uk = f_ * dk[..., 0] / z + cx_; vk = f_ * dk[..., 1] / z + cy_
    gx = (uk + 0.5) / W * 2 - 1; gy = (vk + 0.5) / H * 2 - 1
    out = F.grid_sample(a5.view(1, 1, H, W), torch.stack([gx, gy], -1)[None], mode='bilinear', padding_mode='zeros', align_corners=False)[0, 0]
    ok = ((gx.abs() <= 1) & (gy.abs() <= 1) & (dk[..., 2] > 1e-3)).float()
    X = torch.stack([a0, out]); M = ok[None]; allm = torch.cat([torch.ones(1, H, W), M])
    mean = (X * allm).sum((1, 2), keepdim=True) / allm.sum((1, 2), keepdim=True)
    var = (((X - mean) * allm) ** 2).sum((1, 2), keepdim=True) / allm.sum((1, 2), keepdim=True)
    X = (X - mean) / (var.sqrt() + 5.0) * allm
    ch = [X, M, torch.linspace(-1, 1, W).view(1, 1, W).expand(1, H, W), torch.linspace(-1, 1, H).view(1, H, 1).expand(1, H, W)]
    img = torch.cat(ch)[:int(c['cin'])][None]
    with torch.no_grad(): mu, lv = net(img, torch.from_numpy(vec)[None])
    ref.append(np.concatenate([mu[0, 1].numpy(), lv[0, 1].numpy()]))
with open(tmp / 'in.bin', 'wb') as fo:
    for rgb0, rgb5, Rc, fx320, cx320, cy320, vec in recs:
        fo.write(rgb0.tobytes()); fo.write(rgb5.tobytes()); fo.write(Rc.astype(np.float64).tobytes()); fo.write(struct.pack('3d', fx320, cx320, cy320)); fo.write(vec.tobytes())
test = ['#include <stdint.h>', '#include <stdio.h>', '#include <math.h>', '#include <string.h>', '#include <wasm_simd128.h>', blk,
        'int main(void) { FILE *f = fopen("in.bin", "rb"); FILE *g = fopen("out.bin", "wb"); static uint8_t a[230400], b[230400];',
        f'  for (int n = 0; n < {N}; n++) {{ fread(a, 1, 230400, f); fread(b, 1, 230400, f); fread(sn_Rc, 8, 9, f); fread(&sn_fx320, 8, 1, f); fread(&sn_cx320, 8, 1, f); fread(&sn_cy320, 8, 1, f); fread(sn_vec, 4, 19, f);',
        '    sn_gray(a, sn_g0); sn_gray(b, sn_g5); int k = 0; while (!sn_step(k)) k++; fwrite(sn_out, 4, 6, g); }', '  fclose(g); return 0; }']
(tmp / 't.c').write_text('\n'.join(test))
cc = '/data/backups/rganapa/Sebastian/tmp/viobench-toolchain/wasi-sdk/bin/clang'
r = subprocess.run([cc, '-O3', '-msimd128', '-o', str(tmp / 't.wasm'), str(tmp / 't.c'), '-lm'], capture_output=True, text=True)
if r.returncode: print(r.stderr[-3000:]); sys.exit(1)
code = ('import wasmtime,sys,os;os.chdir(sys.argv[1]);e=wasmtime.Engine();s=wasmtime.Store(e);c=wasmtime.WasiConfig();c.preopen_dir(".",".");s.set_wasi(c);'
        'l=wasmtime.Linker(e);l.define_wasi();m=wasmtime.Module.from_file(e,"t.wasm");i=l.instantiate(s,m)\ntry: i.exports(s)["_start"](s)\nexcept wasmtime.ExitTrap as x: pass')
r = subprocess.run(['/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python', '-c', code, str(tmp)], capture_output=True, text=True)
if r.returncode: print(r.stderr[-3000:]); sys.exit(1)
out = np.fromfile(tmp / 'out.bin', dtype=np.float32).reshape(N, 6); ref = np.array(ref)
print('steps', info['steps'], 'max |d mu| %.2e  max |d lv| %.2e  |mu| mean %.3f' % (np.abs(out[:, :3] - ref[:, :3]).max(), np.abs(out[:, 3:] - ref[:, 3:]).max(), np.abs(ref[:, :3]).mean()))
print(np.round(out[:3], 4)); print(np.round(ref[:3], 4))
