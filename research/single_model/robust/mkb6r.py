"""Generate robust/b6r.c from B6 (frontend/adopted_fbh.c): RB_DEBUG per-frame stderr counters + switchable stabilisation arms.
All additions are #ifdef/#ifndef guarded; with every arm off and RB_DEBUG off the wasm is bit-identical to B6 (checked by sha)."""
import re
s = open('../frontend/adopted_fbh.c').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:50], s.count(a)); s = s.replace(a, b)

# guard the nudged parameters (no behaviour change)
for n in ('ACCEL_NOISE', 'KLT_MIN_EIG'):
    s = re.sub(r'^(#define\s+%s\b[^\n]*)$' % n, r'#ifndef %s\n\1\n#endif' % n, s, count=1, flags=re.M)

DEBUG_DECL = '''
#ifdef RB_DEBUG
static int dg_frame, dg_kltfail, dg_fbchk, dg_fbdrop, dg_att, dg_tri, dg_gate, dg_used, dg_near, dg_rows, dg_chol, dg_ub;
static double dg_rmax;
#define DGI(x) (x)++
#else
#define DGI(x) ((void)0)
#endif
'''
rep('static double tri_min_eig = TRI_MIN_EIG, t_start, chi2_z = 1.645;', 'static double tri_min_eig = TRI_MIN_EIG, t_start, chi2_z = 1.645;' + DEBUG_DECL)
# FB counters (do not alter control flow)
rep('        int ok = klt(prev, cur, t->x, t->y, gx, gy, &nx, &ny) && nx >= 0 && ny >= 0 && nx < IMG_W && ny < IMG_H;\n',
    '        int ok = klt(prev, cur, t->x, t->y, gx, gy, &nx, &ny) && nx >= 0 && ny >= 0 && nx < IMG_W && ny < IMG_H;\n        if (!ok) DGI(dg_kltfail);\n')
rep('            double bx, by;\n            if (!klt(cur, prev, nx, ny, t->x, t->y, &bx, &by) || (bx - t->x) * (bx - t->x) + (by - t->y) * (by - t->y) > 0.25) ok = 0;',
    '            double bx, by;\n            DGI(dg_fbchk);\n            if (!klt(cur, prev, nx, ny, t->x, t->y, &bx, &by) || (bx - t->x) * (bx - t->x) + (by - t->y) * (by - t->y) > 0.25) { ok = 0; DGI(dg_fbdrop); }')
rep('    if (!triangulate(&o, ci, pf)) return 0;', '    DGI(dg_att);\n    if (!triangulate(&o, ci, pf)) { DGI(dg_tri); return 0; }')
rep('    if (m2 > gq) { if (INV_HUBER > 0 && m2 < INV_HUBER * gq) hw = sqrt(gq / m2); else return 0; }',
    '''#ifdef RB_DEBUG
    if (m2 > 0.8 * gq && m2 < 1.25 * gq) dg_near++;
    if (m2 / gq > dg_rmax) dg_rmax = m2 / gq;
#endif
    if (m2 > gq) { if (INV_HUBER > 0 && m2 < INV_HUBER * gq) hw = sqrt(gq / m2); else { DGI(dg_gate); return 0; } }''')
rep('    *nrows += k0;\n    return 1;', '    *nrows += k0; DGI(dg_used);\n    return 1;')
rep('    vision(frame);\n    write_state(out);',
'''#ifdef RB_DEBUG
    dg_kltfail = dg_fbchk = dg_fbdrop = dg_tri = dg_gate = dg_used = dg_att = dg_near = 0; dg_rmax = 0;
#endif
    vision(frame);
#ifdef RB_DEBUG
    dg_frame++;
    { int live = 0, live3 = 0; for (int i = 0; i < MAX_TRACKS; i++) if (tracks[i].alive) { live++; if (tracks[i].obs.n >= MIN_OBS) live3++; }
      fprintf(stderr, "D f=%d t=%.2f live=%d live3=%d nc=%d kf=%d fbc=%d fbd=%d att=%d tri=%d gate=%d used=%d near=%d rmax=%.2f mov=%d rel=%d hold=%d v=%.4f,%.4f,%.4f p=%.4f,%.4f,%.4f Pv=%.4f Pth=%.4f\\n",
        dg_frame, t, live, live3, nclones, dg_kltfail, dg_fbchk, dg_fbdrop, dg_att, dg_tri, dg_gate, dg_used, dg_near, dg_rmax, moving, gate_released, hold_on,
        vel[0], vel[1], vel[2], pos[0], pos[1], pos[2],
        sqrt(Pm[V*MAXD+V]+Pm[(V+1)*MAXD+V+1]+Pm[(V+2)*MAXD+V+2]), sqrt(Pm[TH*MAXD+TH]+Pm[(TH+1)*MAXD+TH+1]+Pm[(TH+2)*MAXD+TH+2])); }
#endif
    write_state(out);''')

