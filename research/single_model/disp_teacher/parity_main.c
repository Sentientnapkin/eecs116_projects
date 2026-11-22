/* parity test: stdin-free WASI command. reads in.bin, writes out.bin.
 * in.bin per case: 3*96*128 uint8 (cur, mid, far raw gray), 2*9 double Hinv (mid, far), 10 float aux
 * out.bin per case: 12 float outputs, then 2*2*96*128 float (warped mid img, mask, far img, mask) */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#define DT_NET_ONLY 1
#include "dt_weights.h"
#include "dt_core.h"

int main(void) {
    FILE *f = fopen("in.bin", "rb"), *g = fopen("out.bin", "wb");
    if (!f || !g) return 1;
    static uint8_t im[3][DT_W * DT_H]; double H[2][9]; float aux[10], o[12];
    while (fread(im, 1, sizeof im, f) == sizeof im) {
        if (fread(H, sizeof(double), 18, f) != 18 || fread(aux, sizeof(float), 10, f) != 10) return 2;
        for (int i = 0; i < DT_W * DT_H; i++) { dt_in[0][i] = im[0][i] / 255.0f; dt_in[0][DT_W * DT_H + i] = 1.0f; }
        dt_warp(im[1], H[0], dt_in[1]);
        dt_warp(im[2], H[1], dt_in[2]);
        dt_forward(aux, o);
        fwrite(o, sizeof(float), 12, g);
        fwrite(dt_in[1], sizeof(float), 2 * DT_W * DT_H, g);
        fwrite(dt_in[2], sizeof(float), 2 * DT_W * DT_H, g);
    }
    fclose(g);
    return 0;
}
