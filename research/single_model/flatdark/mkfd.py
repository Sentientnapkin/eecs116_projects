import re
src=open('../fuel/adopted_c1_fbh_exact.c').read()
def rep(a,b,cnt=1):
    global src
    assert src.count(a)==cnt,(a,src.count(a))
    src=src.replace(a,b)
rep('#define BORDER (KLT_R + 3)\n','''#define BORDER (KLT_R + 3)
/* FLAT/DARK arms (all off by default = B7 bit-identical) */
#ifndef FD_THR
#define FD_THR 0.0          /* >0: detection threshold used while starved (live tracks < FD_N) */
#endif
#ifndef FD_N
#define FD_N 25             /* starved = fewer live tracks than this at detection time */
#endif
#ifndef FD_CELL2
#define FD_CELL2 0          /* 1: while starved, a second feature per grid cell (>= FD_MIND px from the first) */
#endif
#ifndef FD_MIND
#define FD_MIND 10.0
#endif
''')
rep('''static void detect(int which) {
    int occupied[MAX_TRACKS] = {0}, free_slot[MAX_TRACKS], nfree = 0;
    for (int i = 0; i < MAX_TRACKS; i++) {
        if (tracks[i].alive) occupied[cell_of(tracks[i].x, tracks[i].y)] = 1;
        else free_slot[nfree++] = i;
    }
    const uint8_t *I = pyr[which][0];
    for (int k = 0; k < MAX_TRACKS && nfree > 0; k++) {
        int cell = (detect_cursor + k) % MAX_TRACKS;
        if (occupied[cell]) continue;
        int x0 = (cell % GRID_X) * CELL_W, y0 = (cell / GRID_X) * CELL_H;
        double best = DETECT_MIN_SCORE;
''','''static void detect(int which) {
    int occupied[MAX_TRACKS] = {0}, free_slot[MAX_TRACKS], nfree = 0, nlive = 0;
    for (int i = 0; i < MAX_TRACKS; i++) {
        if (tracks[i].alive) { occupied[cell_of(tracks[i].x, tracks[i].y)]++; nlive++; }
        else free_slot[nfree++] = i;
    }
    const int starved = (FD_THR > 0.0 || FD_CELL2) && nlive < FD_N;
    const double thr = (starved && FD_THR > 0.0) ? FD_THR : DETECT_MIN_SCORE;
    const int npass = (starved && FD_CELL2) ? 2 : 1;
    const uint8_t *I = pyr[which][0];
    for (int k = 0; k < npass * MAX_TRACKS && nfree > 0; k++) {
        int cell = (detect_cursor + k) % MAX_TRACKS, pass = k / MAX_TRACKS, excl = 0;
        if (pass == 0) { if (occupied[cell]) continue; }
        else { if (occupied[cell] != 1) continue; excl = 1; }
        int x0 = (cell % GRID_X) * CELL_W, y0 = (cell / GRID_X) * CELL_H;
        double best = thr;
''')
# exclusion in the F_DET accept and the plain branch
rep('''                        if (s > best) { best = s; bx = x; by = y; }
                    }
                }
            }
        }
#else''','''                        if (s > best && !(excl && fd_near(x, y, cell))) { best = s; bx = x; by = y; }
                    }
                }
            }
        }
#else''')
rep('''                if (s > best) { best = s; bx = x; by = y; }
            }
        }
#endif''','''                if (s > best && !(excl && fd_near(x, y, cell))) { best = s; bx = x; by = y; }
            }
        }
#endif''')
rep('''            t->alive = 1; t->x = bx; t->y = by; t->obs.n = 0;
        }
    }
    detect_cursor''','''            t->alive = 1; t->x = bx; t->y = by; t->obs.n = 0;
            occupied[cell]++;
        }
    }
    detect_cursor''')
rep('''static void detect(int which) {''','''static int fd_near(int x, int y, int cell) { /* a live track in this cell closer than FD_MIND px */
    for (int i = 0; i < MAX_TRACKS; i++) {
        if (!tracks[i].alive || cell_of(tracks[i].x, tracks[i].y) != cell) continue;
        double dx = tracks[i].x - x, dy = tracks[i].y - y;
        if (dx * dx + dy * dy < FD_MIND * FD_MIND) return 1;
    }
    return 0;
}

static void detect(int which) {''')
rep('#define BORDER (KLT_R + 3)\n/* FLAT/DARK','#define BORDER (KLT_R + 3)\n#ifndef FD_DBG\n#define FD_DBG 0\n#endif\n#ifndef FD_T0\n#define FD_T0 0             /* starvation logic only from this frame on (startup transient excluded) */\n#endif\n/* FLAT/DARK')
rep('const int starved = (FD_THR > 0.0 || FD_CELL2) && nlive < FD_N;','const int starved = (FD_THR > 0.0 || FD_CELL2) && nlive < FD_N && frame_no >= FD_T0;')
rep('    detect_cursor = (detect_cursor + 7) % MAX_TRACKS;\n}','    if (FD_DBG && frame_no % 20 == 0) { int nn = 0; for (int i = 0; i < MAX_TRACKS; i++) nn += tracks[i].alive; fprintf(stderr, "FD f=%d live_before=%d live_after=%d starved=%d thr=%.0f\\n", frame_no, nlive, nn, starved, thr); }\n    detect_cursor = (detect_cursor + 7) % MAX_TRACKS;\n}')
rep('/* FLAT/DARK arms','#ifndef FD_FAST\n#define FD_FAST 0           /* 1: while starved min_obs=2 + relaxed triangulation; 2: also clone every 2 frames */\n#endif\nstatic int fd_starved;\n/* FLAT/DARK arms')
rep('const int starved = (FD_THR > 0.0 || FD_CELL2) && nlive < FD_N && frame_no >= FD_T0;','const int sflag = nlive < FD_N && frame_no >= FD_T0;\n    const int starved = (FD_THR > 0.0 || FD_CELL2) && sflag;\n    fd_starved = FD_FAST ? sflag : 0;')
rep('        chi2_z = fast ? FAST_CHI2_Z : CHI2_Z;\n','        chi2_z = fast ? FAST_CHI2_Z : CHI2_Z;\n        if (FD_FAST && fd_starved) { min_obs = FAST_MIN_OBS; tri_min_eig = FAST_TRI_EIG; if (FD_FAST >= 2) clone_every = FAST_CLONE_EVERY; }\n')
rep('frame_no = 0; clone_every = CLONE_EVERY;','fd_starved = 0; frame_no = 0; clone_every = CLONE_EVERY;')
rep('static int fd_starved;','static int fd_starved, fd_scount;\n#ifndef FD_VS\n#define FD_VS 0.0           /* >0: horizontal speed-prior sd multiplier after FD_LONG consecutive starved frames */\n#endif\n#ifndef FD_LONG\n#define FD_LONG 100\n#endif')
rep('    fd_starved = FD_FAST ? sflag : 0;','    fd_starved = FD_FAST ? sflag : 0;\n    fd_scount = sflag ? fd_scount + 1 : 0;')
rep('    if (INV_VZ > 0) sz = INV_VZ;','    if (INV_VZ > 0) sz = INV_VZ;\n    if (FD_VS > 0.0 && fd_scount > FD_LONG) sh *= FD_VS;')
rep('fd_starved = 0; frame_no = 0;','fd_starved = 0; fd_scount = 0; frame_no = 0;')
open('fd.c','w').write(src)
