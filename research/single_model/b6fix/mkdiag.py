import re,sys
s=open('../frontend/adopted_fbh.c').read()
def rep(a,b,cnt=1):
    global s
    assert s.count(a)==cnt,(a,s.count(a)); s=s.replace(a,b)
rep('static Obs batch[MAX_BATCH];','static Obs batch[MAX_BATCH];',1) if False else None
rep('static double tri_min_eig = TRI_MIN_EIG, t_start, chi2_z = 1.645;','static double tri_min_eig = TRI_MIN_EIG, t_start, chi2_z = 1.645;\nstatic int dg_frame,dg_kltfail,dg_fbchk,dg_fbdrop,dg_tri,dg_gate,dg_used,dg_att;')
# counters after Track definitions: put before track_all
rep('static void track_all(int prev, int cur, const double *Rwc_now) {',
 '#ifndef FB_ON\n#define FB_ON 1\n#endif\nstatic void track_all(int prev, int cur, const double *Rwc_now) {')
rep('        if (ok && ((frame_no + i) & 1)) {','        if (!ok) dg_kltfail++;\n        if (FB_ON && ok && ((frame_no + i) & 1)) {\n            dg_fbchk++;')
rep('> 0.25) ok = 0;','> 0.25) { ok = 0; dg_fbdrop++; }')
# feature_rows counters: failing triangulate & gate
rep('    if (!triangulate(&o, ci, pf)) return 0;','    dg_att++;\n    if (!triangulate(&o, ci, pf)) { dg_tri++; return 0; }')
rep('    if (m2 > gq) { if (INV_HUBER > 0 && m2 < INV_HUBER * gq) hw = sqrt(gq / m2); else return 0; }','    if (m2 > gq) { if (INV_HUBER > 0 && m2 < INV_HUBER * gq) hw = sqrt(gq / m2); else { dg_gate++; return 0; } }')
rep('    *nrows += k0;\n    return 1;','    *nrows += k0; dg_used++;\n    return 1;')
rep('    vision(frame);\n    write_state(out);',
'''    dg_kltfail=dg_fbchk=dg_fbdrop=dg_tri=dg_gate=dg_used=dg_att=0;
    vision(frame);
    dg_frame++;
    { int live=0,live3=0; for (int i=0;i<MAX_TRACKS;i++) if (tracks[i].alive){live++; if(tracks[i].obs.n>=MIN_OBS) live3++;}
      fprintf(stderr,"D f=%d t=%.2f live=%d live3=%d nc=%d kf=%d fbc=%d fbd=%d att=%d tri=%d gate=%d used=%d mov=%d rel=%d v=%.3f,%.3f,%.3f p=%.3f,%.3f,%.3f Pv=%.4f Pth=%.4f\\n",
        dg_frame,t,live,live3,nclones,dg_kltfail,dg_fbchk,dg_fbdrop,dg_att,dg_tri,dg_gate,dg_used,moving,gate_released,vel[0],vel[1],vel[2],pos[0],pos[1],pos[2],
        sqrt(Pm[V*MAXD+V]+Pm[(V+1)*MAXD+V+1]+Pm[(V+2)*MAXD+V+2]),sqrt(Pm[TH*MAXD+TH]+Pm[(TH+1)*MAXD+TH+1]+Pm[(TH+2)*MAXD+TH+2])); }
    write_state(out);''')
open('diag.c','w').write(s)
