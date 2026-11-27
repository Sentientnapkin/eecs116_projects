
#include <stdint.h>
#include <string.h>
#include <wasm_simd128.h>
static void conv_f32(const float *in, float *out, const float *w, const float *b, int H, int W, int CI, int CO, int s) {
  int OH = (H - 3) / s + 1, OW = (W - 3) / s + 1;
  for (int oy = 0; oy < OH; oy++) for (int ox = 0; ox < OW; ox++) for (int oc = 0; oc < CO; oc += 16) {
    v128_t a0 = wasm_v128_load(b + oc), a1 = wasm_v128_load(b + oc + 4), a2 = wasm_v128_load(b + oc + 8), a3 = wasm_v128_load(b + oc + 12);
    for (int ky = 0; ky < 3; ky++) for (int kx = 0; kx < 3; kx++) {
      const float *ip = in + ((oy * s + ky) * W + ox * s + kx) * CI; const float *wp = w + ((ky * 3 + kx) * CI) * CO + oc;
      for (int ic = 0; ic < CI; ic++, wp += CO) { v128_t v = wasm_v128_load32_splat(ip + ic);
        a0 = wasm_f32x4_add(a0, wasm_f32x4_mul(v, wasm_v128_load(wp))); a1 = wasm_f32x4_add(a1, wasm_f32x4_mul(v, wasm_v128_load(wp + 4)));
        a2 = wasm_f32x4_add(a2, wasm_f32x4_mul(v, wasm_v128_load(wp + 8))); a3 = wasm_f32x4_add(a3, wasm_f32x4_mul(v, wasm_v128_load(wp + 12))); } }
    v128_t z = wasm_f32x4_splat(0); float *op = out + (oy * OW + ox) * CO + oc;
    wasm_v128_store(op, wasm_f32x4_max(a0, z)); wasm_v128_store(op + 4, wasm_f32x4_max(a1, z)); wasm_v128_store(op + 8, wasm_f32x4_max(a2, z)); wasm_v128_store(op + 12, wasm_f32x4_max(a3, z)); }
}
static inline int32_t hsum(v128_t a) { return wasm_i32x4_extract_lane(a, 0) + wasm_i32x4_extract_lane(a, 1) + wasm_i32x4_extract_lane(a, 2) + wasm_i32x4_extract_lane(a, 3); }
/* weights per oc contiguous over (ky,kx,ic) */
static void conv_i16(const int16_t *in, int16_t *out, const int16_t *w, const int32_t *b, int H, int W, int CI, int CO, int s) {
  int OH = (H - 3) / s + 1, OW = (W - 3) / s + 1, K = 9 * CI;
  for (int oy = 0; oy < OH; oy++) for (int ox = 0; ox < OW; ox++) for (int oc = 0; oc < CO; oc += 4) {
    v128_t a0 = wasm_i32x4_splat(0), a1 = a0, a2 = a0, a3 = a0; const int16_t *w0 = w + oc * K;
    for (int ky = 0; ky < 3; ky++) for (int kx = 0; kx < 3; kx++) {
      const int16_t *ip = in + ((oy * s + ky) * W + ox * s + kx) * CI; int o = (ky * 3 + kx) * CI;
      for (int ic = 0; ic < CI; ic += 8) { v128_t v = wasm_v128_load(ip + ic);
        a0 = wasm_i32x4_add(a0, wasm_i32x4_dot_i16x8(v, wasm_v128_load(w0 + o + ic))); a1 = wasm_i32x4_add(a1, wasm_i32x4_dot_i16x8(v, wasm_v128_load(w0 + K + o + ic)));
        a2 = wasm_i32x4_add(a2, wasm_i32x4_dot_i16x8(v, wasm_v128_load(w0 + 2 * K + o + ic))); a3 = wasm_i32x4_add(a3, wasm_i32x4_dot_i16x8(v, wasm_v128_load(w0 + 3 * K + o + ic))); } }
    int16_t *op = out + (oy * OW + ox) * CO + oc; int32_t r;
    r = (hsum(a0) + b[oc]) >> 8; op[0] = r < 0 ? 0 : r > 32767 ? 32767 : r; r = (hsum(a1) + b[oc + 1]) >> 8; op[1] = r < 0 ? 0 : r > 32767 ? 32767 : r;
    r = (hsum(a2) + b[oc + 2]) >> 8; op[2] = r < 0 ? 0 : r > 32767 ? 32767 : r; r = (hsum(a3) + b[oc + 3]) >> 8; op[3] = r < 0 ? 0 : r > 32767 ? 32767 : r; }
}
#ifdef RELAXED
static void conv_i8r(const int8_t *in, int8_t *out, const int8_t *w, const int32_t *b, int H, int W, int CI, int CO, int s) {
  int OH = (H - 3) / s + 1, OW = (W - 3) / s + 1, K = 9 * CI;
  for (int oy = 0; oy < OH; oy++) for (int ox = 0; ox < OW; ox++) for (int oc = 0; oc < CO; oc += 4) {
    v128_t a0 = wasm_i32x4_splat(0), a1 = a0, a2 = a0, a3 = a0; const int8_t *w0 = w + oc * K;
    for (int ky = 0; ky < 3; ky++) for (int kx = 0; kx < 3; kx++) {
      const int8_t *ip = in + ((oy * s + ky) * W + ox * s + kx) * CI; int o = (ky * 3 + kx) * CI;
      for (int ic = 0; ic < CI; ic += 16) { v128_t v = wasm_v128_load(ip + ic);
        a0 = wasm_i32x4_relaxed_dot_i8x16_i7x16_add(v, wasm_v128_load(w0 + o + ic), a0); a1 = wasm_i32x4_relaxed_dot_i8x16_i7x16_add(v, wasm_v128_load(w0 + K + o + ic), a1);
        a2 = wasm_i32x4_relaxed_dot_i8x16_i7x16_add(v, wasm_v128_load(w0 + 2 * K + o + ic), a2); a3 = wasm_i32x4_relaxed_dot_i8x16_i7x16_add(v, wasm_v128_load(w0 + 3 * K + o + ic), a3); } }
    int8_t *op = out + (oy * OW + ox) * CO + oc; int32_t r;
    r = (hsum(a0) + b[oc]) >> 7; op[0] = r < 0 ? 0 : r > 127 ? 127 : r; r = (hsum(a1) + b[oc + 1]) >> 7; op[1] = r < 0 ? 0 : r > 127 ? 127 : r;
    r = (hsum(a2) + b[oc + 2]) >> 7; op[2] = r < 0 ? 0 : r > 127 ? 127 : r; r = (hsum(a3) + b[oc + 3]) >> 7; op[3] = r < 0 ? 0 : r > 127 ? 127 : r; }
}
#endif

