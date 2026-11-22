"""mk_gs.py: servertail/sa.c + atepush edgelets (edge_mod.c/edge_rows.c, adapted to the HM40 GOV path) + geomstarve arms
-> geomstarve/gs.c. All switches default 0: gs.c with the HM40 defines must build byte-identical to hfg_m40s1.wasm."""
from pathlib import Path
H = Path(__file__).resolve().parent
A = H.parent / 'atepush'
s = (H.parent / 'servertail' / 'sa.c').read_text()
def rep(old, new, start=0, uniq=True):
    global s
    i = s.find(old, start); assert i >= 0, old[:80]
    if uniq and not start: assert s.find(old, i + 1) < 0, ('not unique', old[:80])
    s = s[:i] + new + s[i + len(old):]
    return i
# ---- filtcons RSOFT port (FC_RMAX_ON / FC_RMAX / FC_RMAX_T0 / FC_RMAX_K; code copied from filtcons/fc.c; default off) ----
rep('static int triangulate(const Obs *o, const int *ci, double *pf) {', """#ifndef FC_RMAX_ON
#define FC_RMAX_ON 0
#endif
#ifndef FC_RMAX_T0
#define FC_RMAX_T0 0.0  /* s: RMAX check only after this time (startup clone poses are poor) */
#endif
#ifndef FC_RMAX_K
#define FC_RMAX_K 3.0
#endif
#ifndef FC_RMAX
#define FC_RMAX 1.0     /* px at solution resolution */
#endif
#if FC_RMAX_ON
/* filtcons: rms reprojection residual (normalized units) of a triangulated feature under the current clone poses */
static double fc_trirms(const Obs *o, const int *ci, const double *pf) {
    double s2 = 0;
    for (int k = 0; k < o->n; k++) {
        double Rwc[9], pwc[3], dpt[3], pc[3];
        camera_pose(&clones[ci[k]], Rwc, pwc);
        for (int i = 0; i < 3; i++) dpt[i] = pf[i] - pwc[i];
        m3tvec(Rwc, dpt, pc);
        double ex = o->x[k] - pc[0] / pc[2], ey = o->y[k] - pc[1] / pc[2]; s2 += ex * ex + ey * ey;
    }
    return sqrt(s2 / (2 * o->n));
}
#endif
static int triangulate(const Obs *o, const int *ci, double *pf) {""")
rep("    if (!triangulate(&o, ci, pf)) { tc_tri++; return 0; }\n", """    if (!triangulate(&o, ci, pf)) { tc_tri++; return 0; }
#if FC_RMAX_ON
#if FC_RMAX_ON == 2
    { /* relative: reject if residual > K x median of the last 32 features' residuals (scale adapts when the state is off) */
      static double ring[32]; static int nr; double rr_ = fc_trirms(&o, ci, pf) * fx;
      if (nr >= 16 && last_t - t_start >= FC_RMAX_T0) {
          double tmp[32]; int m_ = nr < 32 ? nr : 32; memcpy(tmp, ring, m_ * sizeof(double));
          for (int a = 1; a < m_; a++) { double v = tmp[a]; int b = a - 1; while (b >= 0 && tmp[b] > v) { tmp[b + 1] = tmp[b]; b--; } tmp[b + 1] = v; }
          double th = FC_RMAX_K * tmp[m_ / 2]; if (th < FC_RMAX) th = FC_RMAX;
          if (rr_ > th) { tc_tri++; return 0; }
      }
      ring[nr & 31] = rr_; nr++; }
#elif FC_RMAX_ON == 3
    double fc_hw = 1.0;   /* soft: rows down-weighted by FC_RMAX / residual (noise sd scaled by residual / FC_RMAX) */
    { double rr_ = fc_trirms(&o, ci, pf) * fx; if (last_t - t_start >= FC_RMAX_T0 && rr_ > FC_RMAX) fc_hw = FC_RMAX / rr_; }
#else
    if (last_t - t_start >= FC_RMAX_T0 && fc_trirms(&o, ci, pf) * fx > FC_RMAX) { tc_tri++; return 0; }
#endif   /* filtcons: absolute track-consistency check (P-independent) */
#endif
""")
rep("    if (*nrows + k0 > MAX_ROWS) return 0;\n", "#if FC_RMAX_ON == 3\n    hw *= fc_hw;\n#endif\n    if (*nrows + k0 > MAX_ROWS) return 0;\n")
OBS = 'typedef struct { int n; int cid[MAX_OBS]; double x[MAX_OBS], y[MAX_OBS]; int tid; double px, py; } Obs;'
rep(OBS, '#ifndef EDGE\n#define EDGE 0   /* atepush/geomstarve: edgelet (point-on-line) MSCKF features in vision-starved scenes */\n#endif\n#ifndef EDGE_DBG\n#define EDGE_DBG 0\n#endif\n#ifndef GS_DIAG\n#define GS_DIAG 0\n#endif\n'
    '#if EDGE\ntypedef struct { int n; int cid[MAX_OBS]; double x[MAX_OBS], y[MAX_OBS]; int tid; double px, py; float enx[MAX_OBS], eny[MAX_OBS], ehl[MAX_OBS]; int edge; } Obs;\n#else\n' + OBS + '\n#endif')
