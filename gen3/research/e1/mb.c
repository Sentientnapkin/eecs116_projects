#include <stdint.h>
#include <math.h>
#include <string.h>
static uint8_t F[240*320*3]; static double IMU[70]; static double Q[4]={1,0,0,0};
static float P[36], H[6], Kg[6], X[6];
static float Rm[9]={1,0,0,0,1,0,0,0,1}; static float vf[3];
static int32_t Ri[9]={65536,0,0,0,65536,0,0,0,65536}; static int32_t vi[3];
volatile int32_t sink; volatile float fs;
__attribute__((export_name("init"))) void init(void){ for(int i=0;i<sizeof F;i++)F[i]=(i*7919)>>5; for(int i=0;i<70;i++)IMU[i]=0.01*i; for(int i=0;i<36;i++)P[i]=(i%7==0); for(int i=0;i<6;i++)H[i]=0.1f*i; }
__attribute__((export_name("empty"))) void empty(void){ sink=1; }
/* A: 10 samples double, full exp rotation matrix (as base.c) */
static void rotd(double*R,const double*w,double dt){double a=sqrt(w[0]*w[0]+w[1]*w[1]+w[2]*w[2])*dt,s=sin(a)/a,c=(1-cos(a))/(a*a);double k[3]={w[0]*dt,w[1]*dt,w[2]*dt};
 double K[9]={0,-k[2],k[1],k[2],0,-k[0],-k[1],k[0],0},K2[9],E[9],N[9];for(int i=0;i<3;i++)for(int j=0;j<3;j++)K2[3*i+j]=K[3*i]*K[j]+K[3*i+1]*K[3+j]+K[3*i+2]*K[6+j];
 for(int i=0;i<9;i++)E[i]=(i%4==0)+s*K[i]+c*K2[i];for(int i=0;i<3;i++)for(int j=0;j<3;j++)N[3*i+j]=R[3*i]*E[j]+R[3*i+1]*E[3+j]+R[3*i+2]*E[6+j];memcpy(R,N,sizeof N);}
static double Rd[9]={1,0,0,0,1,0,0,0,1}, vd[3];
__attribute__((export_name("imu_dbl_exp"))) void a(void){for(int r=0;r<10;r++){const double*q=IMU+7*r;double w[3]={q[4],q[5],q[6]};rotd(Rd,w,0.005);
 for(int i=0;i<3;i++){double aw=Rd[3*i]*q[1]+Rd[3*i+1]*q[2]+Rd[3*i+2]*q[3];vd[i]+=aw*0.005;}}}
/* B: 10 samples float, first-order rotation + one renorm per frame, double->float reads */
__attribute__((export_name("imu_f32_fo"))) void b(void){for(int r=0;r<10;r++){const double*q=IMU+7*r;float wx=q[4]*.005f,wy=q[5]*.005f,wz=q[6]*.005f;
 float R0[9];memcpy(R0,Rm,36);
 for(int i=0;i<3;i++){Rm[3*i]=R0[3*i]+R0[3*i+1]*wz-R0[3*i+2]*wy;Rm[3*i+1]=R0[3*i+1]-R0[3*i]*wz+R0[3*i+2]*wx;Rm[3*i+2]=R0[3*i+2]+R0[3*i]*wy-R0[3*i+1]*wx;}
 for(int i=0;i<3;i++){float aw=Rm[3*i]*q[1]+Rm[3*i+1]*q[2]+Rm[3*i+2]*q[3];vf[i]+=aw*.005f;}}
 /* renorm rows once (approx) */
 for(int i=0;i<3;i++){float n=Rm[3*i]*Rm[3*i]+Rm[3*i+1]*Rm[3*i+1]+Rm[3*i+2]*Rm[3*i+2];float s=1.5f-0.5f*n;for(int j=0;j<3;j++)Rm[3*i+j]*=s;}}
