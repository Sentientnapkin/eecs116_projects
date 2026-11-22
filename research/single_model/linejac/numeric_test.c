#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#define EDGE_AJAC 1
#define EDGE_AJCHECK 0
typedef struct {double Q[3],D[3];} Line3;
typedef struct {double x[1],y[1],enx[1],eny[1],ehl[1];} Obs;
static double R_bc[9],p_bc[3];
static void m3mul(const double *a, const double *b, double *c) { /* c = a b */
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++) c[3 * i + j] = a[3 * i] * b[j] + a[3 * i + 1] * b[3 + j] + a[3 * i + 2] * b[6 + j];
}
static void m3vec(const double *a, const double *x, double *y) { /* y = a x */
    for (int i = 0; i < 3; i++) y[i] = a[3 * i] * x[0] + a[3 * i + 1] * x[1] + a[3 * i + 2] * x[2];
}
static void m3tvec(const double *a, const double *x, double *y) { /* y = a^T x */
    for (int i = 0; i < 3; i++) y[i] = a[i] * x[0] + a[3 + i] * x[1] + a[6 + i] * x[2];
}
static void skew(const double *w, double *k) { /* [w]x */
    k[0] = 0; k[1] = -w[2]; k[2] = w[1]; k[3] = w[2]; k[4] = 0; k[5] = -w[0]; k[6] = -w[1]; k[7] = w[0]; k[8] = 0;
}
static void exp_so3(const double *w, double *r) { /* Rodrigues */
    double angle = sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2]), k[9], kk[9];
    if (angle < 1e-12) {
        skew(w, k);
        for (int i = 0; i < 9; i++) r[i] = k[i] + (i % 4 == 0);
        return;
    }
    double u[3] = {w[0] / angle, w[1] / angle, w[2] / angle};
    skew(u, k);
    m3mul(k, k, kk);
    double s = sin(angle), c = 1 - cos(angle);
    for (int i = 0; i < 9; i++) r[i] = (i % 4 == 0) + s * k[i] + c * kk[i];
}
static void rot_right(double *Rm, const double *w) { /* Rm <- Rm Exp(w) */
    double e[9], t[9];
    exp_so3(w, e);
    m3mul(Rm, e, t);
    memcpy(Rm, t, sizeof t);
}
static void lperturb(const Line3 *L, const double *e1, const double *e2, const double *dl, Line3 *out) {
    double d[3];
    for (int i = 0; i < 3; i++) { out->Q[i] = L->Q[i] + dl[0] * e1[i] + dl[1] * e2[i]; d[i] = L->D[i] + dl[2] * e1[i] + dl[3] * e2[i]; }
    double n = sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]); for (int i = 0; i < 3; i++) out->D[i] = d[i] / n;
}
static int lres(const Line3 *L, const double *Rwc, const double *pwc, double x, double y, double ex, double ey, double hl, double *h) {
    double dq[3], Qc[3], Dc[3];
    for (int i = 0; i < 3; i++) dq[i] = L->Q[i] - pwc[i];
    m3tvec(Rwc, dq, Qc); m3tvec(Rwc, L->D, Dc);
    double l[3] = {Qc[1] * Dc[2] - Qc[2] * Dc[1], Qc[2] * Dc[0] - Qc[0] * Dc[2], Qc[0] * Dc[1] - Qc[1] * Dc[0]};
    double nn = sqrt(l[0] * l[0] + l[1] * l[1]);
    if (nn < 1e-12) return 0;
    double tx = -ey, ty = ex;
    for (int s = 0; s < 2; s++) { double sg = s ? 1 : -1, px = x + sg * hl * tx, py = y + sg * hl * ty; h[s] = (l[0] * px + l[1] * py + l[2]) / nn; }
    return 1;
}
static void lmodel(const Line3 *L, int type, const double *dl, Line3 *out) {
    *out = *L;
    if (type == 1) { out->Q[0] += dl[0]; out->Q[1] += dl[1]; return; }
    if (type == 3) { out->Q[0] += -L->D[1] * dl[0]; out->Q[1] += L->D[0] * dl[0]; out->Q[2] += dl[1]; return; }
    double f = atan2(L->D[1], L->D[0]), c = cos(f), sn = sin(f), f2 = f + dl[2];
    out->Q[0] += -sn * dl[0]; out->Q[1] += c * dl[0]; out->Q[2] += dl[1];
    out->D[0] = cos(f2); out->D[1] = sin(f2); out->D[2] = 0;
}
static void lbasis(const double *D, double *e1, double *e2) {
    double a[3] = {1, 0, 0}; if (fabs(D[0]) > 0.6) { a[0] = 0; a[1] = 1; }
    double t = a[0] * D[0] + a[1] * D[1] + a[2] * D[2], nn = 0;
    for (int i = 0; i < 3; i++) { e1[i] = a[i] - t * D[i]; nn += e1[i] * e1[i]; }
    nn = 1 / sqrt(nn); for (int i = 0; i < 3; i++) e1[i] *= nn;
    e2[0] = D[1] * e1[2] - D[2] * e1[1]; e2[1] = D[2] * e1[0] - D[0] * e1[2]; e2[2] = D[0] * e1[1] - D[1] * e1[0];
}
#ifndef EDGE_AJAC
#define EDGE_AJAC 0
#endif
#ifndef EDGE_AJCHECK
#define EDGE_AJCHECK 0
#endif
#if EDGE_AJAC || EDGE_AJCHECK
/* q=Rwc^T(Q-pwc), d=Rwc^T D, l=q x d, n=hypot(lx,ly).
   dh/dl=(v-h*(lx,ly,0)/n)/n. Thus dh/dq=d x dh/dl,
   dh/dd=dh/dl x q. Line tangents are those of lperturb/lmodel.
   Right body rotation gives dq=Rbc^T([Rb^T(Q-pb)]x theta),
   dd=Rbc^T([Rb^T D]x theta), including the camera lever arm. */
