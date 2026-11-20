s=open('../frontend/adopted_fbh.c').read()
def rep(a,b):
    global s
    assert s.count(a)==1,(a,s.count(a)); s=s.replace(a,b)
blk=open('block.h').read()
rep('static int moving, frame_no, clone_every = CLONE_EVERY, min_obs = MIN_OBS;','static int moving, frame_no, clone_every = CLONE_EVERY, min_obs = MIN_OBS;\n'+blk)
rep('static void track_all(int prev, int cur, const double *Rwc_now) {','static void track_all(int prev, int cur, const double *Rwc_now) {\n    fx_nlive0 = 0;\n    for (int i = 0; i < MAX_TRACKS; i++) fx_nlive0 += tracks[i].alive;')
rep('if (ok && ((frame_no + i) & 1)) {','if (ok && fx_nlive0 >= FX_FBMIN && frame_no >= FX_FBT0 && ((frame_no + i) & 1)) {')
# detect: scaled threshold
rep('        double best = DETECT_MIN_SCORE;','        double best = DETECT_MIN_SCORE * (FX_DETB ? det_scale : 1.0);')
rep('static void vision(const uint8_t *frame) {\n    int prev = cur_pyr, cur = 1 - cur_pyr;\n    build_pyramid(frame, cur);',
'''static void vision(const uint8_t *frame) {
    int prev = cur_pyr, cur = 1 - cur_pyr;
    build_pyramid(frame, cur);
    if (FX_DETB) { long sum = 0; for (int i = 0; i < IMG_W * IMG_H; i += 7) sum += pyr[cur][0][i];
        double b = (double)sum / (IMG_W * IMG_H / 7) / 130.0; det_scale = b * b; if (det_scale > 1) det_scale = 1; if (det_scale < 0.15) det_scale = 0.15; }''')
rep('        if (mineig < KLT_MIN_EIG * KLT_N || det <= 0) {','        if (mineig < KLT_MIN_EIG * KLT_N * (FX_DETB == 2 ? det_scale : 1.0) || det <= 0) {')
# accepted-feature counter
rep('    *nrows += k0;\n    return 1;','    *nrows += k0; fx_used++;\n    return 1;')
# gate override inside vision after chi2_z set
rep('        chi2_z = fast ? FAST_CHI2_Z : CHI2_Z;','        chi2_z = fast ? FAST_CHI2_Z : CHI2_Z;\n        if (FX_GATEZ > 0 && fx_starved && FX_GATEZ > chi2_z) chi2_z = FX_GATEZ;')
rep('    vision(frame);\n    write_state(out);',
'''    fx_used = 0;
    vision(frame);
    if (FX_GATEZ > 0 || FX_INFL > 0) {
        fx_hist[fx_hp % 64] = fx_used; fx_hp++;
        int sum = 0, live3 = 0;
        for (int k = 1; k <= FX_WIN && k <= fx_hp; k++) sum += fx_hist[(fx_hp - k) % 64];
        for (int i = 0; i < MAX_TRACKS; i++) if (tracks[i].alive && tracks[i].obs.n >= MIN_OBS) live3++;
        fx_starved = moving && fx_hp >= FX_WIN && sum == 0 && live3 >= FX_LIVE3;
        if (FX_INFL > 0 && fx_starved && fx_hp % FX_WIN == 0)
            for (int k = 0; k < 3; k++) { Pm[(V + k) * MAXD + V + k] += FX_INFL * FX_INFL; Pm[(TH + k) * MAXD + TH + k] += 0.01 * FX_INFL * FX_INFL; }
    }
    write_state(out);''')
rep('        frame_no = 0; clone_every = CLONE_EVERY;','        fx_hp = 0; fx_starved = 0; memset(fx_hist, 0, sizeof fx_hist); det_scale = 1.0;\n        frame_no = 0; clone_every = CLONE_EVERY;')
open('fx.c','w').write(s)
