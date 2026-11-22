from pathlib import Path
w=Path(__file__).resolve().parent;s=(w/'base.c').read_text()
def fn(name):
 import re
 a=re.search(r'^static (?:void|int) '+name+r'\(',s,re.M).start();b=s.index('{',a);depth=1;i=b+1
 while depth:
  if s[i]=='{':depth+=1
  elif s[i]=='}':depth-=1
  i+=1
 return s[a:i]+'\n'
out='''#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#define EDGE_AJAC 1
#define EDGE_AJCHECK 0
typedef struct {double Q[3],D[3];} Line3;
typedef struct {double x[1],y[1],enx[1],eny[1],ehl[1];} Obs;
static double R_bc[9],p_bc[3];
'''
for n in ['m3mul','m3vec','m3tvec','skew','exp_so3','rot_right','lperturb','lres','lmodel','lbasis']:out+=fn(n)
out+=(w/'analytic.h').read_text()
out+='''
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
    int fail=wp>1e-6;for(int i=0;i<4;i++){printf("type %d n=%d relative max %.12g\\n",i,count[i],worst[i]);fail|=worst[i]>1e-6;}
    printf("pose arbitrary extrinsics relative max %.12g\\n",wp);return fail;
}
'''
(w/'numeric_test.c').write_text(out)
