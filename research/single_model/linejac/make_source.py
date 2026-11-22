from pathlib import Path
w=Path(__file__).resolve().parent
s=(w/'base.c').read_text(); helper=(w/'analytic.h').read_text()
a=s.index('static int line_rows(');s=s[:a]+helper+'\n'+s[a:]
# Preserve every original numeric block verbatim under the switch-off branch.
def wrap(start,end,code,check):
 global s
 a=s.index(start,s.index('static int line_rows('));b=s.index(end,a)
 old=s[a:b]
 s=s[:a]+'#if EDGE_AJAC && !EDGE_AJCHECK\n'+code+'\n#else\n'+old+'#if EDGE_AJCHECK\n'+check+'\n#endif\n#endif\n'+s[b:]
def fitcode(L,typ,idx,st,dim):
 return f'        for (int {idx}=0; {idx}<m; {idx}++) aj_eval(&{L},{typ},e1,e2,Rwc[{idx}],pwc[{idx}],&o,{idx},&J[2*{idx}][0],{dim},0);'
def fitcheck(L,typ,idx,dim):
 return f'        for (int {idx}=0; {idx}<m; {idx}++) {{ double A[2*{dim}];aj_eval(&{L},{typ},e1,e2,Rwc[{idx}],pwc[{idx}],&o,{idx},A,{dim},0);aj_check(&J[2*{idx}][0],A,{dim},{dim},0); }}'
wrap('        for (int p = 0; p < 4; p++) {','        for (int r = 0; r < nr; r++) for (int a = 0; a < 4;',fitcode('L','0','k','',4),fitcheck('L','0','k',4))
# constrained blocks cannot refer to e1/e2 (not in scope); constrained helper never dereferences them
wrap('                for (int p = 0; p < np; p++) {','                for (int q = 0; q < nr; q++) for (int a = 0; a < np;', '                for(int k=0;k<m;k++) aj_eval(&B,want,0,0,Rwc[k],pwc[k],&o,k,&J[2*k][0],3,0);','                for(int k=0;k<m;k++){double A[6];aj_eval(&B,want,0,0,Rwc[k],pwc[k],&o,k,A,3,0);aj_check(&J[2*k][0],A,3,np,want);}')
wrap('                    for (int p = 0; p < 2; p++) {','                    for (int a = 0; a < nr; a++) { A3', '                    for(int k=0;k<m;k++)aj_eval(&B,3,0,0,Rwc[k],pwc[k],&o,k,&J[2*k][0],2,0);','                    for(int k=0;k<m;k++){double A[4];aj_eval(&B,3,0,0,Rwc[k],pwc[k],&o,k,A,2,0);aj_check(&J[2*k][0],A,2,2,3);}')
wrap('    for (int p = 0; p < NP; p++) {','    memset(Hx, 0, nr * MAXD', '    for(int k=0;k<m;k++)aj_eval(&L,type,e1,e2,Rwc[k],pwc[k],&o,k,Hl+8*k,4,0);','    for(int k=0;k<m;k++){double A[8];aj_eval(&L,type,e1,e2,Rwc[k],pwc[k],&o,k,A,4,0);aj_check(Hl+8*k,A,4,NP,4+type);}')
wrap('        for (int a = 0; a < 6; a++) {','    }\n    int nzc[6 * MAX_OBS]', '        double A[12];aj_eval(&L,type,e1,e2,Rwc[k],pwc[k],&o,k,0,0,A);\n        for(int t=0;t<2;t++)for(int a=0;a<6;a++)Hx[(2*k+t)*MAXD+off+a]=A[6*t+a];','        double A[12],B[12];aj_eval(&L,type,e1,e2,Rwc[k],pwc[k],&o,k,0,0,A);\n        for(int t=0;t<2;t++)for(int a=0;a<6;a++)B[6*t+a]=Hx[(2*k+t)*MAXD+off+a];\n        aj_check(B,A,6,6,8);')
(w/'lj.c').write_text(s)