FR = 'static int feature_rows(const Obs *o_in, int *nrows) {'
mod = (H / 'edge_mod.c').read_text() if (H / 'edge_mod.c').exists() else (A / 'edge_mod.c').read_text()
rows = (H / 'edge_rows.c').read_text() if (H / 'edge_rows.c').exists() else (A / 'edge_rows.c').read_text()
rows += '#ifndef EDGE_LINE\n#define EDGE_LINE 0\n#endif\n' + (H / 'line_mod.c').read_text()
rep(FR, '#if EDGE\n' + mod + rows + '#endif\n' + FR + '\n#if EDGE\n#if EDGE_LINE\n    if (o_in->edge == 2) return line_rows(o_in, nrows);\n#endif\n    if (o_in->edge) return edge_rows(o_in, nrows);\n#endif')

# GOV (HM40) path vision
g0 = s.find('static int gov_take(Obs *o, int *rw, int cap)')
rep('        gov_klt_cnt = 0;\n        track_all(prev, cur, Rwc_now);\n        gov_used += gov_klt_cnt * GC_KLT;\n',
    '        gov_klt_cnt = 0;\n        track_all(prev, cur, Rwc_now);\n        gov_used += gov_klt_cnt * GC_KLT;\n#if EDGE\n        if (edge_on()) { double Rr[9]; m3tmul(Rwc_now, Rwc_prev, Rr); edge_track_all(cur, Rr); gov_used += edge_alive() * GC_EDGE; }\n#endif\n', start=g0)
rep('            add_clone(); record_observations(); vision_zupt(); cloned = 1;\n',
    '            add_clone(); record_observations();\n#if EDGE\n            edge_record();\n#endif\n            vision_zupt(); cloned = 1;\n', start=g0)
rep('        if (nb) { cur_rw = rw; msckf_update(batch, nb); gov_used += GC_BATCH + rw * GC_ROW; }\n        remove_oldest_clone();\n',
    '#if EDGE\n        nb = edge_take_b(batch, nb, 1, &rw, cap);\n#endif\n        if (nb) { cur_rw = rw; msckf_update(batch, nb); gov_used += GC_BATCH + rw * GC_ROW; }\n        remove_oldest_clone();\n#if EDGE\n        edge_drop_clone(oldest);\n#endif\n', start=g0)
rep('        }\n        if (nb) { cur_rw = rw; msckf_update(batch, nb); gov_used += GC_BATCH + rw * GC_ROW; }\n    }\n    tc_rows = rw; gov_nb = nb;\n',
    '        }\n#if EDGE\n        if (EDGE_GSPREAD) { if (!cloned) { const int fpc = GOV_VIS * clone_every, nin = fpc - 1 > 0 ? fpc - 1 : 1; int ph = GOV_VIS * frames_since_clone - 1; if (ph < 0) ph = 0; nb = edge_take_phb(batch, nb, ph % nin, nin, &rw, cap); } }\n        else if (cloned) nb = edge_take_b(batch, nb, 0, &rw, cap);\n#endif\n        if (nb) { cur_rw = rw; msckf_update(batch, nb); gov_used += GC_BATCH + rw * GC_ROW; }\n    }\n    tc_rows = rw; gov_nb = nb;\n', start=g0)
rep('        detect(cur);\n        gov_used += gov_ncell * GC_CELL;\n        cur_pyr = cur;\n',
    '        detect(cur);\n        gov_used += gov_ncell * GC_CELL;\n#if EDGE\n        if ((cloned || EDGE_DEVERY) && edge_on() && GOV_B - gov_used > EDGE_GCDET) { edge_detect(cur); gov_used += EDGE_GCDET; }\n#endif\n'
    '#if GS_DIAG\n        gs_diag(cur, cloned);\n#endif\n        cur_pyr = cur;\n', start=g0)

