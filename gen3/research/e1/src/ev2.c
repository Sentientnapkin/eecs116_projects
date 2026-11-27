/* e1 ultra-cheap VIO: gyro attitude + NF persistent gyro-predicted LK patch tracks + 6-state (v, ba) EKF with epipolar velocity-direction constraints. Float. */
#include <math.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include "viobench_abi.h"
#ifndef NF
#define NF 4          /* tracked patches */
#endif
#ifndef HW
#define HW 3          /* window half size in samples */
#endif
#ifndef SS
#define SS 2          /* sample stride (px at 320x240) */
#endif
#ifndef SIGF
#define SIGF 0.004f   /* flow noise, normalised units (px/fx) per frame */
#endif
#ifndef QV
#define QV 0.01f      /* velocity process noise per frame (m/s) */
#endif
#ifndef QB
#define QB 0.0005f
#endif
#ifndef V0STD
#define V0STD 2.0f
#endif
#ifndef ZUPT_THR
#define ZUPT_THR 0.0f     /* normalised mean translational flow below which v=0 pseudo-meas (0=off) */
#endif
#ifndef ZSTD
#define ZSTD 0.15f
#endif
#ifndef SPD0
#define SPD0 0.0f         /* speed prior mean (0 = off) */
#endif
#ifndef SPDSTD
#define SPDSTD 1.0f
#endif
#ifndef TILTK
#define TILTK 0.0f        /* accel tilt correction gain (1/s) */
#endif
#ifndef TILTKI
#define TILTKI 0.0f
#endif
#ifndef RS
#define RS 1.0f
#endif
#ifndef ANGMIN
#define ANGMIN 0.15f
#endif
#ifndef BACLAMP
#define BACLAMP 0.4f
#endif
#ifndef VLEAK
#define VLEAK 0.0f
#endif
#ifndef RIDGE
#define RIDGE 1e-6f
#endif
#ifndef WLP
#define WLP 0.5f
#endif
#ifndef NW
#define NW 10
#endif
#ifndef LAM
#define LAM 0.99f
#endif
#ifndef KAP
#define KAP 0.02f
#endif
#ifndef Z0
#define Z0 3.0f
#endif
#ifndef ZMIN
#define ZMIN 0.8f
#endif
#ifndef ZMAX
#define ZMAX 30.0f
#endif
#ifndef ZMODE
#define ZMODE 0
#endif
#ifndef OUTSC
#define OUTSC 1.0f
#endif
#ifndef GBIAS
#define GBIAS 0           /* estimate gyro bias at start from first GB frames */
#endif
#ifndef MINDET
#define MINDET 400.0f
#endif
#ifndef USE_TRFLOW_PRED
#define USE_TRFLOW_PRED 1
#endif
#define WN (2*HW+3)
#define DT 0.05f
static float fx_, fy_, cx_, cy_; static float Rbc[9], pbc[3];
static float R[9], bg[3], g[3]; static float v[3], ba[3], pos[3], P[36];
static int inited, frame_no;static float Syy;static float wv[3],wring[3*32],aring[3*32],Sxx,Sxy,Zh;
#ifdef ORACLE
float ORC[9], ORG[3], ORV[3]; float DBGH[64];
#endif
typedef struct { float x, y; float fu, fv; int ok; uint8_t tpl[WN*WN]; int have; } Feat;
static Feat F_[NF];
int32_t abi_version(void){return 1;}
void *alloc(uint32_t s){return malloc(s?s:1);}
int32_t frame_width(void){return 320;}
static int num(const char*b,const char*k,double*o,int n){const char*s=strstr(b,k);if(!s)return 0;s+=strlen(k);for(int i=0;i<n;i++){while(*s&&!(*s=='-'||*s=='.'||(*s>='0'&&*s<='9')))s++;char*e;o[i]=strtod(s,&e);s=e;}return 1;}
int32_t init(const char*j,uint32_t n){static char b[4096];double T[16],d;if(n>=4096)return -1;memcpy(b,j,n);b[n]=0;
 if(!num(b,"\"T_cam_imu\"",T,16)||!num(b,"\"fx\"",&d,1))return -1;fx_=d;num(b,"\"fy\"",&d,1);fy_=d;num(b,"\"cx\"",&d,1);cx_=d;num(b,"\"cy\"",&d,1);cy_=d;
 for(int i=0;i<3;i++)for(int k=0;k<3;k++)Rbc[3*i+k]=T[4*k+i];
 for(int i=0;i<3;i++)pbc[i]=-(T[i]*T[3]+T[4+i]*T[7]+T[8+i]*T[11]);
 inited=0;return 0;}
