import re
src = open('../final/fgt.c').read()
def rep(old, new, cnt=1):
    global src
    assert src.count(old) == cnt, (old, src.count(old))
    src = src.replace(old, new)

# --- parameter wrappers
rep('#define LEVELS 2 ', '#ifndef LEVELS\n#define LEVELS 2\n#endif\n#define LEVELS_UNUSED 2 ')
rep('#define KLT_R 4 ', '#ifndef KLT_R\n#define KLT_R 4\n#endif\n#define KLT_R_UNUSED 4 ')
rep('#define GRID_X 10 ', '#ifndef GRID_X\n#define GRID_X 10\n#endif\n#define GRID_X_UNUSED 10 ')
rep('#define GRID_Y 6\n', '#ifndef GRID_Y\n#define GRID_Y 6\n#endif\n')
rep('#include <string.h>\n', '''#include <string.h>
#include <stdio.h>
#ifndef FE_NORM
#define FE_NORM 0          /* contrast normalisation of the gray frame before the pyramid (EMA mean/std) */
#endif
#ifndef FE_NORM_TARGET
#define FE_NORM_TARGET 45.0
#endif
#ifndef FE_NORM_KMAX
#define FE_NORM_KMAX 4.0
#endif
#ifndef FE_FB
#define FE_FB 0            /* forward-backward KLT check */
#endif
#ifndef FE_FB_PX
#define FE_FB_PX 0.5
#endif
#ifndef FE_RS
#define FE_RS 0            /* gyro-aided 2-point translation-direction RANSAC at clone frames */
#endif
#ifndef FE_RS_ITERS
#define FE_RS_ITERS 40
#endif
#ifndef FE_RS_THR
#define FE_RS_THR 1.0      /* px: inlier (consensus) threshold */
#endif
#ifndef FE_RS_OUT
#define FE_RS_OUT 3.0      /* px: a track farther than this from the best epipolar plane is killed */
#endif
#ifndef FE_RS_MINPX
#define FE_RS_MINPX 1.0    /* px de-rotated disparity needed for a track to be used as a sample */
#endif
#ifndef FE_RS_MINN
#define FE_RS_MINN 10      /* min number of sample-eligible tracks */
#endif
#ifndef FE_RADW
#define FE_RADW 0.0        /* observation weight 1 / (1 + k r^2), r = normalised image radius */
#endif
#ifndef FE_RMAX
#define FE_RMAX 0.0        /* >0: no detection where normalised radius exceeds this */
#endif
#ifndef FE_CELLFALL
#define FE_CELLFALL 0      /* accept weaker corners (score >= FE_FALL x threshold) while few tracks are alive */
#endif
#ifndef FE_FALL
#define FE_FALL 0.4
#endif
#ifndef FE_FALL_N
#define FE_FALL_N 25
#endif
#ifndef FE_DEBUG
#define FE_DEBUG 0
#endif
''')

# --- normalisation
rep('''    for (int i = 0; i < IMG_W * IMG_H; i++) g[i] = (uint8_t)((77 * rgb[3 * i] + 150 * rgb[3 * i + 1] + 29 * rgb[3 * i + 2] + 128) >> 8);
''', '''    for (int i = 0; i < IMG_W * IMG_H; i++) g[i] = (uint8_t)((77 * rgb[3 * i] + 150 * rgb[3 * i + 1] + 29 * rgb[3 * i + 2] + 128) >> 8);
    if (FE_NORM) {
        static double ema_m, ema_s; static int have;
        double sm = 0, ss = 0; int cnt = 0;
        for (int i = 0; i < IMG_W * IMG_H; i += 5) { sm += g[i]; ss += (double)g[i] * g[i]; cnt++; }
        sm /= cnt; ss = sqrt(fmax(ss / cnt - sm * sm, 1.0));
        if (!have || g_have == 0) { ema_m = sm; ema_s = ss; have = 1; } else { ema_m += 0.05 * (sm - ema_m); ema_s += 0.05 * (ss - ema_s); }
        double k = FE_NORM_TARGET / ema_s; if (k < 1) k = 1; if (k > FE_NORM_KMAX) k = FE_NORM_KMAX;
        if (k > 1.05) {
            for (int i = 0; i < IMG_W * IMG_H; i++) { double v = (g[i] - ema_m) * k + 128.0; g[i] = (uint8_t)(v < 0 ? 0 : v > 255 ? 255 : v + 0.5); }
        }
    }
''')

