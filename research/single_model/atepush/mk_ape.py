"""mk_ape.py: ap.c (+ edge_mod.c, edge_rows.c) -> ape.c with the EDGE switch (default 0: same source semantics as ap.c)."""
from pathlib import Path
H = Path(__file__).resolve().parent
s = (H / 'ap.c').read_text()
def rep(old, new, cnt=1, start=0):
    global s
    i = s.find(old, start); assert i >= 0, old[:60]
    if cnt == 1: assert s.find(old, i + 1) < 0 or start, ('not unique', old[:60])
    s = s[:i] + new + s[i + len(old):]
    return i
OBS = 'typedef struct { int n; int cid[MAX_OBS]; double x[MAX_OBS], y[MAX_OBS]; int tid; double px, py; } Obs;'
rep(OBS, '#ifndef EDGE\n#define EDGE 0   /* atepush: edgelet (point-on-line) MSCKF features in vision-starved scenes */\n#endif\n#ifndef EDGE_DBG\n#define EDGE_DBG 0\n#endif\n'
    '#if EDGE\ntypedef struct { int n; int cid[MAX_OBS]; double x[MAX_OBS], y[MAX_OBS]; int tid; double px, py; float enx[MAX_OBS], eny[MAX_OBS]; int edge; } Obs;\n#else\n' + OBS + '\n#endif')
FR = 'static int feature_rows(const Obs *o_in, int *nrows) {'
mod = (H / 'edge_mod.c').read_text(); rows = (H / 'edge_rows.c').read_text()
rep(FR, '#if EDGE\n' + mod + rows + '#endif\n' + FR + '\n#if EDGE\n    if (o_in->edge) return edge_rows(o_in, nrows);\n#endif')
# B17 path vision (the last vision definition)
v0 = s.rfind('static void vision(const uint8_t *frame) {')
rep('    track_all(prev, cur, Rwc_now);\n', '    track_all(prev, cur, Rwc_now);\n#if EDGE\n    { double Rr[9]; m3tmul(Rwc_now, Rwc_prev, Rr); edge_track_all(cur, Rr); }\n#endif\n', start=v0)
rep('        record_observations();\n        vision_zupt();\n', '        record_observations();\n#if EDGE\n        edge_record();\n#endif\n        vision_zupt();\n', start=v0)
rep('            msckf_update(batch, nb);\n            remove_oldest_clone();\n', '#if EDGE\n            nb = edge_take(batch, nb, 1);\n#endif\n            msckf_update(batch, nb);\n            remove_oldest_clone();\n#if EDGE\n            edge_drop_clone(oldest);\n#endif\n', start=v0)
rep('        } else {\n            msckf_update(batch, nb);\n        }\n', '        } else {\n#if EDGE\n            nb = edge_take(batch, nb, 0);\n#endif\n            msckf_update(batch, nb);\n        }\n', start=v0)
rep('    detect(cur);\n    cur_pyr = cur;\n', '    detect(cur);\n#if EDGE\n    if (frames_since_clone == 0) edge_detect(cur);\n'
    '    if (EDGE_DBG && frames_since_clone == 0) { int ne = 0, nl = 0; for (int i = 0; i < EDGE_N; i++) ne += edges[i].alive; for (int i = 0; i < MAX_TRACKS; i++) nl += tracks[i].alive;\n'
    '        fprintf(stderr, "E f=%d live=%d edges=%d spawn=%ld rows=%ld\\n", frame_no, nl, ne, e_spawn, e_rows); }\n#endif\n    cur_pyr = cur;\n', start=v0)

v0 = s.rfind('static void vision(const uint8_t *frame) {')
rep('        msckf_update(batch, nb);\n#if MAP_MODE\n        if (MAP_SPREAD) map_relocalize(',
    '#if EDGE\n        if (EDGE_SPREAD) { int nph = clone_every - 1 > 0 ? clone_every - 1 : 1; nb = edge_take_ph(batch, nb, (frames_since_clone - 1) % nph, nph); }\n#endif\n        msckf_update(batch, nb);\n#if MAP_MODE\n        if (MAP_SPREAD) map_relocalize(', start=v0)

# GOV (T4uB) path vision
g0 = s.find('static int gov_take(Obs *o, int *rw, int cap)')
rep('        gov_klt_cnt = 0;\n        track_all(prev, cur, Rwc_now);\n        gov_used += gov_klt_cnt * GC_KLT;\n',
    '        gov_klt_cnt = 0;\n        track_all(prev, cur, Rwc_now);\n        gov_used += gov_klt_cnt * GC_KLT;\n#if EDGE\n        { double Rr[9]; m3tmul(Rwc_now, Rwc_prev, Rr); edge_track_all(cur, Rr); gov_used += edge_alive() * GC_EDGE; }\n#endif\n', start=g0)
rep('            add_clone(); record_observations(); vision_zupt(); cloned = 1;\n',
    '            add_clone(); record_observations();\n#if EDGE\n            edge_record();\n#endif\n            vision_zupt(); cloned = 1;\n', start=g0)
rep('        if (nb) { msckf_update(batch, nb); gov_used += GC_BATCH + rw * GC_ROW; }\n        remove_oldest_clone();\n',
    '#if EDGE\n        nb = edge_take_b(batch, nb, 1, &rw, cap);\n#endif\n        if (nb) { msckf_update(batch, nb); gov_used += GC_BATCH + rw * GC_ROW; }\n        remove_oldest_clone();\n#if EDGE\n        edge_drop_clone(oldest);\n#endif\n', start=g0)