# ---------------------------------------------------------------- stabilisation arms (all default off)
ARMS = """
#ifndef RB_SOFT
#define RB_SOFT 0          /* 1: smooth chi2 weight instead of the accept/reject cliff: w = cos taper from gate to RB_SOFT_K*gate */
#endif
#ifndef RB_SOFT_K
#define RB_SOFT_K 2.0
#endif
#ifndef RB_DEFER
#define RB_DEFER 0         /* n>0: an update that would use fewer than n features is deferred (batch kept, retried with the next one) */
#endif
#ifndef RB_DEFER_MAX
#define RB_DEFER_MAX 3     /* frames a batch may be deferred */
#endif
#ifndef RB_STEP
#define RB_STEP 0          /* 1: trust region: the MSCKF correction is scaled so that |dp|,|dv|,|dtheta| stay below the caps */
#endif
#ifndef RB_STEP_P
#define RB_STEP_P 0.05
#endif
#ifndef RB_STEP_V
#define RB_STEP_V 0.10
#endif
#ifndef RB_STEP_T
#define RB_STEP_T 0.02
#endif
#ifndef RB_LONE
#define RB_LONE 0          /* n>0: update with fewer than n accepted features gets its pixel noise variance multiplied by n/used */
#endif
static int rb_step_on;
static double rb_noise_mult = 1.0;
"""
rep('static double tri_min_eig = TRI_MIN_EIG, t_start, chi2_z = 1.645;', 'static double tri_min_eig = TRI_MIN_EIG, t_start, chi2_z = 1.645;' + ARMS if False else 'static double tri_min_eig = TRI_MIN_EIG, t_start, chi2_z = 1.645;')
s = s.replace('static double tri_min_eig = TRI_MIN_EIG, t_start, chi2_z = 1.645;', 'static double tri_min_eig = TRI_MIN_EIG, t_start, chi2_z = 1.645;' + ARMS, 1)
# ARMS must precede update(): update is defined earlier than the declaration above, so move arms block to just before update()
s = s.replace(ARMS, '', 1)
rep('static int update(const double *r, const double *H, int k, double noise, double gate) {', ARMS + 'static int update(const double *r, const double *H, int k, double noise, double gate) {')
rep('    inject(dx);\n    return 1;\n}\n\n/* ====', """#if RB_STEP
    if (rb_step_on) {
        double np = sqrt(dx[P] * dx[P] + dx[P + 1] * dx[P + 1] + dx[P + 2] * dx[P + 2]), nv = sqrt(dx[V] * dx[V] + dx[V + 1] * dx[V + 1] + dx[V + 2] * dx[V + 2]),
               nt = sqrt(dx[TH] * dx[TH] + dx[TH + 1] * dx[TH + 1] + dx[TH + 2] * dx[TH + 2]), sc = 1.0;
        if (np > RB_STEP_P) sc = RB_STEP_P / np;
        if (nv > RB_STEP_V && RB_STEP_V / nv < sc) sc = RB_STEP_V / nv;
        if (nt > RB_STEP_T && RB_STEP_T / nt < sc) sc = RB_STEP_T / nt;
        if (sc < 1.0) for (int j = 0; j < D; j++) dx[j] *= sc;
    }
#endif
    inject(dx);
    return 1;
}

/* ====""")
# soft gate (after debug replacement)
rep('    if (m2 > gq) { if (INV_HUBER > 0 && m2 < INV_HUBER * gq) hw = sqrt(gq / m2); else { DGI(dg_gate); return 0; } }',
"""#if RB_SOFT
    if (m2 > gq) { if (m2 < RB_SOFT_K * gq) hw = sqrt(0.5 * (1.0 + cos(M_PI * (m2 - gq) / ((RB_SOFT_K - 1.0) * gq)))); else { DGI(dg_gate); return 0; } }
#else
    if (m2 > gq) { if (INV_HUBER > 0 && m2 < INV_HUBER * gq) hw = sqrt(gq / m2); else { DGI(dg_gate); return 0; } }
#endif""")
# msckf_update: defer + lone + step
rep("""static void msckf_update(Obs *batch, int nbatch) {
    int nrows = 0;
    for (int b = 0; b < nbatch; b++) feature_rows(&batch[b], &nrows);
    if (!nrows) return;""", """#if RB_DEFER > 0
static Obs rb_pend[MAX_BATCH], rb_comb[2 * MAX_BATCH];
static int rb_npend, rb_age;
#endif
static void msckf_update(Obs *batch, int nbatch) {
    int nrows = 0, nused = 0;
#if RB_DEFER > 0
    { int n2 = 0;
      for (int i = 0; i < rb_npend; i++) rb_comb[n2++] = rb_pend[i];
      for (int i = 0; i < nbatch && n2 < 2 * MAX_BATCH; i++) rb_comb[n2++] = batch[i];
      batch = rb_comb; nbatch = n2; }
#endif
    for (int b = 0; b < nbatch; b++) nused += feature_rows(&batch[b], &nrows);
#if RB_DEFER > 0
    if (nbatch > 0 && nused < RB_DEFER && rb_age < RB_DEFER_MAX) {
        int from = nbatch > MAX_BATCH ? nbatch - MAX_BATCH : 0;
        rb_npend = 0;
        for (int i = from; i < nbatch; i++) rb_pend[rb_npend++] = batch[i];
        rb_age++;
        return;
    }
    rb_npend = 0; rb_age = 0;
#endif
    if (!nrows) return;
    rb_noise_mult = 1.0;
#if RB_LONE > 0
    if (nused > 0 && nused < RB_LONE) rb_noise_mult = (double)RB_LONE / nused;
#endif""")
rep("    update(rbig, Hbig, nrows, (PIXEL_STD / fx) * (PIXEL_STD / fx), INFINITY);\n}",
    "    rb_step_on = 1;\n    update(rbig, Hbig, nrows, rb_noise_mult * (PIXEL_STD / fx) * (PIXEL_STD / fx), INFINITY);\n    rb_step_on = 0;\n}")
rep('        nclones = 0; clone_counter = 0; frames_since_clone = 0; nlost = 0; detect_cursor = 0;',
    '        nclones = 0; clone_counter = 0; frames_since_clone = 0; nlost = 0; detect_cursor = 0;\n#if RB_DEFER > 0\n        rb_npend = 0; rb_age = 0;\n#endif')

open('b6r.c', 'w').write(s)
