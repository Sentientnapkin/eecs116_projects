/* host test driver for lc_core.h: reads dump files (see parity.py), writes lc_in / lc_vec / lc_out per sample. gcc -O2 -I<weights dir> lc_test.c -lm */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#define MAXD 64
#define V 3
static double fx, fy, cx, cy, R_bc[9], R[9] = {1, 0, 0, 0, 1, 0, 0, 0, 1}, vel[3], Hs[3 * MAXD];
static void m3mul(const double *a, const double *b, double *c) { for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) { double s = 0; for (int k = 0; k < 3; k++) s += a[3 * i + k] * b[3 * k + j]; c[3 * i + j] = s; } }
static void m3tmul(const double *a, const double *b, double *c) { for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) { double s = 0; for (int k = 0; k < 3; k++) s += a[3 * k + i] * b[3 * k + j]; c[3 * i + j] = s; } }
static int update(const double *r, const double *H, int k, double noise, double gate) { (void)r; (void)H; (void)k; (void)noise; (void)gate; return 1; }
#ifndef LC_CORE_H
#define LC_CORE_H "lc_core.h"
#endif
#include LC_CORE_H
#ifdef LC_NN
#define LC_OUT0 lc_out[0]
#else
#define LC_OUT0 lc_out
#endif
static uint8_t frames[6][240 * 320 * 3]; static double imu[6][400 * 7]; static int nimu[6];
int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb"), *o = fopen(argv[2], "wb"); int ns; fread(&ns, 4, 1, f);
    for (int s = 0; s < ns; s++) {
        double hdr[12]; fread(hdr, 8, 12, f); fx = hdr[0]; fy = hdr[0]; cx = hdr[1]; cy = hdr[2]; memcpy(R_bc, hdr + 3, 72);
        for (int k = 0; k < 6; k++) { fread(frames[k], 1, 240 * 320 * 3, f); fread(&nimu[k], 4, 1, f); fread(imu[k], 8, nimu[k] * 7, f); }
        lc_begin(frames[0], imu[0], nimu[0]);
        for (int k = 1; k <= 5; k++) lc_step(frames[k], imu[k], nimu[k]);
        for (int k = 6; k <= 9; k++) lc_step(frames[5], imu[5], 0); /* later stages of the staged forward pass */
#ifdef LC_NN
        if (LC_NN > 1) { double mq[3], vq[3]; lc_combine(mq, vq); for (int i = 0; i < 3; i++) { lc_out[0][6 + i] = (float)mq[i]; lc_out[0][9 + i] = (float)log(vq[i]); } }
#endif
        fwrite(lc_in, 4, LC_PH * LC_PW * 5, o); fwrite(lc_vec, 4, 19, o); fwrite(LC_OUT0, 4, 12, o);
        fwrite(lc_g0, 1, LC_H * LC_W, o); fwrite(lc_g5, 1, LC_H * LC_W, o);
    }
    return 0;
}