rep('        }\n        if (nb) { msckf_update(batch, nb); gov_used += GC_BATCH + rw * GC_ROW; }\n    }\n    tc_rows = rw; gov_nb = nb;\n',
    '        }\n#if EDGE\n        if (cloned) nb = edge_take_b(batch, nb, 0, &rw, cap);\n#endif\n        if (nb) { msckf_update(batch, nb); gov_used += GC_BATCH + rw * GC_ROW; }\n    }\n    tc_rows = rw; gov_nb = nb;\n', start=g0)
rep('        detect(cur);\n        gov_used += gov_ncell * GC_CELL;\n        cur_pyr = cur;\n',
    '        detect(cur);\n        gov_used += gov_ncell * GC_CELL;\n#if EDGE\n        if (cloned && GOV_B - gov_used > EDGE_GCDET) { edge_detect(cur); gov_used += EDGE_GCDET; }\n#endif\n        cur_pyr = cur;\n', start=g0)

rep('memset(tracks, 0, sizeof tracks); memset(det_until, 0, sizeof det_until);\n', 'memset(tracks, 0, sizeof tracks); memset(det_until, 0, sizeof det_until);\n#if EDGE\n        edge_reset();\n#endif\n')

# GINF: gate-consensus velocity covariance inflation (in tc_monitor; both paths)
GI = """#ifndef GINF
#define GINF 0          /* atepush: inflate the velocity covariance when most attempted features fail the gate/triangulation */
#endif
#ifndef GI_WIN
#define GI_WIN 20       /* frames */
#endif
#ifndef GI_MINATT
#define GI_MINATT 10
#endif
#ifndef GI_FRAC
#define GI_FRAC 0.5     /* (gated + triangulation-failed) / attempted over the window */
#endif
#ifndef GI_SD
#define GI_SD 0.5       /* m/s added (in quadrature) to each velocity axis */
#endif
#ifndef GI_GAP
#define GI_GAP 20       /* min frames between inflations */
#endif
#ifndef GI_T0
#define GI_T0 0.0
#endif
#if GINF
static int gi_att[64], gi_bad[64], gi_last = -1000000; static long gi_n;
#endif
"""
rep('static void tc_reset(void) {', GI + 'static void tc_reset(void) {')
rep('    tc_live_lo = 0; tc_live_run = 0; tc_fire = 0; tc_last_fire = -100000; tc_frame = 0; tc_score = 0;\n',
    '    tc_live_lo = 0; tc_live_run = 0; tc_fire = 0; tc_last_fire = -100000; tc_frame = 0; tc_score = 0;\n#if GINF\n    memset(gi_att, 0, sizeof gi_att); memset(gi_bad, 0, sizeof gi_bad); gi_last = -1000000; gi_n = 0;\n#endif\n')
rep('    if (fire && TC_PHB >= 0 && (frame_no & 3) != TC_PHB) fire = 0;\n',
    """#if GINF
    {
        gi_att[tc_frame & 63] = tc_att; gi_bad[tc_frame & 63] = tc_gate + tc_tri;
        int sa = 0, sb = 0; for (int k = 0; k < GI_WIN; k++) { sa += gi_att[(tc_frame - k) & 63]; sb += gi_bad[(tc_frame - k) & 63]; }
        if (tt >= GI_T0 && sa >= GI_MINATT && sb >= GI_FRAC * sa && tc_frame - gi_last >= GI_GAP) {
            for (int i = 0; i < 3; i++) Pm[(V + i) * MAXD + V + i] += GI_SD * GI_SD;
            gi_last = tc_frame; gi_n++;
            if (EDGE_DBG) fprintf(stderr, "GI f=%d t=%.2f att=%d bad=%d n=%ld\\n", tc_frame, tt, sa, sb, gi_n);
        }
    }
#endif
    if (fire && TC_PHB >= 0 && (frame_no & 3) != TC_PHB) fire = 0;
""")

# GREG: immediate re-gate: when most features of a batch fail the gate, inflate Pv and rebuild the rows once
rep('        g_dx = it ? dx : 0;\n        int k = build_rows(batch, nbatch);\n',
    """        g_dx = it ? dx : 0;
#if GREG
        int ga0 = tc_att, gg0 = tc_gate + tc_tri;
#endif
        int k = build_rows(batch, nbatch);
#if GREG
        if (it == 0) {
            int ga = tc_att - ga0, gb = tc_gate + tc_tri - gg0;
            if (ga >= GR_MIN && gb >= GR_FRAC * ga) {
                for (int i = 0; i < 3; i++) Pm[(V + i) * MAXD + V + i] += GR_SD * GR_SD;
                tc_att = ga0; tc_gate = gg0; tc_tri = 0; /* recount (tri folded into gate snapshot) */
                k = build_rows(batch, nbatch);
            }
        }
#endif
""")
rep('static void tc_reset(void) {', """#ifndef GREG
#define GREG 0
#endif
#ifndef GR_MIN
#define GR_MIN 4
#endif
#ifndef GR_FRAC
#define GR_FRAC 0.6
#endif
#ifndef GR_SD
#define GR_SD 0.5
#endif
static void tc_reset(void) {""")

(H / 'ape.c').write_text(s)
print('ok', len(s))
