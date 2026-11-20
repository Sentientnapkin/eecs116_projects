s=open('../b6fix/diag.c').read()
def rep(a,b):
    global s
    assert s.count(a)==1,(a,s.count(a)); s=s.replace(a,b)
rep('static int dg_frame,','static double dg_nis,dg_nisk,dg_nisn,dg_pn,dg_pk,dg_fn,dg_fs; static int dg_ctx;\nstatic int dg_frame,')
rep('    for (int a = 0; a < k; a++) m2 += r[a] * y[a];\n    if (m2 > gate) return 0;',
    '    for (int a = 0; a < k; a++) m2 += r[a] * y[a];\n    if (dg_ctx==1) { dg_nis += m2; dg_nisk += k; dg_nisn++; } else if (dg_ctx==2) { dg_pn += m2; dg_pk += k; }\n    if (m2 > gate) return 0;')
rep('    update(rbig, Hbig, nrows, (PIXEL_STD / fx) * (PIXEL_STD / fx), INFINITY);','    dg_ctx=1; update(rbig, Hbig, nrows, (PIXEL_STD / fx) * (PIXEL_STD / fx), INFINITY); dg_ctx=0;')
rep('        update(r, Hs, 3, 1.0, PRIOR_GATE);\n        return;','        dg_ctx=2; update(r, Hs, 3, 1.0, PRIOR_GATE); dg_ctx=0;\n        return;')
rep('    double gq = chi2_quantile(k0), hw = 1.0;','    double gq = chi2_quantile(k0), hw = 1.0;\n    dg_fs += m2 / k0; dg_fn += 1;')
rep('dg_frame++;','dg_frame++; fprintf(stderr,"M f=%d nis=%.3f nisk=%.0f nisn=%.0f pn=%.3f pk=%.0f fs=%.3f fn=%.0f\\n",dg_frame,dg_nis,dg_nisk,dg_nisn,dg_pn,dg_pk,dg_fs,dg_fn); dg_nis=dg_nisk=dg_nisn=dg_pn=dg_pk=dg_fs=dg_fn=0;')
open('dbg.c','w').write(s)
