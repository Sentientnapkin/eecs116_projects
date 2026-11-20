#ifndef FX_FBMIN
#define FX_FBMIN 0       /* FB check only while >= this many tracks are alive at the start of the frame (0: always, = B6) */
#endif
#ifndef FX_DETB
#define FX_DETB 0        /* 1: corner-detection threshold scaled by clamp((mean gray/130)^2, .15, 1); 2: also the KLT min-eigenvalue test */
#endif
#ifndef FX_GATEZ
#define FX_GATEZ 0.0     /* >0: chi2 gate z while the filter is starved (no feature accepted for FX_WIN frames though tracks exist) */
#endif
#ifndef FX_INFL
#define FX_INFL 0.0      /* >0: while starved, every FX_WIN frames add (FX_INFL m/s)^2 to Pv and (FX_INFL/10 rad)^2 to Pth diagonals */
#endif
#ifndef FX_WIN
#define FX_WIN 20
#endif
#ifndef FX_LIVE3
#define FX_LIVE3 8
#endif
static double det_scale = 1.0;
static int fx_used, fx_hist[64], fx_hp, fx_starved, fx_nlive0;
#ifndef FX_FBT0
#define FX_FBT0 0        /* FB check starts only after this many frames (startup transient without FB) */
#endif
