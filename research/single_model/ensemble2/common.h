#ifndef ENS2_COMMON_H
#define ENS2_COMMON_H
#include <stdint.h>
#ifndef ENS2_PROFILE
#define ENS2_PROFILE 0
#endif
#ifndef ENS2_CAP
#define ENS2_CAP 5000000
#endif
#ifndef ENS2_SYNC
#define ENS2_SYNC 0
#endif
#ifndef ENS2_PIXEL
#define ENS2_PIXEL 1.515
#endif
#define ENS2_RING 16
#define ENS2_IMU 4096
/* Observations belong to each filter. Only image-space tracking is shared. */
typedef struct { int alive; double x,y,dx,dy; } EnsPoint;
typedef struct { int alive,pol; double x[3],y[3],nx[3],ny[3],con[3]; int sal[3]; } EnsLine;
typedef struct {
    double t, primary[13]; int count, sequence, tracked, line_tracked, klt_calls, det_cells, line_detected;
    double imu[ENS2_IMU*7];
    uint8_t rgb[320*240*3], pyramid[2][320*240];
    EnsPoint points[60], born[60]; uint8_t point_new[60];
    EnsLine lines[32], line_born[32]; uint8_t line_new[32];
} EnsFrame;
extern EnsFrame *ens_frame;
extern double ens_cost;
extern int ens_role;
void ens_copy(void *dst,const void *src,uint32_t n);
void ens_meter(int job, int a, int b, int c);
void ens_meter_end(void);
void ens_meter_args(int a,int b,int c);
int ens_estimate(int job,int a,int b,int c);
int ens_bound(int job,int a,int b,int c);
int ens_primary_init(const char *,uint32_t);
int ens_primary_step(double,const uint8_t *,const double *,int32_t,double *);
int ens_secondary_init(const char *,uint32_t);
void ens_secondary_start(EnsFrame *);
int ens_secondary_tick(int budget);
void ens_secondary_output(double *);
int ens_secondary_need(void);
/* Profiling imports exist only in diagnostic builds. */
#if ENS2_PROFILE
__attribute__((import_module("env"),import_name("ens_mark")))
void ens_mark(int job,int a,int b,int c);
#else
#define ens_mark(j,a,b,c) ((void)0)
#endif
#endif