# --- forward-backward
rep('''        if (klt(prev, cur, t->x, t->y, gx, gy, &nx, &ny) && nx >= 0 && ny >= 0 && nx < IMG_W && ny < IMG_H) {
            t->x = nx; t->y = ny;''', '''        int ok = klt(prev, cur, t->x, t->y, gx, gy, &nx, &ny) && nx >= 0 && ny >= 0 && nx < IMG_W && ny < IMG_H;
        if (FE_FB && ok) {
            double bx, by;
            if (!klt(cur, prev, nx, ny, t->x, t->y, &bx, &by) || (bx - t->x) * (bx - t->x) + (by - t->y) * (by - t->y) > FE_FB_PX * FE_FB_PX) { ok = 0; fe_fb_kill++; }
        }
        if (ok) {
            t->x = nx; t->y = ny;''')
rep('static void track_all(int prev', 'static int fe_fb_kill, fe_rs_kill, fe_rs_run, fe_rs_skip;\nstatic void track_all(int prev')

# --- radius detection limit + cell fallback
rep('''        double best = DETECT_MIN_SCORE * (TAILS_DET ? tex_scale : 1.0);
        int bx = -1, by = -1;''', '''        double thr0 = DETECT_MIN_SCORE * (TAILS_DET ? tex_scale : 1.0);
        double best = FE_CELLFALL ? FE_FALL * thr0 : thr0;
        int bx = -1, by = -1;''')
rep('''                if (x < BORDER || x >= IMG_W - BORDER) continue;
                double s = corner_score(I, x, y);''', '''                if (x < BORDER || x >= IMG_W - BORDER) continue;
                if (FE_RMAX > 0) { double ax = (x - cx) / fx, ay = (y - cy) / fy; if (ax * ax + ay * ay > FE_RMAX * FE_RMAX) continue; }
                double s = corner_score(I, x, y);''')
rep('''        if (bx >= 0) {
            Track *t = &tracks[free_slot[--nfree]];''', '''        if (bx >= 0 && FE_CELLFALL && best < thr0) { /* weak corner: only while the grid is starved */
            int nl = 0; for (int i = 0; i < MAX_TRACKS; i++) nl += tracks[i].alive;
            if (nl >= FE_FALL_N) bx = -1;
        }
        if (bx >= 0) {
            Track *t = &tracks[free_slot[--nfree]];''')

# --- radius weighting
rep('''        rr[2 * k + 1] = o.y[k] - pc[1] * iz;
''', '''        rr[2 * k + 1] = o.y[k] - pc[1] * iz;
        wobs[k] = FE_RADW > 0 ? 1.0 / (1.0 + FE_RADW * (o.x[k] * o.x[k] + o.y[k] * o.y[k])) : 1.0;
''')
rep('static int feature_rows(const Obs *o_in, int *nrows) {', 'static double wobs[MAX_OBS];\nstatic int feature_rows(const Obs *o_in, int *nrows) {')
rep('''    for (int c = 0; c < 3; c++) { /* left null space of Hf */''', '''    if (FE_RADW > 0)
        for (int k = 0; k < o.n; k++)
            for (int r2 = 0; r2 < 2; r2++) {
                double w = wobs[k]; int row = 2 * k + r2;
                for (int j = 0; j < D; j++) Hx[row * MAXD + j] *= w;
                for (int j = 0; j < 3; j++) Hf[row * 3 + j] *= w;
                rr[row] *= w;
            }
    for (int c = 0; c < 3; c++) { /* left null space of Hf */''')

