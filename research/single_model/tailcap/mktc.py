"""tc_base.c (= learned_c/lc_b11.c) -> tc_b.c : adds switchable blocks. All off by default (TC_LOG, TC_RAD, TC_SPD, TC_MON = 0) => bit-identical to B11."""
s = open('tc_base.c').read()
def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:60], s.count(a)); s = s.replace(a, b)

# ---- globals (after filter state declarations)
rep('static double tri_min_eig = TRI_MIN_EIG, t_start, chi2_z = 1.645;', r'''static double tri_min_eig = TRI_MIN_EIG, t_start, chi2_z = 1.645;
/* ---- tailcap globals ---- */
#ifndef TC_LOG
#define TC_LOG 0
#endif
#ifndef TC_RAD
#define TC_RAD 0            /* A1: soft containment prior */
#endif
#ifndef TC_SPD
#define TC_SPD 0            /* A2: soft long-window speed prior */
#endif
#ifndef TC_MON
#define TC_MON 0            /* B: early-warning monitor + net re-anchor */
#endif
#ifndef TC_PH
#define TC_PH -1
#endif
static int tc_att, tc_used, tc_gate, tc_tri; static double tc_nis;
static int tc_nanch;        /* number of net re-anchors started (>0 keeps the startup heading prior off) */
static float tc_lcscale = 1.0f, tc_lcfloor = -1.0f;
''')
# ---- counters in feature_rows
rep('    if (!triangulate(&o, ci, pf)) return 0;', '    tc_att++;\n    if (!triangulate(&o, ci, pf)) { tc_tri++; return 0; }')
rep('    if (m2 > gq) { if (INV_HUBER > 0 && m2 < INV_HUBER * gq) hw = sqrt(gq / m2); else return 0; }',
    '    tc_nis += m2 / gq;\n    if (m2 > gq) { if (INV_HUBER > 0 && m2 < INV_HUBER * gq) hw = sqrt(gq / m2); else { tc_gate++; return 0; } }')
rep('    *nrows += k0;\n    return 1;', '    *nrows += k0; tc_used++;\n    return 1;')
# ---- net scale / floor hooks
rep('double s = LC_SCALE * exp(0.5 * lv) * (1.0 + LC_SPD_K * spd);', 'double s = LC_SCALE * tc_lcscale * exp(0.5 * lv) * (1.0 + LC_SPD_K * spd);')
rep('        sd[i] = s < fl ? fl : s; mu[i] = lc_out[6 + i];', '        if (tc_lcfloor >= 0) fl = tc_lcfloor;\n        sd[i] = s < fl ? fl : s; mu[i] = lc_out[6 + i];')
rep('    const signed char *at = lc_at_tab[LC_SPREAD];', '''    if (tc_nanch > 0 && TC_PH >= 0 && (frame_no & 3) != TC_PH) return; /* re-anchor stages only on the cheap phase of the clone cycle */
    const signed char *at = lc_at_tab[LC_SPREAD];''')
rep('#define LC_PRIOR_OFF (LC_REPLACE && lc_active && lc_frame >= LC_K)', '#define LC_PRIOR_OFF (LC_REPLACE && lc_active && (lc_frame >= LC_K || tc_nanch > 0))')

