/* native stub replacing the learned net: returns GT body velocity at epoch + noise (set from python) */
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <stdlib.h>
static int lc_have_row, ns_have5, nt_frame, nt_pos;
static uint8_t sn_g0[1], sn_g5[1]; static float lc_fm[2][1], lc_gm[2][1]; static double lc_Rs[9], lc_R5[9], lc_Vs[3], lc_V5[3];
#define NET_K 5
double stub_v[3]; /* set by python each frame: body-frame GT velocity (IMU body) */
double stub_noise=0.44; static double mu_[3];
static unsigned rs=12345; static double rn(void){double s=0;for(int i=0;i<12;i++){rs=rs*1664525u+1013904223u;s+=(rs>>8)/16777216.0;}return s-6.0;}
static void sn_gray(const uint8_t*f,uint8_t*g){(void)f;(void)g;}
static void sn_setup(void){} static void sn_step(int u){(void)u;} static void sn_head(int a,int b){(void)a;(void)b;}
void net_cam(double a,double b,double c,const double*R){(void)a;(void)b;(void)c;(void)R;}
void net_begin(const uint8_t*f,const double*i,int n){(void)f;(void)i;(void)n;nt_frame=0;}
int net_feed(const uint8_t*f,const double*i,int n){(void)f;(void)i;(void)n;if(nt_frame>=NET_K)return 0;nt_frame++; if(nt_frame==NET_K){memcpy(mu_,stub_v,24);for(int k=0;k<3;k++)mu_[k]+=stub_noise*rn();return 1;}return 0;}
void net_out(double*mu,double*lv){memcpy(mu,mu_,24);lv[0]=lv[1]=lv[2]=0;}
