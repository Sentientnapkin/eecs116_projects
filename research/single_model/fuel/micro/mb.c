#include <stdint.h>
#include <math.h>
#include <wasm_simd128.h>
#include "viobench_abi.h"
#ifndef N
#define N 100000
#endif
static double buf[4096]; static float fbuf[4096]; static int32_t ibuf[4096];
VIOBENCH_EXPORT(abi_version) int32_t abi_version(void){return 1;}
static char heap[1<<16];
VIOBENCH_EXPORT(alloc) void*alloc(uint32_t s){static uint32_t o=0;void*p=heap+o;o+=(s+15)&~15u;return p;}
VIOBENCH_EXPORT(init) int32_t init(const char*c,uint32_t l){for(int i=0;i<4096;i++){buf[i]=1.0+i*1e-3;fbuf[i]=1.0f+i*1e-3f;ibuf[i]=i+1;}return 0;}
VIOBENCH_EXPORT(step) int32_t step(double t,const uint8_t*f,const double*imu,int32_t n,double*out){
  volatile int k = KERNEL; (void)k;
  double a=1.0,b=1.0000001; float fa=1.f,fb=1.0000001f; int32_t ia=1; double acc=0;
#if KERNEL==0
  /* empty */
#elif KERNEL==1  /* dependent f64 add chain */
  for(int i=0;i<N;i++) a+=b;
  acc=a;
#elif KERNEL==2  /* f64 div chain */
  for(int i=0;i<N;i++) a=b/a;
  acc=a;
#elif KERNEL==3  /* f64 sqrt chain */
  for(int i=0;i<N;i++) a=sqrt(a+b);
  acc=a;
#elif KERNEL==4  /* libm sin chain (call into wasm-compiled libm) */
  for(int i=0;i<N;i++) a=sin(a)+b;
  acc=a;
#elif KERNEL==5  /* f64x2 simd add chain */
  v128_t v=wasm_f64x2_splat(1.0), w=wasm_f64x2_splat(1.0000001);
  for(int i=0;i<N;i++) v=wasm_f64x2_add(v,w);
  acc=wasm_f64x2_extract_lane(v,0);
#elif KERNEL==6  /* memory load+add (f64) */
  for(int i=0;i<N;i++) a+=buf[i&4095];
  acc=a;
#elif KERNEL==7  /* f32 add chain */
  for(int i=0;i<N;i++) fa+=fb;
  acc=fa;
#elif KERNEL==8  /* int add chain */
  for(int i=0;i<N;i++) ia=ia*3+i;
  acc=ia;
#elif KERNEL==9  /* i32x4 simd mul-add chain: 4 lanes per instruction */
  v128_t v=wasm_i32x4_splat(1), w=wasm_i32x4_splat(3);
  for(int i=0;i<N;i++) v=wasm_i32x4_add(wasm_i32x4_mul(v,w),w);
  acc=wasm_i32x4_extract_lane(v,0);
#elif KERNEL==10 /* f32x4 simd add chain */
  v128_t v=wasm_f32x4_splat(1.f), w=wasm_f32x4_splat(1.0000001f);
  for(int i=0;i<N;i++) v=wasm_f32x4_add(v,w);
  acc=wasm_f32x4_extract_lane(v,0);
#elif KERNEL==11 /* f64 mul chain */
  for(int i=0;i<N;i++) a*=b;
  acc=a;
#elif KERNEL==12 /* memory store+load roundtrip */
  for(int i=0;i<N;i++){ buf[i&4095]=a; a=buf[(i+1)&4095]+b; }
  acc=a;
#endif
  out[0]=acc; for(int i=1;i<13;i++) out[i]=0; out[6]=1; (void)ibuf;(void)fbuf;
  return 0;}
