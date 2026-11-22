s = open('b16s.c').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)

# priors on tracking frames in split mode: the frame about to be processed is a tracking frame when frames_since_clone + 1 is even
rep("    if (PRIOR_N <= 1 || frame_no % PRIOR_N == 0) update(r, Hs, 2,",
    "    if (PRIOR_N <= 1 || (PRIOR_TRK ? (frames_since_clone + 1) % PRIOR_N == PRIOR_N / 2 : frame_no % PRIOR_N == 0)) update(r, Hs, 2,")
rep("    if (PRIOR_N > 1) { if (frame_no % PRIOR_N != PRIOR_N / 2) return; scale /= sqrt((double)PRIOR_N); }\n",
    "    if (PRIOR_N > 1) { if (PRIOR_TRK ? (frames_since_clone + 1) % PRIOR_N != 0 : frame_no % PRIOR_N != PRIOR_N / 2) return; scale /= sqrt((double)PRIOR_N); }\n")
rep("#ifndef PRIOR_N\n", "#ifndef PRIOR_TRK\n#define PRIOR_TRK 0   /* split mode, PRIOR_N 2 or 4: priors on tracking frames (thrust at phase N/2, velocity priors at phase 0 = clone frame) */\n#endif\n#ifndef PRIOR_N\n")
# detection at the end of tracking frames
rep("""        cur_pyr = cur;
        m3mul(R, R_bc, Rwc_prev);
        return;
    }
    /* update frame */""", """        cur_pyr = cur;
        m3mul(R, R_bc, Rwc_prev);
        if (DET_ON_TRACK) detect(cur_pyr);
        return;
    }
    /* update frame */""")
rep("""        msckf_update(batch, nb);
    }
    detect(cur_pyr);
}""", """        msckf_update(batch, nb);
    }
    if (!DET_ON_TRACK) detect(cur_pyr);
}""")
rep("#ifndef OLD_EARLY\n", "#ifndef DET_ON_TRACK\n#define DET_ON_TRACK 0\n#endif\n#ifndef OLD_EARLY\n")
open('b16s.c', 'w').write(s)
print("ok")