static void aj_cross(const double *a, const double *b, double *c) {
    c[0]=a[1]*b[2]-a[2]*b[1]; c[1]=a[2]*b[0]-a[0]*b[2]; c[2]=a[0]*b[1]-a[1]*b[0];
}
static inline __attribute__((always_inline)) void aj_eval(const Line3 *L, int type, const double *e1, const double *e2,
                    const double *Rw, const double *pw, const Obs *o, int k,
                    double *J, int stride, double *JP) {
    double w[3], q[3], d[3], l[3];
    for(int i=0;i<3;i++) w[i]=L->Q[i]-pw[i];
    m3tvec(Rw,w,q); m3tvec(Rw,L->D,d); aj_cross(q,d,l);
    double n=sqrt(l[0]*l[0]+l[1]*l[1]);
    double c=0,sn=0;
    if(type==2) { double f=atan2(L->D[1],L->D[0]);c=cos(f);sn=sin(f); }
    int np=type==0?4:type==2?3:2;
    for(int s=0;s<2;s++) {
        double sg=s?1:-1,px=o->x[k]-sg*o->ehl[k]*o->eny[k],py=o->y[k]+sg*o->ehl[k]*o->enx[k];
        double h=(l[0]*px+l[1]*py+l[2])/n;
        double g[3]={(px-h*l[0]/n)/n,(py-h*l[1]/n)/n,1/n};
        double aq[3],bd[3],A[3],B[3]; aj_cross(d,g,aq);aj_cross(g,q,bd);
        m3vec(Rw,aq,A);m3vec(Rw,bd,B);
        if(J) {
            double z[4]={0};
            if(type==0) for(int i=0;i<3;i++) { z[0]+=A[i]*e1[i];z[1]+=A[i]*e2[i];z[2]+=B[i]*e1[i];z[3]+=B[i]*e2[i]; }
            else if(type==1) {z[0]=A[0];z[1]=A[1];}
            else {z[0]=-A[0]*(type==2?sn:L->D[1])+A[1]*(type==2?c:L->D[0]);z[1]=A[2];if(type==2)z[2]=-B[0]*sn+B[1]*c;}
            for(int p=0;p<np;p++) J[s*stride+p]=z[p];
        }
        if(JP) {
            double ab[3],bb[3],qb[3],db[3],ar[3],br[3];
            m3vec(R_bc,aq,ab);m3vec(R_bc,bd,bb);m3vec(R_bc,q,qb);m3vec(R_bc,d,db);
            for(int i=0;i<3;i++)qb[i]+=p_bc[i];
            aj_cross(ab,qb,ar);aj_cross(bb,db,br);
            for(int i=0;i<3;i++){JP[s*6+i]=ar[i]+br[i];JP[s*6+3+i]=-A[i];}
        }
    }
}
#if EDGE_AJCHECK
static void aj_check(const double *numeric,const double *analytic,int stride,int np,int kind) {
    double nd=0,na=0,err=0,ma=0;
    for(int s=0;s<2;s++)for(int p=0;p<np;p++){
        double a=analytic[s*stride+p],b=numeric[s*stride+p],e=a-b;nd+=b*b;na+=a*a;err+=e*e;if(fabs(e)>ma)ma=fabs(e);
    }
    double rel=sqrt(err/fmax(fmax(nd,na),1e-20));
    /* One record per observation/block; checker aggregates maximum and quantiles.
       Debug builds retain numeric values, so validation precedes deployment. */
    fprintf(stderr,"AJ %d %.12g %.12g\n",kind,rel,ma);
}
#endif
#endif