# --- RANSAC
rep('static void record_observations(void) {', '''static void ransac_filter(void) {
    if (!FE_RS) return;
    int idx[MAX_TRACKS], na = 0, elig[MAX_TRACKS], ne = 0;
    static double f1[MAX_TRACKS][3], f2[MAX_TRACKS][3], nn[MAX_TRACKS][3], disp[MAX_TRACKS];
    int cur_ci = nclones - 1;
    double Rc2[9];
    m3mul(clones[cur_ci].R, R_bc, Rc2);
    for (int i = 0; i < MAX_TRACKS; i++) {
        Track *t = &tracks[i];
        if (!t->alive || t->obs.n < 2) continue;
        int c1 = clone_index(t->obs.cid[0]);
        if (c1 < 0 || c1 == cur_ci) continue;
        double Rc1[9], Rrel[9], r2[3], a[3] = {t->obs.x[0], t->obs.y[0], 1.0}, b[3] = {t->obs.x[t->obs.n - 1], t->obs.y[t->obs.n - 1], 1.0};
        m3mul(clones[c1].R, R_bc, Rc1);
        m3tmul(Rc1, Rc2, Rrel); /* cam2 -> cam1 */
        m3vec(Rrel, b, r2);
        if (r2[2] < 1e-3) continue;
        f1[na][0] = a[0]; f1[na][1] = a[1]; f1[na][2] = 1.0;
        f2[na][0] = r2[0] / r2[2]; f2[na][1] = r2[1] / r2[2]; f2[na][2] = 1.0;
        nn[na][0] = f1[na][1] * f2[na][2] - f1[na][2] * f2[na][1];
        nn[na][1] = f1[na][2] * f2[na][0] - f1[na][0] * f2[na][2];
        nn[na][2] = f1[na][0] * f2[na][1] - f1[na][1] * f2[na][0];
        double dx = f2[na][0] - f1[na][0], dy = f2[na][1] - f1[na][1];
        disp[na] = sqrt(dx * dx + dy * dy) * fx;
        idx[na] = i;
        if (disp[na] >= FE_RS_MINPX) elig[ne++] = na;
        na++;
    }
    if (ne < FE_RS_MINN) { fe_rs_skip++; return; }
    fe_rs_run++;
    static unsigned seed = 12345u;
    int bestc = -1; double bt[3] = {0, 0, 0};
    for (int it = 0; it < FE_RS_ITERS; it++) {
        seed = seed * 1664525u + 1013904223u; int a = elig[(seed >> 8) % ne];
        seed = seed * 1664525u + 1013904223u; int b = elig[(seed >> 8) % ne];
        if (a == b) continue;
        double t[3] = {nn[a][1] * nn[b][2] - nn[a][2] * nn[b][1], nn[a][2] * nn[b][0] - nn[a][0] * nn[b][2], nn[a][0] * nn[b][1] - nn[a][1] * nn[b][0]};
        double tn = sqrt(t[0] * t[0] + t[1] * t[1] + t[2] * t[2]);
        if (tn < 1e-9) continue;
        int cnt = 0;
        for (int q = 0; q < ne; q++) {
            int j = elig[q];
            double l[3] = {t[1] * f1[j][2] - t[2] * f1[j][1], t[2] * f1[j][0] - t[0] * f1[j][2], t[0] * f1[j][1] - t[1] * f1[j][0]};
            double ln = sqrt(l[0] * l[0] + l[1] * l[1]);
            if (ln < 1e-12) { cnt++; continue; }
            double d = fabs(l[0] * f2[j][0] + l[1] * f2[j][1] + l[2]) / ln * fx;
            if (d < FE_RS_THR) cnt++;
        }
        if (cnt > bestc) { bestc = cnt; bt[0] = t[0]; bt[1] = t[1]; bt[2] = t[2]; }
    }
    if (bestc < 0.5 * ne) return; /* no consensus: do not trust it */
    for (int q = 0; q < na; q++) {
        int j = q;
        double l[3] = {bt[1] * f1[j][2] - bt[2] * f1[j][1], bt[2] * f1[j][0] - bt[0] * f1[j][2], bt[0] * f1[j][1] - bt[1] * f1[j][0]};
        double ln = sqrt(l[0] * l[0] + l[1] * l[1]);
        if (ln < 1e-12) continue;
        double d = fabs(l[0] * f2[j][0] + l[1] * f2[j][1] + l[2]) / ln * fx;
        if (d > FE_RS_OUT) { tracks[idx[q]].alive = 0; tracks[idx[q]].obs.n = 0; fe_rs_kill++; }
    }
}

static void record_observations(void) {''')
rep('''        add_clone();
        record_observations();
        if (VI_MODE''', '''        add_clone();
        record_observations();
        ransac_filter();
        if (VI_MODE''')
rep('''    detect(cur);
    cur_pyr = cur;''', '''    detect(cur);
    if (FE_DEBUG && (frame_no % 200) == 0) fprintf(stderr, "FEDBG frame %d fb_kill %d rs_run %d rs_skip %d rs_kill %d\\n", frame_no, fe_fb_kill, fe_rs_run, fe_rs_skip, fe_rs_kill);
    cur_pyr = cur;''')
rep('''vi_ok = 0; vi_done = 0; g_have = 0;''', '''vi_ok = 0; vi_done = 0; g_have = 0; fe_fb_kill = fe_rs_kill = fe_rs_run = fe_rs_skip = 0;''')
open('fe.c', 'w').write(src)