static void mv(const float*A,const float*x,float*y){for(int i=0;i<3;i++)y[i]=A[3*i]*x[0]+A[3*i+1]*x[1]+A[3*i+2]*x[2];}
static void mtv(const float*A,const float*x,float*y){for(int i=0;i<3;i++)y[i]=A[i]*x[0]+A[3+i]*x[1]+A[6+i]*x[2];}
static void mm(const float*A,const float*B,float*C){for(int i=0;i<3;i++)for(int k=0;k<3;k++)C[3*i+k]=A[3*i]*B[k]+A[3*i+1]*B[3+k]+A[3*i+2]*B[6+k];}
static void rotupd(float*Rm,const float*k){ /* R <- R (I + [k]x + [k]x^2/2), then renorm */
 float R0[9];memcpy(R0,Rm,36);float a=k[0],b=k[1],c=k[2];float q=0.5f;
 float E[9]={1-q*(b*b+c*c),-c+q*a*b,b+q*a*c, c+q*a*b,1-q*(a*a+c*c),-a+q*b*c, -b+q*a*c,a+q*b*c,1-q*(a*a+b*b)};
 mm(R0,E,Rm);
 for(int i=0;i<3;i++){float n=Rm[3*i]*Rm[3*i]+Rm[3*i+1]*Rm[3*i+1]+Rm[3*i+2]*Rm[3*i+2];float s=1.5f-0.5f*n;for(int j=0;j<3;j++)Rm[3*i+j]*=s;}}
static inline const uint8_t *px(const uint8_t*f,int x,int y){return f+(y*320+x)*3+1;}
/* scalar EKF update: z - h = innovation; H[6] */
static void upd(const float*H,float innov,float rv){float PH[6];for(int i=0;i<6;i++){float s=0;for(int j=0;j<6;j++)s+=P[6*i+j]*H[j];PH[i]=s;}
 float S=rv;for(int i=0;i<6;i++)S+=H[i]*PH[i];float is=1.f/S;
 /* gate: 4 sigma */ if(innov*innov>16.f*S)return;
 float K[6];for(int i=0;i<6;i++)K[i]=PH[i]*is;
 v[0]+=K[0]*innov;v[1]+=K[1]*innov;v[2]+=K[2]*innov;ba[0]+=K[3]*innov;ba[1]+=K[4]*innov;ba[2]+=K[5]*innov;
 for(int i=0;i<6;i++)for(int j=0;j<6;j++)P[6*i+j]-=K[i]*PH[j];for(int i=0;i<3;i++){if(ba[i]>BACLAMP)ba[i]=BACLAMP;if(ba[i]<-BACLAMP)ba[i]=-BACLAMP;}}
static void quat(const float*C,double*o){float tr=C[0]+C[4]+C[8],qw,qx,qy,qz;
 if(tr>0){float s=sqrtf(tr+1)*2;qw=s/4;qx=(C[7]-C[5])/s;qy=(C[2]-C[6])/s;qz=(C[3]-C[1])/s;}
 else if(C[0]>C[4]&&C[0]>C[8]){float s=sqrtf(1+C[0]-C[4]-C[8])*2;qw=(C[7]-C[5])/s;qx=s/4;qy=(C[1]+C[3])/s;qz=(C[2]+C[6])/s;}
 else if(C[4]>C[8]){float s=sqrtf(1+C[4]-C[0]-C[8])*2;qw=(C[2]-C[6])/s;qx=(C[1]+C[3])/s;qy=s/4;qz=(C[5]+C[7])/s;}
 else{float s=sqrtf(1+C[8]-C[0]-C[4])*2;qw=(C[3]-C[1])/s;qx=(C[2]+C[6])/s;qy=(C[5]+C[7])/s;qz=s/4;}
 o[3]=qx;o[4]=qy;o[5]=qz;o[6]=qw;}
static void seed(Feat*ft,int i,const uint8_t*f){ /* grid position */
 static const float gx[8]={0.25f,0.75f,0.25f,0.75f,0.5f,0.5f,0.1f,0.9f},gy[8]={0.3f,0.3f,0.7f,0.7f,0.5f,0.1f,0.5f,0.5f};
 int k=i&7;ft->x=gx[k]*320;ft->y=gy[k]*240;ft->fu=ft->fv=0;
 int m=(HW+1)*SS+2;if(ft->x<m)ft->x=m;if(ft->y<m)ft->y=m;if(ft->x>319-m)ft->x=319-m;if(ft->y>239-m)ft->y=239-m;
 int x0=(int)ft->x,y0=(int)ft->y;for(int j=0;j<WN;j++)for(int i2=0;i2<WN;i2++)ft->tpl[j*WN+i2]=*px(f,x0+(i2-HW-1)*SS,y0+(j-HW-1)*SS);ft->have=1;}
