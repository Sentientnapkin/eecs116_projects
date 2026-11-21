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
