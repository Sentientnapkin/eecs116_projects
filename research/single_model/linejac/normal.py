from pathlib import Path
w=Path(__file__).resolve().parent;s=(w/'lj.c').read_text()
s=s.replace('#ifndef EDGE_ASIMD','#ifndef LJ_NORMAL\n#define LJ_NORMAL 0\n#endif\n#ifndef EDGE_ASIMD',1)
patterns=[
('        for (int r = 0; r < nr; r++) for (int a = 0; a < 4; a++) { Jtr[a] += J[r][a] * h[r]; for (int b = 0; b < 4; b++) JtJ[4 * a + b] += J[r][a] * J[r][b]; }', '4','h','4'),
('                for (int q = 0; q < nr; q++) for (int a = 0; a < np; a++) { Jtr[a] += J[q][a] * hv[q]; for (int b = 0; b < np; b++) JtJ[np * a + b] += J[q][a] * J[q][b]; }','np','hv','np')]
for old,n,h,ld in patterns:
 assert old in s
 new=f'''        for(int a=0;a<{n};a++){{
            double v=0;for(int r=0;r<nr;r++)v+=J[r][a]*{h}[r];Jtr[a]=v;
            for(int b=0;b<=a;b++){{
                double v=0;for(int r=0;r<nr;r++)v+=J[r][a]*J[r][b];
                JtJ[{ld}*a+b]=JtJ[{ld}*b+a]=v;
            }}
        }}'''
 s=s.replace(old,'#if LJ_NORMAL\n'+new+'\n#else\n'+old+'\n#endif',1)
(w/'lj.c').write_text(s)
