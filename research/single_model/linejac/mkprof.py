"""mkprof.py src.c out.c : insert PH(id) phase marks (cleanup-attr) at function entries for fuel profiling (PROF build only)."""
import re, sys
src = open(sys.argv[1]).read()
ids = {'propagate':1,'imu_measurements':2,'lc_step':3,'vision':4,'build_pyramid':5,'track_all':6,'add_clone':7,'record_observations':7,'vision_zupt':7,
 'remove_oldest_clone':7,'take_for_update':7,'map_relocalize':8,'detect':9,'write_state':10,'build_rows':11,'solve_dx':12,'update':13,'feature_rows':14,
 'triangulate':15,'lc_stage_prep_part':20,'lc_conv0':21,'lc_conv1':22,'lc_conv2':23,'lc_conv3':24,'lc_head':25,'lc_apply':26,'lc_gray128':27,'save_state':28,'restore_state':28,'inject':29,'klt':30,'klt_i':30,'lc_begin':27,'lc_gray_pair':27,'ns_prep_rows':20,'ns_var':20,'ns_pool':20,'ns_conv0':21,'ns_conv1':22,'ns_conv2':23,'ns_conv3':24,'ns_head':25,'propagate_cov':1,'hp_f32':57,'line_track_all':60,'line_detect':60,'line_rows':61}
hdr = '''#ifdef PROF
__attribute__((import_module("env"), import_name("mark"))) void mark(int id, int val);
static int ph_cur = 0;
static inline int ph_begin(int id) { int sv = ph_cur; ph_cur = id; mark(id, 0); return sv; }
static inline void ph_end(int *sv) { ph_cur = *sv; mark(*sv, 0); }
#define PH(id) int _ph __attribute__((cleanup(ph_end))) = ph_begin(id)
#else
#define PH(id)
#endif
'''
lines = src.split('\n'); out = []; done = set()
# insert header after the first #include block
first_inc = max(i for i,l in enumerate(lines[:2000]) if l.startswith('#include'))
for i, l in enumerate(lines):
    out.append(l)
    if i == first_inc: out.append(hdr)
    m = re.match(r'^(?:static )?(?:inline )?(?:int|void|double)\s+(\w+)\(.*\)\s*\{\s*$', l)
    if m and m.group(1) in ids and '/*' not in l[:2]:
        out.append('    PH(%d);' % ids[m.group(1)]); done.add(m.group(1))
print('instrumented', sorted(done), 'missing', sorted(set(ids)-done), file=sys.stderr)
open(sys.argv[2], 'w').write('\n'.join(out))
# --- fine section marks
s = open(sys.argv[2]).read()
def ins(anchor, mid, count=1):
    global s
    assert s.count(anchor) >= 1, anchor
    s = s.replace(anchor, '    PM(%d);\n' % mid + anchor, 1)
s = s.replace('#define PH(id) int _ph', '#define PM(id) do { ph_cur = id; mark(id, 0); } while (0)\n#define PH(id) int _ph', 1)
s = s.replace('#define PH(id) int _ph', '#define PV(id,v) do { int _c = ph_cur; mark(id, (v)); mark(_c, 0); } while (0)\n#define PH(id) int _ph', 1)
s = s.replace('#else\n#define PH(id)\n', '#else\n#define PM(id)\n#define PV(id,v)\n#define PH(id)\n', 1)
ins('    int nzc[6 * MAX_OBS], nnz = 0, seen[MAX_CLONES + 1] = {0};', 31)
ins('    for (int c = 0; c < 3; c++) { /* left null space of Hf */', 32)
ins('    int k0 = m - 3;\n    const double *H0 = Hx + 3 * MAXD', 33)
ins('        for (int a = 0; a < k0; a++) {\n            v128_t acc[MAX_OBS + 1];', 34)
ins('    if (!cholesky(Sm, k0)) return 0;', 35)
ins('    if (*nrows + k0 > MAX_ROWS) return 0;', 36)
ins('#if MAP_MODE\n    if (o_in->tid >= 0 && o.n >= MAP_MIN_OBS) map_add', 37)
open(sys.argv[2], 'w').write(s)
s = open(sys.argv[2]).read()
s = s.replace('    double noise = (PIXEL_STD / fx) * (PIXEL_STD / fx), dx[MAXD], dxn[MAXD]', '    PV(40, nbatch);\n    double noise = (PIXEL_STD / fx) * (PIXEL_STD / fx), dx[MAXD], dxn[MAXD]', 1)
s = s.replace('    int nclone_cols = D - CORE;\n    if (nrows > nclone_cols) {', '    PV(41, nrows);\n    int nclone_cols = D - CORE;\n    if (nrows > nclone_cols) {', 1)
open(sys.argv[2], 'w').write(s)
# --- fuelpush fine marks inside update() (48-53) and solve_dx() (54-57)
s = open(sys.argv[2]).read()
def ins_in(s, start, anchor, mid):
    i = s.index(start); j = s.index(anchor, i)
    return s[:j] + '    PM(%d);\n' % mid + s[j:]