static float A[196608], B[196608]; static float Wt[294912]; static float Bs[480];
__attribute__((export_name("init"))) void init(void) { uint32_t s = 1; for (int i = 0; i < (int)(sizeof Wt / sizeof Wt[0]); i++) { s = s * 1103515245u + 12345u; Wt[i] = (float)((int)(s >> 24) - 128) * 0.003f; }
  for (int i = 0; i < (int)(sizeof A / sizeof A[0]); i++) { s = s * 1103515245u + 12345u; A[i] = (float)((s >> 25)); } }
__attribute__((export_name("run"))) void run(void) {
  conv_f32(A, B, Wt + 0, Bs + 0, 96, 128, 16, 16, 1);
  conv_f32(B, A, Wt + 2304, Bs + 16, 94, 126, 16, 16, 1);
  conv_f32(A, B, Wt + 4608, Bs + 32, 92, 124, 16, 32, 2);
  conv_f32(B, A, Wt + 9216, Bs + 64, 45, 61, 32, 32, 1);
  conv_f32(A, B, Wt + 18432, Bs + 96, 43, 59, 32, 64, 2);
  conv_f32(B, A, Wt + 36864, Bs + 160, 21, 29, 64, 64, 1);
  conv_f32(A, B, Wt + 73728, Bs + 224, 19, 27, 64, 128, 2);
  conv_f32(B, A, Wt + 147456, Bs + 352, 9, 13, 128, 128, 1);
}
int main(void) { return 0; }