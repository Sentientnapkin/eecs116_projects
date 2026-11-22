from pathlib import Path
w=Path(__file__).resolve().parent;s=(w/'lj.c').read_text()
a=s.index('static int cholesky(double *A, int n) {');b=s.index('static void chol_solve',a);old=s[a:b]
new='''static int cholesky(double *A, int n) {
    /* Upper triangle stores a transposed copy of the computed lower factor.
       Four independent rows are vectorized; each dot keeps ascending k order. */
    for(int j=0;j<n;j++){
        double s=A[j*n+j];for(int k=0;k<j;k++)s-=A[j*n+k]*A[j*n+k];
        if(s<=1e-300)return 0;s=sqrt(s);A[j*n+j]=s;
        v128_t den=wasm_f64x2_splat(s);int i=j+1;
        for(;i+4<=n;i+=4){
            v128_t t0=wasm_f64x2_make(A[i*n+j],A[(i+1)*n+j]);
            v128_t t1=wasm_f64x2_make(A[(i+2)*n+j],A[(i+3)*n+j]);
            for(int k=0;k<j;k++){
                v128_t a=wasm_f64x2_splat(A[j*n+k]);
                t0=wasm_f64x2_sub(t0,wasm_f64x2_mul(wasm_v128_load(A+k*n+i),a));
                t1=wasm_f64x2_sub(t1,wasm_f64x2_mul(wasm_v128_load(A+k*n+i+2),a));
            }
            t0=wasm_f64x2_div(t0,den);t1=wasm_f64x2_div(t1,den);
            wasm_v128_store(A+j*n+i,t0);wasm_v128_store(A+j*n+i+2,t1);
            A[i*n+j]=wasm_f64x2_extract_lane(t0,0);A[(i+1)*n+j]=wasm_f64x2_extract_lane(t0,1);
            A[(i+2)*n+j]=wasm_f64x2_extract_lane(t1,0);A[(i+3)*n+j]=wasm_f64x2_extract_lane(t1,1);
        }
        for(;i<n;i++){
            double t=A[i*n+j];for(int k=0;k<j;k++)t-=A[i*n+k]*A[j*n+k];
            A[i*n+j]=t/s;A[j*n+i]=A[i*n+j];
        }
    }
    return 1;
}
'''
s=s[:a]+'#ifndef LJ_CHOL\n#define LJ_CHOL 0\n#endif\n#if LJ_CHOL\n'+new+'#else\n'+old+'#endif\n'+s[b:]
(w/'lj.c').write_text(s)
