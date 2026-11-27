"""mkgsn.py RUN OUT.c [--base SRC] [--stepf F]: GSLV source with the smallnet (SN) net spliced in behind -DSN=1 (default 0 = base
behaviour, byte-identical wasm). Base default: src/v2_727.c (= netv2 gslv_v2.c + auto_727 weights; F flags -> 9a468ce9 VERIFIED).
With SN=1 the NET_SLICE path uses the SN net: low-res box gray of frame 0 / frame K computed at stash time (instead of the 230 KB RGB memcpy;
charged SN_GCG), then SN_STEPS micro-steps (prep, norm, convs, head) each charged GC_UNIT by the governor."""
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); import mksn
ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('out')
ap.add_argument('--base', default='/data/backups/rganapa/Sebastian/gen3/agents/smallnet/src/v2_727.c'); ap.add_argument('--stepf', type=float, default=120e3); ap.add_argument('--q16', type=int, default=1)
a = ap.parse_args()
blk, info = mksn.gen(a.run, a.stepf, q16=a.q16)
import subprocess, re as _re
_o = subprocess.run([sys.executable, '-B', str(Path(__file__).parent / 'snbench.py'), a.run, '--q16', str(a.q16), '--stepf', str(a.stepf)], capture_output=True, text=True).stdout
_costs = [int(x) * 1000 for x in _re.search(r'per step \[([^\]]*)\]', _o).group(1).split(',')]
_gray = int(_re.search(r'gray (\d+)k', _o).group(1)) * 1000
assert len(_costs) == info['steps']
blk += 'static const double sn_costtab[%d] = {%s};\n' % (len(_costs), ', '.join(map(str, _costs)))
s = Path(a.base).read_text()
def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (old, s.count(old)); s = s.replace(old, new)
glue = r'''
#ifndef SN
#define SN 0
#endif
#if SN
#ifndef SN_GCG
#define SN_GCG @GCG@   /* governor charge for one low-res gray (frame 0 / frame K): snbench x 1.1 */
#endif
''' + blk + r'''
static void lc_apply(void);
static int sn_do(int k) {
    if (k == 0) {
        if (!ns_have5) return 0;
        double Rb[9], T_[9];
        for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) { double a = 0; for (int q = 0; q < 3; q++) a += lc_Rs[3 * q + i] * lc_R5[3 * q + j]; Rb[3 * i + j] = a; }
        m3tmul(R_bc, Rb, T_); m3mul(T_, R_bc, sn_Rc);
        sn_fx320 = fx; sn_cx320 = cx; sn_cy320 = cy;
        for (int i = 0; i < 3; i++) {
            sn_vec[i] = (float)(lc_fm[0][i] / 9.81); sn_vec[3 + i] = (float)lc_gm[0][i];
            sn_vec[6 + i] = (float)(lc_fm[1][i] / 9.81); sn_vec[9 + i] = (float)lc_gm[1][i];
            double dv = lc_Rs[i] * (lc_V5[0] - lc_Vs[0]) + lc_Rs[3 + i] * (lc_V5[1] - lc_Vs[1]) + lc_Rs[6 + i] * (lc_V5[2] - lc_Vs[2]);
            sn_vec[12 + i] = (float)(dv / (0.05 * 5 * 1 * 1 * 9.81));
        }
        double tr = (Rb[0] + Rb[4] + Rb[8] - 1) / 2;
        tr = tr < -1 + 1e-6 ? -1 + 1e-6 : tr > 1 - 1e-6 ? 1 - 1e-6 : tr;
        double th = acos(tr), w[3] = {Rb[7] - Rb[5], Rb[2] - Rb[6], Rb[3] - Rb[1]}, kk = th / (2 * sin(th) + 1e-6);
        for (int i = 0; i < 3; i++) sn_vec[15 + i] = (float)(w[i] * kk);
        sn_vec[18] = (float)(fx / 100.0);
    }
    if (sn_step(k)) {
        for (int i = 0; i < 6; i++) lc_out[6 + i] = sn_out[i];
#ifdef SN_DEBUG
        fprintf(stderr, "SN out %.4f %.4f %.4f %.3f %.3f %.3f\n", sn_out[0], sn_out[1], sn_out[2], sn_out[3], sn_out[4], sn_out[5]);
#endif
        lc_apply(); lc_next = 6;
    }
    return 1;
}
#endif
'''
glue = glue.replace('@GCG@', '%.0f' % (_gray * 1.1))
rep('static int ns_do(int k) {\n', glue + 'static int ns_do(int k) {\n#if SN\n    return sn_do(k);\n#endif\n')
rep('static double ns_cost(int k) { /* measured fuel per micro-step (tools/prof.py, max over 6 v3val flights x 400 frames) */\n',
    'static double ns_cost(int k) { /* measured fuel per micro-step (tools/prof.py, max over 6 v3val flights x 400 frames) */\n#if SN\n    return sn_costtab[k];\n#endif\n')
rep('#if NS_GEN\n#define NS_STEPS (62 + NS_K0 + NS_K1 + NS_K2 + NS_K3 + NS_KH)\n#else\n#define NS_STEPS 97\n#endif',
    '#if SN\n#define NS_STEPS SN_STEPS\n#elif NS_GEN\n#define NS_STEPS (62 + NS_K0 + NS_K1 + NS_K2 + NS_K3 + NS_KH)\n#else\n#define NS_STEPS 97\n#endif')
rep('    if (lc_active) { memcpy(ns_rgb0, frame, sizeof ns_rgb0); gov_used += GC_STASH; }',
    '#if SN\n    if (lc_active) { sn_gray(frame, sn_g0); gov_used += SN_GCG; }\n#else\n    if (lc_active) { memcpy(ns_rgb0, frame, sizeof ns_rgb0); gov_used += GC_STASH; }\n#endif')
rep('            memcpy(ns_rgb5, frame, sizeof ns_rgb5); ns_have5 = 1; gov_used += GC_STASH;',
    '#if SN\n            sn_gray(frame, sn_g5); ns_have5 = 1; gov_used += SN_GCG;\n#else\n            memcpy(ns_rgb5, frame, sizeof ns_rgb5); ns_have5 = 1; gov_used += GC_STASH;\n#endif')
Path(a.out).write_text(s); print('wrote', a.out, 'SN steps', info['steps'], [x[0] for x in info['sched']])
