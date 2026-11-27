"""r7 patch: blur-aware per-observation pixel noise. base.c -> r7.c. BLUR_C=0 => identical code path."""
import re
s=open('base.c').read()
def rep(a,b,cnt=None):
    global s; n=s.count(a); assert n and (cnt is None or n==cnt),(a,n); s=s.replace(a,b)
rep("double x[MAX_OBS], y[MAX_OBS]; int tid;","double x[MAX_OBS], y[MAX_OBS]; float bl[MAX_OBS]; int tid;",2)
rep("typedef struct { int alive; double x, y; Obs obs; int born; double fx_, fy_; } Track;",
    "typedef struct { int alive; double x, y; Obs obs; int born; double fx_, fy_; float dl; } Track;",1)
rep("o.x[o.n] = o_in->x[k]; o.y[o.n] = o_in->y[k];","o.x[o.n] = o_in->x[k]; o.y[o.n] = o_in->y[k]; o.bl[o.n] = o_in->bl[k];")
rep("o->x[k] = o->x[j]; o->y[k] = o->y[j];","o->x[k] = o->x[j]; o->y[k] = o->y[j]; o->bl[k] = o->bl[j];")
rep("memmove(t->obs.y, t->obs.y + 1, (MAX_OBS - 1) * sizeof(double));",
    "memmove(t->obs.y, t->obs.y + 1, (MAX_OBS - 1) * sizeof(double)); memmove(t->obs.bl, t->obs.bl + 1, (MAX_OBS - 1) * sizeof(float));")
rep("t->obs.y[t->obs.n] = (t->y - cy) / fy;","t->obs.y[t->obs.n] = (t->y - cy) / fy; t->obs.bl[t->obs.n] = t->dl;")
rep("if (ok) { t->fx_ = nx - g0x; t->fy_ = ny - g0y; }","if (ok) { t->fx_ = nx - g0x; t->fy_ = ny - g0y; t->dl = (float)hypot(nx - t->x, ny - t->y); }")
rep("t->alive = 1; t->x = bx; t->y = by; t->obs.n = 0; t->fx_ = t->fy_ = 0;","t->alive = 1; t->x = bx; t->y = by; t->obs.n = 0; t->fx_ = t->fy_ = 0; t->dl = (float)blur_dlmed;")
# globals + estimator hook, placed before Track typedef users: put after Track typedef
rep("float dl; } Track;","""float dl; } Track;
#ifndef BLUR_ON
#define BLUR_ON 0
#endif
static void blur_update(void);
#ifndef BLUR_C
#define BLUR_C 0.0      /* r7: obs noise sd^2 = PIXEL_STD^2 + (BLUR_C * blur_std_px)^2 ; 0 = off */
#endif
#ifndef BLUR_K
#define BLUR_K 0        /* r7: oracle sub-frame count (exposure = BLUR_K x 5 ms); 0 = use runtime estimate blur_k */
#endif
#ifndef BLUR_KDEF
#define BLUR_KDEF 5.5   /* r7: assumed k when no estimate (prior mean of U(1..10)) */
#endif
static double blur_dlmed = 0, blur_k = BLUR_KDEF;
static double blur_spx(void) { double k = BLUR_K > 0 ? BLUR_K : blur_k; return k > 1 ? 0.1 * sqrt((k * k - 1) / 12.0) : 0; } /* blur std (px) per px/frame of image speed */""")
# whitening in feature_rows (the plain-point version: unique anchor is the Hf assignment followed by the null-space comment)
a="""    int nzc[6 * MAX_OBS], nnz = 0, seen[MAX_CLONES + 1] = {0};
    for (int k = 0; k < o.n; k++)
        if (!seen[ci[k]]) {"""
n=s.count(a);print('anchor count',n)
idx=[m.start() for m in re.finditer(re.escape(a),s)]
# choose the occurrence inside static int feature_rows(
fr=s.index('static int feature_rows(const Obs *o_in, int *nrows) {')
i=min(x for x in idx if x>fr)
w="""#if BLUR_ON
    { const double sp = blur_spx() * BLUR_C / PIXEL_STD;
      for (int k = 0; k < o.n; k++) {
        const double L = sp * o.bl[k], wk = 1 / sqrt(1 + L * L);
        if (wk > 0.999) continue;
        const int off = CORE + 6 * ci[k];
        for (int r2 = 0; r2 < 2; r2++) {
            rr[2 * k + r2] *= wk;
            for (int q = 0; q < 6; q++) Hx[(2 * k + r2) * MAXD + off + q] *= wk;
            for (int q = 0; q < 3; q++) Hf[(2 * k + r2) * 3 + q] *= wk;
        } } }
#endif
"""
s=s[:i]+w+s[i:]
open('r7.c','w').write(s);print('ok')
s=open('r7.c').read()
s=s.replace("track_all(prev, cur, Rwc_now);","track_all(prev, cur, Rwc_now); blur_update();")
a="static void vision(const uint8_t *frame) {"
i=s.index(a)
s=s[:i]+"""static void blur_update(void) { /* r7: mean last-frame image displacement of live tracks (seed for new tracks) + exposure estimate hook */
    double sm = 0; int n = 0;
    for (int i = 0; i < MAX_TRACKS; i++) if (tracks[i].alive) { sm += tracks[i].dl; n++; }
    blur_dlmed = n ? sm / n : 0;
#ifdef BLUR_EST
    blur_est_step();
#endif
}
"""+s[i:]
open('r7.c','w').write(s);print('ok2')
