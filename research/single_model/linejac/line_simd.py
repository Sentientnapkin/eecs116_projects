from pathlib import Path
w=Path(__file__).resolve().parent
s=(w/'lj.c').read_text()
a=s.index('static int line_rows(')
start='''        for (int a = 0; a < k0; a++)
            for (int jj = 0; jj < nnz; jj++) {'''
i=s.index(start,a);j=s.index('        for (int a = 0; a < k0; a++)\n            for (int b = 0; b <= a; b++)',i)
old=s[i:j]
new='''        /* nzc contains contiguous six-column clone blocks. SIMD along output
           columns preserves the scalar accumulation order over q exactly. */
        for(int a=0;a<k0;a++)for(int jj=0;jj<nnz;jj+=6){
            int j=nzc[jj];v128_t v0=wasm_f64x2_splat(0),v1=v0,v2=v0;
            for(int q=0;q<nnz;q++){
                v128_t h=wasm_f64x2_splat(H0[a*MAXD+nzc[q]]);
                const double *p=Pm+nzc[q]*MAXD+j;
                v0=wasm_f64x2_add(v0,wasm_f64x2_mul(h,wasm_v128_load(p)));
                v1=wasm_f64x2_add(v1,wasm_f64x2_mul(h,wasm_v128_load(p+2)));
                v2=wasm_f64x2_add(v2,wasm_f64x2_mul(h,wasm_v128_load(p+4)));
            }
            double *p=H0P+a*MAXD+j;wasm_v128_store(p,v0);wasm_v128_store(p+2,v1);wasm_v128_store(p+4,v2);
        }
'''
s=s[:i]+'#if EDGE_ASIMD\n'+new+'#else\n'+old+'#endif\n'+s[j:]
# SIMD along row b of S; transpose the sparse H0 once.
i=s.index('        for (int a = 0; a < k0; a++)\n            for (int b = 0; b <= a; b++)',a);j=s.index('        if (!cholesky(Sm, k0))',i);old=s[i:j]
new='''        double ht[6*MAX_OBS][2*MAX_OBS+2];
        for(int q=0;q<nnz;q++){
            for(int b=0;b<k0;b++)ht[q][b]=H0[b*MAXD+nzc[q]];
            ht[q][k0]=0;
        }
        for(int a=0;a<k0;a++)for(int b=0;b<=a;b+=2){
            v128_t v=wasm_f64x2_splat(0);
            for(int q=0;q<nnz;q++)v=wasm_f64x2_add(v,wasm_f64x2_mul(wasm_f64x2_splat(H0P[a*MAXD+nzc[q]]),wasm_v128_load(ht[q]+b)));
            double tmp[2];wasm_v128_store(tmp,v);
            for(int t=0;t<2 && b+t<=a;t++)Sm[a*k0+b+t]=Sm[(b+t)*k0+a]=tmp[t]+(a==b+t?sigma2:0);
        }
'''
s=s[:i]+'#if EDGE_ASIMD\n'+new+'#else\n'+old+'#endif\n'+s[j:]
# Null space pose reflection: operate on each six-column clone block.
i=s.index('        for (int jj = 0; jj < nnz; jj++) {\n            int j = nzc[jj]; double s = 0;',a);j=s.index('        double s = 0;\n        for (int i = c; i < nr; i++) s += v[i] * rr[i];',i);old=s[i:j]
new='''        for(int jj=0;jj<nnz;jj+=6){
            int j=nzc[jj];v128_t s0=wasm_f64x2_splat(0),s1=s0,s2=s0;
            for(int i=c;i<nr;i++){
                v128_t vi=wasm_f64x2_splat(v[i]);const double *h=Hx+i*MAXD+j;
                s0=wasm_f64x2_add(s0,wasm_f64x2_mul(vi,wasm_v128_load(h)));
                s1=wasm_f64x2_add(s1,wasm_f64x2_mul(vi,wasm_v128_load(h+2)));
                s2=wasm_f64x2_add(s2,wasm_f64x2_mul(vi,wasm_v128_load(h+4)));
            }
            v128_t scale=wasm_f64x2_splat(2/vn);
            s0=wasm_f64x2_mul(s0,scale);s1=wasm_f64x2_mul(s1,scale);s2=wasm_f64x2_mul(s2,scale);
            for(int i=c;i<nr;i++){
                v128_t vi=wasm_f64x2_splat(v[i]);double *h=Hx+i*MAXD+j;
                wasm_v128_store(h,wasm_f64x2_sub(wasm_v128_load(h),wasm_f64x2_mul(s0,vi)));
                wasm_v128_store(h+2,wasm_f64x2_sub(wasm_v128_load(h+2),wasm_f64x2_mul(s1,vi)));
                wasm_v128_store(h+4,wasm_f64x2_sub(wasm_v128_load(h+4),wasm_f64x2_mul(s2,vi)));
            }
        }
'''
s=s[:i]+'#if EDGE_ASIMD\n'+new+'#else\n'+old+'#endif\n'+s[j:]
s=s.replace('#ifndef EDGE_AJAC','#ifndef EDGE_ASIMD\n#define EDGE_ASIMD 0\n#endif\n#ifndef EDGE_AJAC',1)
(w/'lj.c').write_text(s)
