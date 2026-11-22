s = open('b16s.c').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)

# --- priors on alternate frames with doubled information
rep("    update(r, Hs, 2, ACCEL_NOISE * ACCEL_NOISE / n + THRUST_MODEL_STD * THRUST_MODEL_STD, THRUST_GATE);",
    "    if (!PRIOR_ALT || (frame_no & 1) == 0) update(r, Hs, 2, (ACCEL_NOISE * ACCEL_NOISE / n + THRUST_MODEL_STD * THRUST_MODEL_STD) * (PRIOR_ALT ? 0.5 : 1.0), THRUST_GATE);")
rep("    double scale = sqrt(SPEED_TAU / FRAME_DT);\n",
    "    double scale = sqrt(SPEED_TAU / FRAME_DT);\n    if (PRIOR_ALT) { if ((frame_no & 1) == 0) return; scale *= M_SQRT1_2; }\n")
rep("sl = INV_LAT * sqrt(SPEED_TAU / FRAME_DT)", "sl = INV_LAT * sqrt(SPEED_TAU / FRAME_DT) * (PRIOR_ALT ? M_SQRT1_2 : 1.0)")
rep("static void imu_measurements(const double *imu, int n) {",
    "#ifndef PRIOR_ALT\n#define PRIOR_ALT 0   /* 1: thrust model on even frames, velocity priors on odd frames, each with doubled information */\n#endif\nstatic void imu_measurements(const double *imu, int n) {")

# --- cap on stacked rows per MSCKF update; the rest wait in the ended-track queue
rep("""static void msckf_update(Obs *batch, int nbatch) {
    double noise = (PIXEL_STD / fx) * (PIXEL_STD / fx), dx[MAXD], dxn[MAXD], reff[MAX_ROWS > MAXD ? MAXD : MAX_ROWS];""",
"""static void msckf_update(Obs *batch, int nbatch) {
    if (UPD_ROWCAP > 0) {
        int est = 0, keep = 0;
        for (; keep < nbatch; keep++) {
            int no = 0;
            for (int k = 0; k < batch[keep].n; k++) no += clone_index(batch[keep].cid[k]) >= 0;
            int rws = no >= min_obs ? 2 * no - 3 : 0;
            if (keep > 0 && est + rws > UPD_ROWCAP) break;
            est += rws;
        }
        for (int b = keep; b < nbatch; b++) if (nlost < 2 * MAX_TRACKS) { lost[nlost] = batch[b]; lost[nlost].tid = -1; nlost++; }
        nbatch = keep;
    }
    double noise = (PIXEL_STD / fx) * (PIXEL_STD / fx), dx[MAXD], dxn[MAXD], reff[MAX_ROWS > MAXD ? MAXD : MAX_ROWS];""")
rep("#if ITER_UPD > 1\nstatic Clone sv_clones", "#ifndef UPD_ROWCAP\n#define UPD_ROWCAP 0   /* >0: features beyond this many stacked rows wait for the next update */\n#endif\n#if ITER_UPD > 1\nstatic Clone sv_clones")
open('b16s.c', 'w').write(s)
print("ok")
