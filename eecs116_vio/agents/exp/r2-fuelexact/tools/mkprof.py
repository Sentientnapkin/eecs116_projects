"""mkprof.py SRC.c ACTIVE.txt OUT.c : PROF build. Inserts PH(id) (self-fuel phase marks via an env.mark host import,
restored on scope exit) at the entry of the ACTIVE definitions of the functions below. Fuel profile only; the mark
calls add a few instructions per call. Phase ids are printed by prof.py."""
import re, sys
src, act, out = sys.argv[1:4]
L = open(src).read().split('\n')
active = {int(l.split()[0]) for l in open(act) if l[:6].strip().isdigit()}
names = ['propagate', 'propagate_cov', 'imu_measurements', 'tc_prior', 'lc_step', 'lc_begin', 'sn_gray', 'sn_prep', 'sn_norm',
         'sn_conv0', 'sn_conv1', 'sn_conv2', 'sn_conv3', 'sn_head', 'lc_apply', 'vision', 'build_pyramid', 'extract', 'track_all',
         'track_half', 'klt', 'klt_i', 'detect', 'corner_score', 'record_observations', 'vision_zupt', 'add_clone',
         'remove_oldest_clone', 'take_for_update', 'map_relocalize', 'map_add', 'msckf_update', 'build_rows', 'feature_rows',
         'triangulate', 'edge_rows', 'line_rows', 'solve_dx', 'update', 'inject', 'cholesky', 'chol_solve', 'edge_track_all',
         'edge_detect', 'edge_record', 'line_track_all', 'line_detect', 'write_state', 'camera_pose', 'save_state',
         'restore_state', 'edge_drop_clone', 'line_drop_clone', 'esearch', 'etensor', 'fc_trirms', 'chi2_quantile']
ids = {n: i + 1 for i, n in enumerate(names)}
hdr = r'''#ifdef PROF
__attribute__((import_module("env"), import_name("mark"))) void mark(int id, int val);
static int ph_cur = 0;
static inline int ph_begin(int id) { int sv = ph_cur; ph_cur = id; mark(id, 0); return sv; }
static inline void ph_end(int *sv) { ph_cur = *sv; mark(*sv, 0); }
static int D;
static inline int ik_begin(int id, int v) { mark(id, v); return id; }
#define IKE(t) static inline void ik_end##t(int *sv) { mark(190 + t, D); }
IKE(0) IKE(1) IKE(2) IKE(3) IKE(4)
#define PH(id) int _ph __attribute__((cleanup(ph_end))) = ph_begin(id)
#define PM(id) do { ph_cur = id; mark(id, 0); } while (0)
#define PV(id,v) do { int _c = ph_cur; mark(100 + (id), (v)); mark(_c, 0); } while (0)
#endif
'''
done = []
res = []
first_inc = max(i for i, l in enumerate(L[:400]) if l.startswith('#include'))
pending = None
for i, l in enumerate(L):
    res.append(l)
    if i == first_inc: res.append(hdr)
    m = re.match(r'^(?:static )?(?:inline )?(?:int|void|double)\s+(\w+)\(', l)
    if m and m.group(1) in ids and (i + 1) in active and not l.rstrip().endswith(';'):
        pending = m.group(1)
    if pending and '{' in l:
        k = l.index('{')
        if l[k + 1:].strip() and not l[k + 1:].strip().startswith('/*'):
            raise SystemExit('code after brace, line %d: %s' % (i + 1, l))
        res.append('    PH(%d);' % ids[pending]); done.append(pending)
        if pending in ('update', 'feature_rows', 'line_rows', 'edge_rows', 'build_rows'):
            # inclusive cost per call: mark(180+t, k) at entry, mark(190+t, D) at exit
            t = ('update', 'feature_rows', 'line_rows', 'edge_rows', 'build_rows').index(pending)
            arg = 'k' if pending == 'update' else ('nbatch' if pending == 'build_rows' else '*nrows')
            res.append('    int _ik __attribute__((cleanup(ik_end%d))) = ik_begin(%d, %s);' % (t, 180 + t, arg))
        pending = None
open(out, 'w').write('\n'.join(res))
print('instrumented', len(done), 'missing', sorted(set(names) - set(done)), file=sys.stderr)
open(out + '.ids', 'w').write('\n'.join('%d %s' % (v, k) for k, v in ids.items()))