/* B2: frame-averaged: sum 10 gyro/accel samples, one rotation update with mean omega (cheap) */
__attribute__((export_name("imu_f32_avg"))) void b2(void){float s[6]={0,0,0,0,0,0};for(int r=0;r<10;r++){const double*q=IMU+7*r;for(int i=0;i<6;i++)s[i]+=q[1+i];}
 float wx=s[3]*.005f,wy=s[4]*.005f,wz=s[5]*.005f;float R0[9];memcpy(R0,Rm,36);
 for(int i=0;i<3;i++){Rm[3*i]=R0[3*i]+R0[3*i+1]*wz-R0[3*i+2]*wy;Rm[3*i+1]=R0[3*i+1]-R0[3*i]*wz+R0[3*i+2]*wx;Rm[3*i+2]=R0[3*i+2]+R0[3*i]*wy-R0[3*i+1]*wx;}
 for(int i=0;i<3;i++){float aw=Rm[3*i]*s[0]+Rm[3*i+1]*s[1]+Rm[3*i+2]*s[2];vf[i]+=aw*.005f;}}
/* C: fixed point 10 samples (Q16 matrix, int gyro) */
__attribute__((export_name("imu_fixed"))) void c(void){for(int r=0;r<10;r++){const double*q=IMU+7*r;int32_t wx=(int32_t)(q[4]*327.68),wy=(int32_t)(q[5]*327.68),wz=(int32_t)(q[6]*327.68);
 int32_t R0[9];memcpy(R0,Ri,36);
 for(int i=0;i<3;i++){Ri[3*i]=R0[3*i]+(int32_t)(((int64_t)R0[3*i+1]*wz-(int64_t)R0[3*i+2]*wy)>>16);Ri[3*i+1]=R0[3*i+1]+(int32_t)(((int64_t)R0[3*i+2]*wx-(int64_t)R0[3*i]*wz)>>16);Ri[3*i+2]=R0[3*i+2]+(int32_t)(((int64_t)R0[3*i]*wy-(int64_t)R0[3*i+1]*wx)>>16);}
 for(int i=0;i<3;i++){int32_t aw=(int32_t)(((int64_t)Ri[3*i]*(int32_t)(q[1]*256)+(int64_t)Ri[3*i+1]*(int32_t)(q[2]*256)+(int64_t)Ri[3*i+2]*(int32_t)(q[3]*256))>>16);vi[i]+=aw;}}}
/* D: read 64 pixels strided, G channel */
__attribute__((export_name("read64px"))) void d(void){int s=0;for(int i=0;i<64;i++){s+=F[((i*29)%240*320+(i*37)%320)*3+1];}sink=s;}
/* E: gray of 8x8 patch (G channel) copy to buffer; at a position */
static uint8_t Pt[64];
__attribute__((export_name("patch8copy"))) void e(void){const uint8_t*p=F+(100*320+150)*3+1;for(int y=0;y<8;y++)for(int x=0;x<8;x++)Pt[y*8+x]=p[(y*320+x)*3];}
/* F: SSD of 8x8 patch template over 3x3 integer search (9 positions, G channel) */
__attribute__((export_name("ssd8x8_3x3"))) void f(void){int best=1<<30,bi=0;for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++){const uint8_t*p=F+((100+dy)*320+150+dx)*3+1;int s=0;for(int y=0;y<8;y++)for(int x=0;x<8;x++){int d=p[(y*320+x)*3]-Pt[y*8+x];s+=d*d;}if(s<best){best=s;bi=dy*3+dx;}}sink=bi;}
/* G: one Lucas-Kanade iteration on 7x7 window (gradients central, float), 2x2 solve */
__attribute__((export_name("lk7x7_iter"))) void g(void){float gxx=0,gxy=0,gyy=0,bx=0,by=0;const uint8_t*p=F+(100*320+150)*3+1;for(int y=1;y<8;y++)for(int x=1;x<8;x++){const uint8_t*q=p+(y*320+x)*3;float ix=(q[3]-q[-3])*.5f,iy=(q[960]-q[-960])*.5f,it=q[0]-Pt[((y-1)&7)*8+((x-1)&7)];gxx+=ix*ix;gxy+=ix*iy;gyy+=iy*iy;bx+=ix*it;by+=iy*it;}
 float det=gxx*gyy-gxy*gxy+1e-3f;fs=(gyy*bx-gxy*by)/det+(gxx*by-gxy*bx)/det;}
