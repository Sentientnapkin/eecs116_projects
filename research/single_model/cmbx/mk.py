import re
src=open('../frontend/adopted_fbh.c').read()
e=open('../edge/e.c').read().split('\n')
def L(a,b): return '\n'.join(e[a-1:b])+'\n'   # 1-based inclusive
params = '''/* ---- CMBX (research/single_model/cmbx): startup speed-consistency check + flow-direction override for starts far off the camera axis ----
   CMBX=1 enables both (EDGE_SPD, VI_MODE); CMBX=0 is bit-identical to frontend/adopted_fbh.c (G+C1+FB).
   VI_MODE 1: at the VI_CLONES-th clone of a moving start the de-rotated flow gives the translation direction; if it is more than acos(VI_COSMAX)
   off the camera axis the velocity is reset to the flow direction and speed (flow speed = |flow|/dt*VI_Z0) and the heading prior is off for the startup.
   EDGE_SPD 1: if the filter speed exceeds EDGE_SP_RATIO*v_flow + EDGE_SP_ABS the velocity is scaled to the flow speed and the heading prior is off. */
#ifndef CMBX
#define CMBX 1
#endif
#ifndef VI_MODE
#define VI_MODE CMBX
#endif
#ifndef EDGE_SPD
#define EDGE_SPD CMBX
#endif
#ifndef FGT_GUARD
#define FGT_GUARD 1
#endif
#ifndef VI_CLONES
#define VI_CLONES 4
#endif
#ifndef VI_COSMAX
#define VI_COSMAX -0.26 /* cos of the angle between flow direction and camera axis above which the reset is skipped (-0.26 = 105 deg) */
#endif
#ifndef VI_TMAX
#define VI_TMAX 1.0
#endif
#ifndef VI_NMIN
#define VI_NMIN 8
#endif
#ifndef VI_Z0
#define VI_Z0 2.0
#endif
#ifndef VI_SPAR
#define VI_SPAR 0.3
#endif
#ifndef VI_SPERP
#define VI_SPERP 0.2
#endif
#ifndef VI_SFLOOR
#define VI_SFLOOR 0.15
#endif
#ifndef EDGE_SP_RATIO
#define EDGE_SP_RATIO 1.8
#endif
#ifndef EDGE_SP_ABS
#define EDGE_SP_ABS 0.25
#endif
#ifndef EDGE_SP_TMAX
#define EDGE_SP_TMAX 1.0
#endif
#ifndef EDGE_SP_SIG
#define EDGE_SP_SIG 0.2
#endif
static int vi_ok, sp_ok;
'''
# 1. params after detect_cursor decl
a='static int detect_cursor;\n'
assert src.count(a)==1
src=src.replace(a,a+params)
# 2. prior skip
b='    int in_start = tt < START_T;\n'
assert src.count(b)==1
src=src.replace(b,b+'    if (((VI_MODE && vi_ok == 1) || (EDGE_SPD && sp_ok == 1)) && startup) return; /* CMBX: flow-based velocity replaces the heading prior */\n')
# 3. functions
funcs = L(1217,1297)  # flow_dir, vi_reset, sp_cap (+ blank)
funcs = funcs.replace('    if (d[2] > VI_COSMAX)','    if (d[2] > VI_COSMAX)')
funcs = funcs.replace('    if (VI_POS) {\n        double el = last_t - t_start;\n        for (int i = 0; i < 3; i++) { double np = vel[i] * el; pos[i] = np; clones[nclones - 1].p[i] = np; }\n    }\n','')
assert 'VI_POS' not in funcs
c='static void vision(const uint8_t *frame) {\n'
assert src.count(c)==1
src=src.replace(c,'/* flow-direction estimate of the camera translation direction between the first and the newest clone */\n'+funcs+c)
# 4. call sites
d='        record_observations();\n        vision_zupt();\n'
assert src.count(d)==1
src=src.replace(d,'''        record_observations();
        if (VI_MODE && moving && !vi_ok && nclones >= VI_CLONES && last_t - t_start < VI_TMAX &&
            !(FGT_GUARD && GATE_MODE == 1 && (gate_released || (gate_pairs >= 1 && gate_pairs <= GATE_PAIRS_MAX && gate_max < GATE_DISP))))
            vi_reset();
        if (EDGE_SPD && moving && !sp_ok && vi_ok != 1 && nclones >= VI_CLONES && last_t - t_start < EDGE_SP_TMAX && !gate_released) sp_cap();
        vision_zupt();
''')
# 5. reset
f='        frame_no = 0; clone_every = CLONE_EVERY;'
assert src.count(f)==1
src=src.replace(f,'        vi_ok = 0; sp_ok = 0;\n'+f)
open('b8.c','w').write(src)
