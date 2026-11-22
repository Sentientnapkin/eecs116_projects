from pathlib import Path
w=Path(__file__).resolve().parent;s=(w/'lj.c').read_text()
s=s.replace('#ifndef EDGE_AJAC', '#ifndef LJ_FUSE\n#define LJ_FUSE 0\n#endif\n#ifndef EDGE_AJAC',1)
a=s.index('static inline __attribute__((always_inline)) void aj_eval(');b=s.index('#if EDGE_AJCHECK\nstatic void aj_check',a)
p=s[a:b].replace('void aj_eval(', 'int aj_eval_raw(',1).replace('double *J, int stride, double *JP) {', 'double *J, int stride, double *JP, double *hout, const double *dir) {',1)
p=p.replace('    double n=sqrt(l[0]*l[0]+l[1]*l[1]);','    double n=sqrt(l[0]*l[0]+l[1]*l[1]);\n    if(n<1e-12)return 0;',1)
p=p.replace('    if(type==2) { double f=atan2(L->D[1],L->D[0]);c=cos(f);sn=sin(f); }','    if(type==2) { if(dir){c=dir[0];sn=dir[1];}else{double f=atan2(L->D[1],L->D[0]);c=cos(f);sn=sin(f);} }')
p=p.replace('        double h=(l[0]*px+l[1]*py+l[2])/n;','        double h=(l[0]*px+l[1]*py+l[2])/n;\n        if(hout)hout[s]=h;',1)
p=p.rstrip();assert p.endswith('}');p=p[:-1]+'    return 1;\n}\n'
p+='''static inline __attribute__((always_inline)) void aj_eval(const Line3 *L,int type,const double *e1,const double *e2,const double *Rw,const double *pw,const Obs *o,int k,double *J,int stride,double *JP) {
    aj_eval_raw(L,type,e1,e2,Rw,pw,o,k,J,stride,JP,0,0);
}
'''
s=s[:a]+p+s[b:]
# Free GN already declares J above the residual pass.
old='''        for (int k = 0; k < m; k++) { if (!lres(&L, Rwc[k], pwc[k], o.x[k], o.y[k], o.enx[k], o.eny[k], o.ehl[k], h + 2 * k)) { tc_tri++; GSD(g_dx ? 0 : l_tri++); return 0; } }'''
new='''        for(int k=0;k<m;k++) {
            int ok = it==3 ? lres(&L,Rwc[k],pwc[k],o.x[k],o.y[k],o.enx[k],o.eny[k],o.ehl[k],h+2*k) : aj_eval_raw(&L,0,e1,e2,Rwc[k],pwc[k],&o,k,&J[2*k][0],4,0,h+2*k,0);
            if(!ok){tc_tri++;GSD(g_dx ? 0 : l_tri++);return 0;}
        }'''
assert old in s;s=s.replace(old,'#if LJ_FUSE && EDGE_AJAC && !EDGE_AJCHECK\n'+new+'\n#else\n'+old+'\n#endif',1)
old='        for (int k=0; k<m; k++) aj_eval(&L,0,e1,e2,Rwc[k],pwc[k],&o,k,&J[2*k][0],4,0);'
assert old in s;s=s.replace(old,'#if !LJ_FUSE\n'+old+'\n#endif',1)
# Constrained and heading GN: declare J before residuals only in fused mode.
for typ,dim,var,last,oldloop,olddecl,oldfill in [
('want',3,'k',4,'                for (int k = 0; k < m && okm; k++) okm = lres(&B, Rwc[k], pwc[k], o.x[k], o.y[k], o.enx[k], o.eny[k], o.ehl[k], hv + 2 * k);','                double J[2 * MAX_OBS][3], JtJ[9] = {0}, Jtr[3] = {0};','                for(int k=0;k<m;k++) aj_eval(&B,want,0,0,Rwc[k],pwc[k],&o,k,&J[2*k][0],3,0);'),
('3',2,'k2',3,'                    for (int k2 = 0; k2 < m && okm; k2++) okm = lres(&B, Rwc[k2], pwc[k2], o.x[k2], o.y[k2], o.enx[k2], o.eny[k2], o.ehl[k2], hv + 2 * k2);','                    double J[2 * MAX_OBS][2], A3[3] = {0, 0, 0}, g2[2] = {0, 0};','                    for(int k=0;k<m;k++)aj_eval(&B,3,0,0,Rwc[k],pwc[k],&o,k,&J[2*k][0],2,0);')]:
 dir='double ad[2]={0}; if(want==2){double f=atan2(B.D[1],B.D[0]);ad[0]=cos(f);ad[1]=sin(f);}' if typ=='want' else 'double ad[2]={0};'
 new=f'''            double J[2*MAX_OBS][{dim}]; {dir}
            for(int {var}=0;{var}<m && okm;{var}++) {{
                okm=it=={last} ? lres(&B,Rwc[{var}],pwc[{var}],o.x[{var}],o.y[{var}],o.enx[{var}],o.eny[{var}],o.ehl[{var}],hv+2*{var}) : aj_eval_raw(&B,{typ},0,0,Rwc[{var}],pwc[{var}],&o,{var},&J[2*{var}][0],{dim},0,hv+2*{var},ad);
            }}'''
 assert oldloop in s;s=s.replace(oldloop,'#if LJ_FUSE && EDGE_AJAC && !EDGE_AJCHECK\n'+new+'\n#else\n'+oldloop+'\n#endif',1)
 newdecl=olddecl.replace(f'J[2 * MAX_OBS][{dim}], ','')
 assert olddecl in s;s=s.replace(olddecl,'#if LJ_FUSE && EDGE_AJAC && !EDGE_AJCHECK\n'+newdecl+'\n#else\n'+olddecl+'\n#endif',1)
 assert oldfill in s;s=s.replace(oldfill,'#if !LJ_FUSE\n'+oldfill+'\n#endif',1)
(w/'lj_exact.c').write_text(s)