U = 'static int update(const double *r, const double *H, int k, double noise, double gate) {'
SD = 'static int solve_dx(const double *r, const double *H, int k, double noise, double *dx) {'
try:
    s = ins_in(s, U, '#if F32HP\n    if (k >= F32_KMIN) hp_f32', 48)
    s = ins_in(s, U, '        static double HT[MAXD * (MAXK + 2)];', 49)
    s = ins_in(s, U, '    if (!cholesky(Sm, k)) return 0;', 50)
    s = ins_in(s, U, '    { /* Kt = S^-1 HP', 51)
    s = ins_in(s, U, '    double dx[MAXD];\n    for (int j = 0; j < D; j += 6)', 52)
    s = ins_in(s, U, '        static double srow[4][MAXD + 8];', 53)
    s = ins_in(s, SD, '#if F32HP\n    if (k >= F32_KMIN) hp_f32', 54)
    s = ins_in(s, SD, '        static double HT[MAXD * (MAXK + 2)];', 55)
    s = ins_in(s, SD, '    if (!cholesky(Sm, k)) return 0;', 56)
except ValueError as e:
    print('fine marks skipped', e, file=sys.stderr)
open(sys.argv[2], 'w').write(s)

s = open(sys.argv[2]).read()
a = '    for (int u = 0; u < units && lc_active && !lc_applied && ns_pos < NS_STEPS; u++) { if (NS_DELAY && ns_pos >= 16 && lc_frame < LC_K + NS_DELAY) break; if (!ns_do(ns_pos)) break; ns_pos++; }'
if a in s:
    s = s.replace(a, a.replace('if (!ns_do(ns_pos)) break;', 'mark(58, ns_pos); { int ok_ = ns_do(ns_pos); mark(59, ns_pos); if (!ok_) break; }'))
else: print('ns step marks skipped', file=sys.stderr)
open(sys.argv[2], 'w').write(s)

s = open(sys.argv[2]).read()
s = s.replace('    /* Gauss-Newton on the 4 line DoF (numeric Jacobian) */', '    PM(61);\n    /* Gauss-Newton on the 4 line DoF (numeric Jacobian) */', 1)
s = s.replace('    /* Jacobians: line (NP, numeric)', '    PM(62);\n    /* Jacobians: line (NP, numeric)', 1)
a = s.index('static int line_rows('); b = s.index('    int nzc[6 * MAX_OBS]', a); s = s[:b] + '    PM(13);\n' + s[b:]
open(sys.argv[2], 'w').write(s)
s=open(sys.argv[2]).read()
a=s.index('static int line_rows(');b=s.index('    PM(13);',a);s=s[:b]+s[b:].replace('PM(13)','PM(59)',1)
u=s.index('static int update(const double *r, const double *H, int k, double noise, double gate) {')
e=s.index('\nstatic ',u+20)
part=s[u:e]
for anchor,id in [ ('    int nz[MAXD], nnz = 0;',48),('        static double HT[MAXD * (MAXK + 2)];',49),('    if (!cholesky(Sm, k))',50),('    { /* Kt = S^-1 HP',51),('    double dx[MAXD];',52),('        static double srow[4][MAXD + 6];',53) ]:
 if anchor in part: part=part.replace(anchor,f'    PM({id});\n'+anchor,1)
s=s[:u]+part+s[e:];open(sys.argv[2],'w').write(s)
