from pathlib import Path
w=Path(__file__).resolve().parent
s=(w/'prof/ajsf.c').read_text()
# Use latest optimized source with phase instrumentation, generated separately.
s=(w/'prof/ajc.c').read_text()
h='''static void line_fee_end(int *n) { mark(58, -100-*n); }
'''
a=s.index('static int line_rows(');s=s[:a]+h+s[a:]
s=s.replace('    const int m = o.n, nr = 2 * m;', '    const int m = o.n, nr = 2 * m;\n    int fee_m __attribute__((cleanup(line_fee_end))) = m; mark(58,100+m);',1)
(w/'prof/fees.c').write_text(s)
s=(w/'prof_run.py').read_text();s=s.replace('seg, cnt, tot, last, poses, raw = [], [], [], [], [], []','seg, cnt, tot, last, poses, raw, fees = [], [], [], [], [], [], []')
s=s.replace('        sg = np.zeros(64);', '''        entered=None
        for mid,val,fuel in state['cur']:
            if mid==58 and val>100: entered=(val-100,fuel)
            if mid==58 and val < -100 and entered is not None:
                fees.append((entered[0],entered[1]-fuel));entered=None
        sg = np.zeros(64);''')
s=s.replace('seg=np.array(seg), cnt=', 'fees=np.array(fees), seg=np.array(seg), cnt=')
(w/'prof_fees_run.py').write_text(s)