int32_t step(double t,const uint8_t*f,const double*imu,int32_t n,double*out){
 (void)t;
 if(!inited){ if(n==0){memset(out,0,13*8);out[6]=1;return 0;}
  float a[3]={0,0,0};for(int r=0;r<n;r++)for(int i=0;i<3;i++)a[i]+=imu[7*r+1+i]/n;
  float na=sqrtf(a[0]*a[0]+a[1]*a[1]+a[2]*a[2]);for(int i=0;i<3;i++)g[i]=-a[i]/na*9.81f;
#ifdef ORACLE
  for(int i=0;i<3;i++)g[i]=ORG[i];
#endif
  memset(R,0,sizeof R);R[0]=R[4]=R[8]=1;memset(v,0,sizeof v);memset(ba,0,sizeof ba);memset(pos,0,sizeof pos);memset(bg,0,sizeof bg);
  memset(P,0,sizeof P);for(int i=0;i<3;i++){P[7*i]=V0STD*V0STD;P[7*(i+3)]=0.2f*0.2f;}
  for(int i=0;i<NF;i++)seed(&F_[i],i,f);inited=1;frame_no=0;}
 else{
  /* --- IMU: average over frame --- */
  float sa[3]={0,0,0},sw[3]={0,0,0};for(int r=0;r<n;r++){const double*q=imu+7*r;for(int i=0;i<3;i++){sa[i]+=q[1+i];sw[i]+=q[4+i];}}
  float inv=1.f/n;for(int i=0;i<3;i++){sa[i]*=inv;sw[i]=sw[i]*inv-bg[i];}
  float dth[3]={sw[0]*DT,sw[1]*DT,sw[2]*DT};
  /* rotate: use mid-point attitude for accel */
  float Rn[9];memcpy(Rn,R,36);float hk[3]={dth[0]*.5f,dth[1]*.5f,dth[2]*.5f};float Rmid[9];memcpy(Rmid,R,36);rotupd(Rmid,hk);rotupd(R,dth);
#ifdef ORACLE
  {float M[9];for(int i=0;i<3;i++)for(int j=0;j<3;j++){float a2=0;for(int k=0;k<3;k++)a2+=Rn[3*k+i]*ORC[3*k+j];M[3*i+j]=a2;}dth[0]=(M[7]-M[5])*.5f;dth[1]=(M[2]-M[6])*.5f;dth[2]=(M[3]-M[1])*.5f;}
  memcpy(R,ORC,36);memcpy(Rmid,ORC,36);if(ORV[0]!=999.f)memcpy(v,ORV,12);
#endif

  float aw[3],fb[3]={sa[0]-ba[0],sa[1]-ba[1],sa[2]-ba[2]};mv(Rmid,fb,aw);for(int i=0;i<3;i++)aw[i]+=g[i];
  if(TILTK>0){float up[3];mv(R,sa,up);float nu=sqrtf(up[0]*up[0]+up[1]*up[1]+up[2]*up[2]);if(fabsf(nu-9.81f)<0.6f){float gu[3]={-g[0]/9.81f,-g[1]/9.81f,-g[2]/9.81f};for(int i=0;i<3;i++)up[i]/=nu;
    float e[3]={up[1]*gu[2]-up[2]*gu[1],up[2]*gu[0]-up[0]*gu[2],up[0]*gu[1]-up[1]*gu[0]};float ew[3];mtv(R,e,ew);float c[3]={ew[0]*TILTK*DT,ew[1]*TILTK*DT,ew[2]*TILTK*DT};rotupd(R,c);for(int i=0;i<3;i++)bg[i]-=ew[i]*TILTKI*DT;}}
  for(int i=0;i<3;i++){pos[i]+=v[i]*DT;if(VLEAK>0)v[i]*=(1.f-VLEAK*DT);}
  /* covariance propagate: F=[[I,-R dt],[0,I]] */
  { float Pvv[9],Pvb[9],Pbb[9],A[9],B[9];
    for(int i=0;i<3;i++)for(int j=0;j<3;j++){Pvv[3*i+j]=P[6*i+j];Pvb[3*i+j]=P[6*i+3+j];Pbb[3*i+j]=P[6*(i+3)+3+j];}
    float Rd[9];for(int i=0;i<9;i++)Rd[i]=Rmid[i]*DT;
    mm(Rd,Pbb,A); /* R dt Pbb */
    /* Pvb' = Pvb - A */ float Pvb2[9];for(int i=0;i<9;i++)Pvb2[i]=Pvb[i]-A[i];
    /* Pvv' = Pvv - Rd Pbv - Pvb Rd^T + Rd Pbb Rd^T ; Pbv=Pvb^T */
    float Pbv[9];for(int i=0;i<3;i++)for(int j=0;j<3;j++)Pbv[3*i+j]=Pvb[3*j+i];
    mm(Rd,Pbv,B); /* Rd Pbv */
    float RdT[9];for(int i=0;i<3;i++)for(int j=0;j<3;j++)RdT[3*i+j]=Rd[3*j+i];
    float C2[9];mm(A,RdT,C2);
    for(int i=0;i<3;i++)for(int j=0;j<3;j++){float s=Pvv[3*i+j]-B[3*i+j]-B[3*j+i]+C2[3*i+j];P[6*i+j]=s;P[6*i+3+j]=Pvb2[3*i+j];P[6*(j+3)+i]=Pvb2[3*i+j];P[6*(i+3)+3+j]=Pbb[3*i+j];}
    for(int i=0;i<3;i++){P[7*i]+=QV*QV;P[7*(i+3)]+=QB*QB;}
  }
  /* --- vision --- */
  float Rwc[9];mm(R,Rbc,Rwc); /* body->world * cam->body */
  float dthc[3];mtv(Rbc,dth,dthc);for(int i=0;i<3;i++)dthc[i]*=RS; /* camera-frame rotation increment */
  float sumf=0;int nv=0;float AtA[9]={0},Atb[3]={0};int nacc=0;
  for(int i=0;i<NF;i++){Feat*ft=&F_[i];
   float u=(ft->x-cx_)/fx_,vv=(ft->y-cy_)/fx_;
   float a0=dthc[1]-dthc[2]*vv,a1=dthc[2]*u-dthc[0],a2=dthc[0]*vv-dthc[1]*u;
   float rfu=(-a0+u*a2)*fx_,rfv=(-a1+vv*a2)*fx_; /* rotational flow px */
   float px0=ft->x+rfu+(USE_TRFLOW_PRED?ft->fu:0),py0=ft->y+rfv+(USE_TRFLOW_PRED?ft->fv:0);
   int m=(HW+1)*SS+2;
   if(px0<m||py0<m||px0>319-m||py0>239-m||!ft->have){seed(ft,i,f);ft->ok=0;continue;}
   int x0=(int)(px0+0.5f),y0=(int)(py0+0.5f);
   uint8_t cur[WN*WN];for(int j=0;j<WN;j++)for(int i2=0;i2<WN;i2++)cur[j*WN+i2]=*px(f,x0+(i2-HW-1)*SS,y0+(j-HW-1)*SS);
   float gxx=0,gxy=0,gyy=0,bx=0,by=0;
   for(int j=1;j<WN-1;j++)for(int i2=1;i2<WN-1;i2++){const uint8_t*c=cur+j*WN+i2;float ix=(c[1]-c[-1])*.5f,iy=(c[WN]-c[-WN])*.5f,it=(float)c[0]-ft->tpl[j*WN+i2];gxx+=ix*ix;gxy+=ix*iy;gyy+=iy*iy;bx+=ix*it;by+=iy*it;}
   float det=gxx*gyy-gxy*gxy;
   float tre=gxx+gyy;
   if(det<MINDET*MINDET*0.01f||tre<MINDET*0.1f||det<0.02f*tre*tre){ /* weak: reseed */ seed(ft,i,f);ft->ok=0;continue;}
   float id=1.f/det;float dx=-(gyy*bx-gxy*by)*id,dy=-(-gxy*bx+gxx*by)*id; /* sample units, template->cur displacement: solve G d = -b */
   if(dx>1.5f)dx=1.5f;if(dx<-1.5f)dx=-1.5f;if(dy>1.5f)dy=1.5f;if(dy<-1.5f)dy=-1.5f;
   float tx=(float)x0+dx*SS,ty=(float)y0+dy*SS; /* new location of the content that sat at the template centre ft->x */
   float totu=tx-ft->x,totv=ty-ft->y; /* total flow px */
   float tru=totu-rfu,trv=totv-rfv;   /* translational flow px */
   /* measurement at midpoint of motion */
   float um=((ft->x+tx)*.5f-cx_)/fx_,vm=((ft->y+ty)*.5f-cy_)/fx_;
   float oldx=ft->x,oldy=ft->y;(void)oldx;(void)oldy;
   float fu=tru/fx_,fv=trv/fx_;float fm=sqrtf(fu*fu+fv*fv);
   ft->fu=tru;ft->fv=trv;
   /* new template = cur window (anchored at x0,y0; approx) */
   memcpy(ft->tpl,cur,WN*WN);
   /* the template position offset (<1 sample) ignored; reset position anchor to integer to keep consistent */
   ft->x=(float)x0;ft->y=(float)y0;
   ft->ok=1;sumf+=fm;nv++;
   { float wgt=1.f; /* flow rows: (u*wz - wx)=fu ; (v*wz - wy)=fv, w = v*dt/Z (normalised units) */
     float r0[3]={-1,0,um},r1[3]={0,-1,vm};
     for(int p2=0;p2<3;p2++){for(int q2=0;q2<3;q2++)AtA[3*p2+q2]+=wgt*(r0[p2]*r0[q2]+r1[p2]*r1[q2]);Atb[p2]+=wgt*(r0[p2]*fu+r1[p2]*fv);} nacc++; }
  }
  { /* solve (AtA + ridge) w = Atb : 3x3 via adjugate */
    float A[9];memcpy(A,AtA,36);for(int i=0;i<3;i++)A[4*i]+=RIDGE;
    float c0=A[4]*A[8]-A[5]*A[7],c1=A[5]*A[6]-A[3]*A[8],c2=A[3]*A[7]-A[4]*A[6];float det=A[0]*c0+A[1]*c1+A[2]*c2;
    float wc[3]={0,0,0};
    if(nacc>=2&&det>1e-9f){float id=1.f/det;
      float inv[9]={c0,A[2]*A[7]-A[1]*A[8],A[1]*A[5]-A[2]*A[4], c1,A[0]*A[8]-A[2]*A[6],A[2]*A[3]-A[0]*A[5], c2,A[1]*A[6]-A[0]*A[7],A[0]*A[4]-A[1]*A[3]};
      for(int i=0;i<3;i++)wc[i]=(inv[3*i]*Atb[0]+inv[3*i+1]*Atb[1]+inv[3*i+2]*Atb[2])*id/DT;}
    /* wc: velocity per unit depth, camera axes, 1/s.  to world: Rwc wc */
    float ww[3];mv(Rwc,wc,ww);
    for(int i=0;i<3;i++)wv[i]=wv[i]+WLP*(ww[i]-wv[i]);
    /* scale from IMU: ring of 10 frames */
    memcpy(wring+3*(frame_no%NW),wv,12);memcpy(aring+3*(frame_no%NW),aw,12);
    if(frame_no>=NW){const float*w0=wring+3*((frame_no+1)%NW);float dw[3],dv[3]={0,0,0};for(int i=0;i<3;i++)dw[i]=wv[i]-w0[i];
      for(int k=0;k<NW;k++)for(int i=0;i<3;i++)dv[i]+=aring[3*k+i]*DT; /* sum of a over last NW frames */
      Sxx=LAM*Sxx+dw[0]*dw[0]+dw[1]*dw[1]+dw[2]*dw[2];Sxy=LAM*Sxy+dw[0]*dv[0]+dw[1]*dv[1]+dw[2]*dv[2];Syy=LAM*Syy+dv[0]*dv[0]+dv[1]*dv[1]+dv[2]*dv[2];}
    float Z=ZMODE==1?sqrtf((Syy+KAP*Z0*Z0)/(Sxx+KAP)):(Sxy+KAP*Z0)/(Sxx+KAP);if(Z<ZMIN)Z=ZMIN;if(Z>ZMAX)Z=ZMAX;Zh=Z;
    for(int i=0;i<3;i++){v[i]=Z*wv[i];}
  }
  frame_no++;
 }
 /* output */
 float C[9],tmp[9],q[3],rp[3],pc[3];mm(R,Rbc,tmp);for(int i=0;i<3;i++)for(int k=0;k<3;k++){float s=0;for(int m=0;m<3;m++)s+=Rbc[3*m+i]*tmp[3*m+k];C[3*i+k]=s;}
 mv(R,pbc,rp);for(int i=0;i<3;i++)q[i]=pos[i]+rp[i]-pbc[i];mtv(Rbc,q,pc);
 for(int i=0;i<3;i++)out[i]=pc[i]*OUTSC;quat(C,out);
 float vc[3];mtv(Rbc,v,vc);out[7]=vc[0];out[8]=vc[1];out[9]=vc[2];out[10]=out[11]=out[12]=0;
#ifdef DBGOUT
 out[10]=P[0];out[11]=Sxx;out[12]=Zh;
#endif

 return 0;}
