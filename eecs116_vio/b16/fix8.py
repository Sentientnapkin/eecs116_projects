s = open('b16s.c').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)

rep("    if (!PRIOR_ALT || (frame_no & 1) == 0) update(r, Hs, 2, (ACCEL_NOISE * ACCEL_NOISE / n + THRUST_MODEL_STD * THRUST_MODEL_STD) * (PRIOR_ALT ? 0.5 : 1.0), THRUST_GATE);",
    "    if (PRIOR_N <= 1 || frame_no % PRIOR_N == 0) update(r, Hs, 2, (ACCEL_NOISE * ACCEL_NOISE / n + THRUST_MODEL_STD * THRUST_MODEL_STD) / PRIOR_N, THRUST_GATE);")
rep("    if (PRIOR_ALT) { if ((frame_no & 1) == 0) return; scale *= M_SQRT1_2; }\n",
    "    if (PRIOR_N > 1) { if (frame_no % PRIOR_N != PRIOR_N / 2) return; scale /= sqrt((double)PRIOR_N); }\n")
rep("sl = INV_LAT * sqrt(SPEED_TAU / FRAME_DT) * (PRIOR_ALT ? M_SQRT1_2 : 1.0)", "sl = INV_LAT * sqrt(SPEED_TAU / FRAME_DT) / sqrt((double)PRIOR_N)")
rep("#ifndef PRIOR_ALT\n#define PRIOR_ALT 0   /* 1: thrust model on even frames, velocity priors on odd frames, each with doubled information */\n#endif\n",
    "#ifndef PRIOR_ALT\n#define PRIOR_ALT 0\n#endif\n#ifndef PRIOR_N\n#define PRIOR_N (PRIOR_ALT ? 2 : 1)   /* thrust model every N frames, velocity priors every N frames (offset N/2), each with N x the information */\n#endif\n")
open('b16s.c', 'w').write(s)
print("ok")
