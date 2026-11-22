from pathlib import Path
w=Path(__file__).resolve().parent;s=(w/'lj.c').read_text()
a=s.index('static int update(const double *r, const double *H, int k, double noise, double gate) {');b=s.index('\nstatic ',a+20)
p=s[a:b]
p=p.replace('#if F_UPD\n    { /* Kt = S^-1 HP', '''#if F_UPD
#if LJ_FWD
    /* W=L^-1 HP; z=L^-1 r; dx=W^T z, P-=W^T W.
       Same EKF equations, no backward solve for each state column. */
    memcpy(y,r,k*sizeof(double));
    for(int i=0;i<k;i++){
        double z=y[i];for(int q=0;q<i;q++)z-=Sm[i*k+q]*y[q];y[i]=z/Sm[i*k+i];
    }
#endif
    { /* Kt = S^-1 HP''',1)
p=p.replace('        for (int i = k - 1; i >= 0; i--) {','        if (!LJ_FWD)\n        for (int i = k - 1; i >= 0; i--) {',1)
p=p.replace('wasm_f64x2_splat(r[a])','wasm_f64x2_splat(LJ_FWD ? y[a] : r[a])')
p=p.replace('*hpa = HP + a * MAXD;', '*hpa = (LJ_FWD ? Kt : HP) + a * MAXD;')
p=p.replace('wasm_f64x2_splat(HP[a * MAXD + i])','wasm_f64x2_splat((LJ_FWD ? Kt : HP)[a * MAXD + i])')
s=s[:a]+p+s[b:]
s=s.replace('#ifndef F_REUSE\n#define F_REUSE 0', '#ifndef LJ_FWD\n#define LJ_FWD 0\n#endif\n#ifndef F_REUSE\n#define F_REUSE 0',1)
(w/'lj.c').write_text(s)
