from pathlib import Path
w=Path(__file__).resolve().parent;s=(w/'lj.c').read_text()
a=s.index('static int line_take_b(')
code='''#ifndef LJ_LCOST
#define LJ_LCOST 0
#endif
#if LJ_LCOST
/* Measured 60-st2dev/23060 line calls, optimized arithmetic: upper envelope
   by retained observations (3..7): 80010,119180,178204,253673,356872 fuel.
   20% allowance for repeat linearizations; backend measured ~50k/output row.
   Constrained fits can emit 2*n-2 rows (free fits emit 2*n-4).
   Convert the measured total to the governor's existing 105k row units. */
static int lj_line_charge(int n) {
    static const double fit[8]={0,0,0,80100,119200,178300,253700,356900};
    double cost=n<=7?fit[n]:356900+(n-7)*130000.0;
    return (int)ceil((1.2*cost+50000.0*(2*n-2))/GC_ROW);
}
#define LJ_CHARGE(n) lj_line_charge(n)
#else
#define LJ_CHARGE(n) (2*(n)-4+EDGE_LROWX)
#endif
'''
s=s[:a]+code+s[a:];a=s.index('static int line_take_b(');b=s.index('static void line_drop_clone',a);p=s[a:b]
p=p.replace('2 * llost[q].n - 4 + EDGE_LROWX','LJ_CHARGE(llost[q].n)').replace('2 * o->n - 4 + EDGE_LROWX','LJ_CHARGE(o->n)')
s=s[:a]+p+s[b:];(w/'lj.c').write_text(s)
