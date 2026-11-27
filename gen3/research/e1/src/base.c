/* e1 baselines. MODE 0: identity pose. 1: IMU dead reckoning (gravity from first accel mean). 2: attitude only (pos=0). 3: DR + speed damping */
#include <math.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include "viobench_abi.h"
#ifndef MODE
#define MODE 1
#endif
#ifndef VDAMP
#define VDAMP 0.0   /* velocity decay per second (MODE 3) */
#endif
#ifndef ATT_K
#define ATT_K 0.0   /* accel attitude correction gain 1/s (MODE 1..3 when >0) */
#endif
static double T[16], R_bc[9], p_bc[3];
static double R[9], v[3], p[3], g[3], bg[3];
static int inited; static double tl;
int32_t abi_version(void){return 1;}
void *alloc(uint32_t s){return malloc(s?s:1);}
int32_t frame_width(void){return 320;}
static int num(const char*b,const char*k,double*o,int n){const char*s=strstr(b,k);if(!s)return 0;s+=strlen(k);for(int i=0;i<n;i++){while(*s&&!(*s=='-'||*s=='.'||(*s>='0'&&*s<='9')))s++;char*e;o[i]=strtod(s,&e);s=e;}return 1;}
int32_t init(const char*j,uint32_t n){static char b[4096];if(n>=4096)return -1;memcpy(b,j,n);b[n]=0;if(!num(b,"\"T_cam_imu\"",T,16))return -1;
 /* R_bc = R_imu<-cam = R_cam_imu^T ; p_bc = -R_cb t */
 for(int i=0;i<3;i++)for(int k=0;k<3;k++)R_bc[3*i+k]=T[4*k+i];
 for(int i=0;i<3;i++)p_bc[i]=-(T[i]*T[3]+T[4+i]*T[7]+T[8+i]*T[11]); inited=0; return 0;}
static void mv(const double*A,const double*x,double*y){for(int i=0;i<3;i++)y[i]=A[3*i]*x[0]+A[3*i+1]*x[1]+A[3*i+2]*x[2];}
static void mtv(const double*A,const double*x,double*y){for(int i=0;i<3;i++)y[i]=A[i]*x[0]+A[3+i]*x[1]+A[6+i]*x[2];}
static void mm(const double*A,const double*B,double*C){for(int i=0;i<3;i++)for(int k=0;k<3;k++)C[3*i+k]=A[3*i]*B[k]+A[3*i+1]*B[3+k]+A[3*i+2]*B[6+k];}
static void rot(double*Rm,const double*w,double dt){ /* R <- R*exp([w dt]x) */
 double a=sqrt(w[0]*w[0]+w[1]*w[1]+w[2]*w[2])*dt, s,c1; double k[3]={w[0]*dt,w[1]*dt,w[2]*dt};
 if(a<1e-9){s=1;c1=0.5;}else{s=sin(a)/a;c1=(1-cos(a))/(a*a);}
 double K[9]={0,-k[2],k[1],k[2],0,-k[0],-k[1],k[0],0},K2[9],E[9],N[9];mm(K,K,K2);
 for(int i=0;i<9;i++)E[i]=(i%4==0)+s*K[i]+c1*K2[i]; mm(Rm,E,N);memcpy(Rm,N,sizeof N);}