# reset: init + HARDEN recovery
rep('memset(tracks, 0, sizeof tracks); memset(det_until, 0, sizeof det_until);\n', 'memset(tracks, 0, sizeof tracks); memset(det_until, 0, sizeof det_until);\n#if EDGE\n        edge_reset();\n#endif\n')
rep('    for (int i = 0; i < MAX_TRACKS; i++) { tracks[i].alive = 0; tracks[i].obs.n = 0; }\n    lc_active = 0;',
    '    for (int i = 0; i < MAX_TRACKS; i++) { tracks[i].alive = 0; tracks[i].obs.n = 0; }\n#if EDGE\n    edge_reset();\n#endif\n    lc_active = 0;')

# GS_DIAG: per vision frame image statistics (diagnostics builds only)
DIAG = r'''
#if GS_DIAG
static void gs_diag(int cur, int cloned) {
    const uint8_t *I = pyr[cur][0];
    long sum = 0; int black = 0, gx8 = 0, gx20 = 0;
    for (int y = 1; y < IMG_H - 1; y += 2)
        for (int x = 1; x < IMG_W - 1; x += 2) {
            const uint8_t *p = I + y * IMG_W + x; int v = p[0]; sum += v; black += v < 4;
            int g = abs(p[1] - p[-1]) + abs(p[IMG_W] - p[-IMG_W]); gx8 += g >= 8; gx20 += g >= 20;
        }
    int n = ((IMG_H - 2 + 1) / 2) * ((IMG_W - 2 + 1) / 2), live = 0, lo = 0;
    for (int i = 0; i < MAX_TRACKS; i++) { live += tracks[i].alive; lo += tracks[i].alive && tracks[i].obs.n >= MIN_OBS; }
    int ne = 0;
#if EDGE
    ne = edge_alive();
#if EDGE_LINE
    fprintf(stderr, "L f=%d spawn=%ld kcol=%ld att=%ld tri=%ld rmax=%ld gate=%ld ok=%ld rows=%ld vert=%ld horiz=%ld myaw=%ld fixed=%d phi0=%.2f\n", frame_no, l_spawn, l_kcol, l_att, l_tri, l_rmax, l_gate, l_ok, l_rows, l_vert, l_horiz, l_myaw, my_fixed, my_phi0 * 57.29578);
#endif
    fprintf(stderr, "K f=%d %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld sp=%ld rows=%ld er=%ld,%ld,%ld,%ld,%ld\n", frame_no, ek[0], ek[1], ek[2], ek[3], ek[4], ek[5], ek[6], ek[7], ek[8], ek[9], e_spawn, e_rows, er_att, er_tri, er_rmax, er_gate, er_ok);
#endif
    fprintf(stderr, "G f=%d live=%d lo=%d mean=%.1f black=%.3f g8=%.4f g20=%.4f edges=%d rows=%d used=%d cl=%d\n", frame_no, live, lo, (double)sum / n, (double)black / n,
            (double)gx8 / n, (double)gx20 / n, ne, tc_rows, (int)(gov_used / 1000), cloned);
}
#endif
'''
rep('static int gov_take(Obs *o, int *rw, int cap)', DIAG + 'static int gov_take(Obs *o, int *rw, int cap)')
rep('#define CLONE_EVERY 4          /* frames between clones */\n', '#ifndef CLONE_EVERY\n#define CLONE_EVERY 4          /* frames between clones */\n#endif\n')
rep('#define MAX_OBS 8\n', '#ifndef MAX_OBS\n#define MAX_OBS 8\n#endif\n')
# GS_FBS: looser forward-backward check while starved (live tracks < GS_FBLIVE at frame start)
rep("""static void track_all(int prev, int cur, const double *Rwc_now) {
    double Rrel[9];
    m3tmul(Rwc_now, Rwc_prev, Rrel); /* previous camera -> current camera */
""", """#ifndef GS_FBS
#define GS_FBS 0
#endif
#ifndef GS_FBLIVE
#define GS_FBLIVE 20
#endif
#ifndef GS_FBTHR
#define GS_FBTHR 1.0     /* px^2 */
#endif
static void track_all(int prev, int cur, const double *Rwc_now) {
    double Rrel[9];
    m3tmul(Rwc_now, Rwc_prev, Rrel); /* previous camera -> current camera */
#if GS_FBS
    double fbthr = 0.25; { int lv = 0; for (int i = 0; i < MAX_TRACKS; i++) lv += tracks[i].alive; if (lv < GS_FBLIVE) fbthr = GS_FBTHR; }
#else
    const double fbthr = 0.25;
#endif
""")
rep("(bx - t->x) * (bx - t->x) + (by - t->y) * (by - t->y) > 0.25) { ok = 0; ST(st_fbrej++); }", "(bx - t->x) * (bx - t->x) + (by - t->y) * (by - t->y) > fbthr) { ok = 0; ST(st_fbrej++); }")
(H / 'gs.c').write_text(s)
print('ok', len(s))
