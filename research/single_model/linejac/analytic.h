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