int32_t step(double t,const uint8_t*f,const double*imu,int32_t n,double*out){
 (void)f;
 if(MODE==0){memset(out,0,13*8);out[6]=1;return 0;}
 if(!inited&&n>0){double a[3]={0,0,0};for(int r=0;r<n;r++)for(int i=0;i<3;i++)a[i]+=imu[7*r+1+i]/n;
  double na=sqrt(a[0]*a[0]+a[1]*a[1]+a[2]*a[2]);for(int i=0;i<3;i++)g[i]=-a[i]/na*9.81; /* gravity in b0 = -specific force */
  memset(R,0,sizeof R);R[0]=R[4]=R[8]=1;memset(v,0,sizeof v);memset(p,0,sizeof p);inited=1;tl=imu[0]-0.005;}
 if(inited){for(int r=0;r<n;r++){const double*q=imu+7*r;double dt=q[0]-tl;tl=q[0];if(dt<=0||dt>0.1)continue;
   double w[3]={q[4]-bg[0],q[5]-bg[1],q[6]-bg[2]},a[3]={q[1],q[2],q[3]},aw[3];
   rot(R,w,dt);
   if(ATT_K>0){ /* tilt correction: measured up (R a) vs -g */
     double up[3];mv(R,a,up);double gn=-1/9.81;double u[3]={g[0]*gn*-1*-1,0,0};(void)u;
     double gu[3]={-g[0]/9.81,-g[1]/9.81,-g[2]/9.81}; /* up in world */
     double na=sqrt(up[0]*up[0]+up[1]*up[1]+up[2]*up[2]);for(int i=0;i<3;i++)up[i]/=na;
     double e[3]={up[1]*gu[2]-up[2]*gu[1],up[2]*gu[0]-up[0]*gu[2],up[0]*gu[1]-up[1]*gu[0]}; /* up x gu: world rotation */
     double ew[3];mtv(R,e,ew);double c[3]={ew[0]*ATT_K,ew[1]*ATT_K,ew[2]*ATT_K};rot(R,c,dt);}
   if(MODE==2)continue;
   mv(R,a,aw);for(int i=0;i<3;i++){aw[i]+=g[i];p[i]+=v[i]*dt+0.5*aw[i]*dt*dt;v[i]+=aw[i]*dt;}
   if(MODE==3){double d=exp(-VDAMP*dt);for(int i=0;i<3;i++)v[i]*=d;}}}
 /* camera pose in cam0 frame: R_c0ck = R_cb R_wb R_bc ; p = R_cb (p_wb + R_wb p_bc - p_bc) */
 double Rbw[9],Rc[9],tmp[9],q[3],pc[3],pb[3];
 mm(R,R_bc,tmp);for(int i=0;i<3;i++)for(int k=0;k<3;k++)Rc[3*i+k]=0;
 for(int i=0;i<3;i++)for(int k=0;k<3;k++){double s=0;for(int m=0;m<3;m++)s+=R_bc[3*m+i]*tmp[3*m+k];Rc[3*i+k]=s;}
 double rp[3];mv(R,p_bc,rp);for(int i=0;i<3;i++)q[i]=p[i]+rp[i]-p_bc[i];mtv(R_bc,q,pc);
 (void)Rbw;(void)pb;
 out[0]=pc[0];out[1]=pc[1];out[2]=pc[2];
 double tr=Rc[0]+Rc[4]+Rc[8],qw,qx,qy,qz;
 if(tr>0){double s=sqrt(tr+1)*2;qw=s/4;qx=(Rc[7]-Rc[5])/s;qy=(Rc[2]-Rc[6])/s;qz=(Rc[3]-Rc[1])/s;}
 else if(Rc[0]>Rc[4]&&Rc[0]>Rc[8]){double s=sqrt(1+Rc[0]-Rc[4]-Rc[8])*2;qw=(Rc[7]-Rc[5])/s;qx=s/4;qy=(Rc[1]+Rc[3])/s;qz=(Rc[2]+Rc[6])/s;}
 else if(Rc[4]>Rc[8]){double s=sqrt(1+Rc[4]-Rc[0]-Rc[8])*2;qw=(Rc[2]-Rc[6])/s;qx=(Rc[1]+Rc[3])/s;qy=s/4;qz=(Rc[5]+Rc[7])/s;}
 else{double s=sqrt(1+Rc[8]-Rc[0]-Rc[4])*2;qw=(Rc[3]-Rc[1])/s;qx=(Rc[2]+Rc[6])/s;qy=(Rc[5]+Rc[7])/s;qz=s/4;}
 out[3]=qx;out[4]=qy;out[5]=qz;out[6]=qw;
 double vc[3];mtv(R_bc,v,vc);out[7]=vc[0];out[8]=vc[1];out[9]=vc[2];out[10]=out[11]=out[12]=0;
 return 0;}