static double unif(void){return 2.0*rand()/RAND_MAX-1;}
int main(void){
    srand(20261122);double worst[4]={0},wp=0;int count[4]={0};
    for(int type=0;type<4;type++)for(int it=0;it<3000;it++){
        double w[3]={unif(),unif(),unif()},Rb[9],Rw[9],pb[3]={unif(),unif(),unif()},pw[3],t[3];
        exp_so3(w,Rb);for(int i=0;i<3;i++)w[i]=unif();exp_so3(w,R_bc);
        for(int i=0;i<3;i++)p_bc[i]=0.2*unif();
        m3mul(Rb,R_bc,Rw);m3vec(Rb,p_bc,t);for(int i=0;i<3;i++)pw[i]=pb[i]+t[i];
        Line3 L={{3*unif(),3*unif(),3+unif()},{unif(),unif(),unif()}};
        if(type==1){L.D[0]=0;L.D[1]=0;L.D[2]=1;}
        if(type==2||type==3)L.D[2]=0;
        double norm=sqrt(L.D[0]*L.D[0]+L.D[1]*L.D[1]+L.D[2]*L.D[2]);for(int i=0;i<3;i++)L.D[i]/=norm;
        double dq[3],q[3],d[3],l[3];for(int i=0;i<3;i++)dq[i]=L.Q[i]-pw[i];m3tvec(Rw,dq,q);m3tvec(Rw,L.D,d);aj_cross(q,d,l);
        if(hypot(l[0],l[1])<0.2)continue;
        Obs o={{unif()},{unif()},{0.6},{0.8},{0.1}};double e1[3],e2[3];lbasis(L.D,e1,e2);
        double J[8],JP[12];aj_eval(&L,type,e1,e2,Rw,pw,&o,0,J,4,JP);int np=type==0?4:type==2?3:2;
        double err=0,nrm=0;const double eps=1e-6;
        for(int p=0;p<np;p++){
            double dl[4]={0},hp[2],hm[2];Line3 Bp,Bm;dl[p]=eps;
            if(type)lmodel(&L,type,dl,&Bp);else lperturb(&L,e1,e2,dl,&Bp);
            dl[p]=-eps;if(type)lmodel(&L,type,dl,&Bm);else lperturb(&L,e1,e2,dl,&Bm);
            lres(&Bp,Rw,pw,o.x[0],o.y[0],o.enx[0],o.eny[0],o.ehl[0],hp);lres(&Bm,Rw,pw,o.x[0],o.y[0],o.enx[0],o.eny[0],o.ehl[0],hm);
            for(int r=0;r<2;r++){double num=(hp[r]-hm[r])/(2*eps),a=J[4*r+p];err+=(num-a)*(num-a);nrm+=a*a;}
        }
        double rel=sqrt(err/fmax(nrm,1e-20));if(rel>worst[type])worst[type]=rel;count[type]++;
        err=nrm=0;
        for(int p=0;p<6;p++){
            double hh[2][2];for(int sg=0;sg<2;sg++){
                double Rp[9],pp[3],Rc[9],pc[3],e=sg?-eps:eps;memcpy(Rp,Rb,sizeof Rp);memcpy(pp,pb,sizeof pp);
                if(p<3){double dr[3]={0};dr[p]=e;rot_right(Rp,dr);}else pp[p-3]+=e;
                m3mul(Rp,R_bc,Rc);m3vec(Rp,p_bc,pc);for(int i=0;i<3;i++)pc[i]+=pp[i];
                lres(&L,Rc,pc,o.x[0],o.y[0],o.enx[0],o.eny[0],o.ehl[0],hh[sg]);
            }
            for(int r=0;r<2;r++){double num=(hh[0][r]-hh[1][r])/(2*eps),a=JP[6*r+p];err+=(num-a)*(num-a);nrm+=a*a;}
        }
        rel=sqrt(err/fmax(nrm,1e-20));if(rel>wp)wp=rel;
    }
    int fail=wp>1e-6;for(int i=0;i<4;i++){printf("type %d n=%d relative max %.12g\n",i,count[i],worst[i]);fail|=worst[i]>1e-6;}
    printf("pose arbitrary extrinsics relative max %.12g\n",wp);return fail;
}