/* H: 6-state EKF scalar update (P 6x6 float): K=PH'/(HPH'+r), x+=K y, P-=K H P */
__attribute__((export_name("ekf6_scalar"))) void h(void){float PH[6];for(int i=0;i<6;i++){float s=0;for(int j=0;j<6;j++)s+=P[6*i+j]*H[j];PH[i]=s;}float S=1e-2f;for(int i=0;i<6;i++)S+=H[i]*PH[i];float is=1.f/S;for(int i=0;i<6;i++)Kg[i]=PH[i]*is;float y=0.3f;for(int i=0;i<6;i++)X[i]+=Kg[i]*y;for(int i=0;i<6;i++)for(int j=0;j<6;j++)P[6*i+j]-=Kg[i]*PH[j];}
/* I: covariance propagate 6x6 P = F P F' + Q with F=I+A (sparse ignored: dense 6x6 matmul x2) */
__attribute__((export_name("cov6_prop"))) void ii(void){static float Fm[36],T[36];for(int i=0;i<36;i++)Fm[i]=(i%7==0)+0.001f*i;for(int i=0;i<6;i++)for(int j=0;j<6;j++){float s=0;for(int k=0;k<6;k++)s+=Fm[6*i+k]*P[6*k+j];T[6*i+j]=s;}for(int i=0;i<6;i++)for(int j=0;j<6;j++){float s=0;for(int k=0;k<6;k++)s+=T[6*i+k]*Fm[6*j+k];P[6*i+j]=s+(i==j)*1e-6f;}}
/* J: write out[13] pose conversion: rotation->quaternion (float sqrt) + frame change 3x3x3 mat mul */
__attribute__((export_name("write_state"))) void j(void){double out[13];float A[9],B[9],C[9];for(int i=0;i<9;i++){A[i]=Rm[i];B[i]=Rm[(i+3)%9];}for(int i=0;i<3;i++)for(int k=0;k<3;k++)C[3*i+k]=A[3*i]*B[k]+A[3*i+1]*B[3+k]+A[3*i+2]*B[6+k];
 float tr=C[0]+C[4]+C[8];float s=sqrtf(tr+1)*2;out[6]=s/4;out[3]=(C[7]-C[5])/s;out[4]=(C[2]-C[6])/s;out[5]=(C[3]-C[1])/s;for(int i=0;i<3;i++)out[i]=C[i];for(int i=7;i<13;i++)out[i]=0;sink=(int32_t)out[3];}
/* K: sample whole 320x240 gray every 8 px: 40x30 = 1200 px */
__attribute__((export_name("read1200px"))) void k(void){int s=0;for(int y=0;y<240;y+=8)for(int x=0;x<320;x+=8)s+=F[(y*320+x)*3+1];sink=s;}
/* L: precompute bilinear 2x downsample of 40x30 from 320x240 area 8x8 box per out px (full-frame 76800 px) */
__attribute__((export_name("box8_full"))) void l(void){static volatile uint8_t o[1200];for(int y=0;y<30;y++)for(int x=0;x<40;x++){int s=0;for(int j=0;j<8;j++)for(int i=0;i<8;i++)s+=F[((y*8+j)*320+x*8+i)*3+1];o[y*40+x]=s>>6;}sink=o[77];}
/* M: 4x4 box of 80x60 */
__attribute__((export_name("box4_80x60_G"))) void m(void){static volatile uint8_t o[4800];for(int y=0;y<60;y++)for(int x=0;x<80;x++){int s=0;for(int j=0;j<4;j++)for(int i=0;i<4;i++)s+=F[((y*4+j)*320+x*4+i)*3+1];o[y*80+x]=s>>4;}sink=o[177];}
/* N: float 3x3 matvec + normalize chain (small) x 10 */
__attribute__((export_name("matvec10"))) void n(void){float x[3]={1,2,3};for(int r=0;r<10;r++){float y[3];for(int i=0;i<3;i++)y[i]=Rm[3*i]*x[0]+Rm[3*i+1]*x[1]+Rm[3*i+2]*x[2];x[0]=y[0];x[1]=y[1];x[2]=y[2];}vf[0]=x[0];}
int main(void){return 0;}