# ---- tailcap block before imu_measurements
block = r'''
/* =====================================================================================================================
 * tailcap: A1 containment prior, A2 speed-envelope prior, B monitor + re-anchor
 * ===================================================================================================================== */
#ifndef TC_R_OUT
#define TC_R_OUT 22.0       /* m: no effect inside (truth max distance p99 holdout 17.5, max 21.8) */
#endif
#ifndef TC_R_SD
#define TC_R_SD 3.0         /* m: sd of the pseudo-measurement 'excess distance = 0' */
#endif
#ifndef TC_Z_OUT
#define TC_Z_OUT 9.0        /* m: vertical |z| limit (holdout max 9.66) */
#endif
#ifndef TC_V3_MAX
#define TC_V3_MAX 2.5       /* m/s: 3-s mean speed above this is pulled to TC_V3_TARGET (truth max 3-s rate 2.51) */
#endif
#ifndef TC_V3_TARGET
#define TC_V3_TARGET 1.6
#endif
#ifndef TC_V_SD
#define TC_V_SD 0.5
#endif
#define TC_HIST 61
static double tc_hist[TC_HIST][3]; static int tc_hn;
static void tc_prior(void) {
    double tt = last_t - t_start;
    memcpy(tc_hist[tc_hn % TC_HIST], pos, sizeof pos); tc_hn++;
#if TC_RAD
    {
        double d = sqrt(pos[0] * pos[0] + pos[1] * pos[1] + pos[2] * pos[2]);
        double s = TC_R_SD * sqrt(SPEED_TAU / FRAME_DT);
        if (d > TC_R_OUT && d > 1e-6) {
            double rr[1] = {(TC_R_OUT - d) / s};
            memset(Hs, 0, sizeof Hs);
            for (int j = 0; j < 3; j++) Hs[P + j] = pos[j] / d / s;
            update(rr, Hs, 1, 1.0, INFINITY);
        }
        if (fabs(pos[2]) > TC_Z_OUT) {
            double rr[1] = {((pos[2] > 0 ? TC_Z_OUT : -TC_Z_OUT) - pos[2]) / s};
            memset(Hs, 0, sizeof Hs); Hs[P + 2] = 1.0 / s;
            update(rr, Hs, 1, 1.0, INFINITY);
        }
    }
#endif
#if TC_SPD
    if (tc_hn > TC_HIST - 1) {
        const double *p0 = tc_hist[(tc_hn - TC_HIST) % TC_HIST], *p1 = tc_hist[(tc_hn - 1) % TC_HIST];
        double v3 = sqrt((p1[0] - p0[0]) * (p1[0] - p0[0]) + (p1[1] - p0[1]) * (p1[1] - p0[1]) + (p1[2] - p0[2]) * (p1[2] - p0[2])) / (60 * FRAME_DT);
        double sp = sqrt(vel[0] * vel[0] + vel[1] * vel[1] + vel[2] * vel[2]);
        if (v3 > TC_V3_MAX && sp > 1e-6) {
            double s = TC_V_SD * sqrt(SPEED_TAU / FRAME_DT), rr[1] = {(TC_V3_TARGET - sp) / s};
            memset(Hs, 0, sizeof Hs);
            for (int j = 0; j < 3; j++) Hs[V + j] = vel[j] / sp / s;
            update(rr, Hs, 1, 1.0, INFINITY);
        }
    }
#endif
    (void)tt;
}

/* B: monitor. Per-frame filter-internal signals; fires a re-anchor of the learned net. */
#ifndef TC_UWIN
#define TC_UWIN 20          /* frames of the accepted-feature window */
#endif
#ifndef TC_T0
#define TC_T0 1.0           /* monitor active from (s) */
#endif
#ifndef TC_T1
#define TC_T1 3.0           /* startup monitor until (s) */
#endif
#ifndef TC_U_THR
#define TC_U_THR 3          /* startup: accepted features in the last TC_UWIN frames below this => lock-out */
#endif
#ifndef TC_RATIO
#define TC_RATIO 3.0        /* startup: est speed / net-predicted speed above this */
#endif
#ifndef TC_SPMIN
#define TC_SPMIN 1.2        /* ... and est speed above this (m/s) */
#endif
#ifndef TC_LIVE_THR
#define TC_LIVE_THR 25      /* starvation: live tracks below this for TC_LIVE_N frames */
#endif
#ifndef TC_LIVE_N
#define TC_LIVE_N 40
#endif
#ifndef TC_PERIOD
#define TC_PERIOD 100       /* frames between re-anchors while starved (0: never) */
#endif
#ifndef TC_STARTUP_MON
#define TC_STARTUP_MON 1
#endif
#ifndef TC_RE_SCALE
#define TC_RE_SCALE 1.5
#endif
#ifndef TC_RE_FLOOR
#define TC_RE_FLOOR 0.15
#endif
#ifndef TC_INFL_V
#define TC_INFL_V 0.0       /* m/s added to the velocity sd at fire time */
#endif
#ifndef TC_PV_THR
#define TC_PV_THR 0.0       /* sqrt(trace Pv) (m/s) above this after TC_T0 => re-anchor (0: off) */
#endif
#ifndef TC_PV_PERIOD
#define TC_PV_PERIOD 20
#endif
#ifndef TC_MAXANCH
#define TC_MAXANCH 12
#endif
static int tc_uring[64], tc_unow, tc_live_run, tc_fire, tc_last_fire = -100000, tc_frame;
static double tc_score;
static void tc_monitor(int live) {
    tc_frame++;
    tc_uring[tc_frame & 63] = tc_used;
    int u = 0; for (int k = 0; k < TC_UWIN; k++) u += tc_uring[(tc_frame - k) & 63];
    tc_live_run = live < TC_LIVE_THR ? tc_live_run + 1 : 0;
    double tt = last_t - t_start, sp = sqrt(vel[0] * vel[0] + vel[1] * vel[1] + vel[2] * vel[2]);
    double psp = sqrt(lc_out[6] * lc_out[6] + lc_out[7] * lc_out[7] + lc_out[8] * lc_out[8]);
    int ready = lc_applied && lc_next >= 6 && moving;       /* net has landed: predicted speed is meaningful */
    int fire = 0;
#if TC_MON
    if (tc_nanch < TC_MAXANCH && tc_frame - tc_last_fire > 30 && lc_applied && lc_next >= 6) {
        if (TC_STARTUP_MON && moving && tt >= TC_T0 && tt <= TC_T1 && ready) {
            int lock = u < TC_U_THR, runaway = sp > TC_SPMIN && sp > TC_RATIO * (psp > 0.2 ? psp : 0.2);
            if (lock && runaway) fire = 1;
        }
        if (TC_PV_THR > 0 && moving && tt >= TC_T0 && tc_frame - tc_last_fire >= TC_PV_PERIOD && sqrt(Pm[V * MAXD + V] + Pm[(V + 1) * MAXD + V + 1] + Pm[(V + 2) * MAXD + V + 2]) > TC_PV_THR) fire = 3;
        if (TC_PERIOD > 0 && moving && tc_live_run >= TC_LIVE_N && tc_frame - tc_last_fire >= TC_PERIOD && tt > TC_T1) fire = 2;
    }
#endif
    tc_fire = fire;
    if (fire) tc_last_fire = tc_frame;
#if TC_LOG
    fprintf(stderr, "D f=%d t=%.2f live=%d used=%d u20=%d att=%d gate=%d tri=%d nis=%.2f sp=%.3f psp=%.3f nanch=%d fire=%d Pv=%.4f v=%.3f,%.3f,%.3f p=%.3f,%.3f,%.3f\n",
            tc_frame, tt, live, tc_used, u, tc_att, tc_gate, tc_tri, tc_att ? tc_nis / tc_att : 0.0, sp, ready ? psp : -1.0, tc_nanch, fire,
            sqrt(Pm[V * MAXD + V] + Pm[(V + 1) * MAXD + V + 1] + Pm[(V + 2) * MAXD + V + 2]), vel[0], vel[1], vel[2], pos[0], pos[1], pos[2]);
#endif
    tc_att = tc_used = tc_gate = tc_tri = 0; tc_nis = 0;
}

static void imu_measurements('''
rep('\nstatic void imu_measurements(', block)
# ---- step hooks
rep('''    lc_step(frame, imu, imu_count);
    vision(frame);
    write_state(out);''', '''#if TC_RAD || TC_SPD
    tc_prior();
#endif
    if (tc_fire && imu_count) {
        tc_fire = 0; tc_nanch++;
        tc_lcscale = (float)TC_RE_SCALE; tc_lcfloor = (float)TC_RE_FLOOR;
        for (int i = 0; i < 3; i++) Pm[(V + i) * MAXD + V + i] += TC_INFL_V * TC_INFL_V;
        lc_begin(frame, imu, imu_count);
    } else
    lc_step(frame, imu, imu_count);
    vision(frame);
#if TC_LOG || TC_MON
    { int live = 0; for (int i = 0; i < MAX_TRACKS; i++) live += tracks[i].alive; tc_monitor(live); }
#endif
    write_state(out);''')
open('tc_c.c', 'w').write(s)
