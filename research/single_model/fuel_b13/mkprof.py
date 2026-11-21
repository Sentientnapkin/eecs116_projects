"""mkprof.py src.c out.c : insert PH(id) phase marks (cleanup-attr) at function entries for fuel profiling (PROF build only)."""
import re, sys
src = open(sys.argv[1]).read()
ids = {'propagate':1,'imu_measurements':2,'lc_step':3,'vision':4,'build_pyramid':5,'track_all':6,'add_clone':7,'record_observations':7,'vision_zupt':7,
 'remove_oldest_clone':7,'take_for_update':7,'map_relocalize':8,'detect':9,'write_state':10,'build_rows':11,'solve_dx':12,'update':13,'feature_rows':14,
 'triangulate':15,'lc_stage_prep':20,'lc_conv0':21,'lc_conv1':22,'lc_conv2':23,'lc_conv3':24,'lc_head':25,'lc_apply':26,'lc_gray128':27,'save_state':28,'restore_state':28,'inject':29,'klt':30,'lc_begin':27}
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
first_inc = max(i for i,l in enumerate(lines[:80]) if l.startswith('#include'))
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
