# ---- 7. approximate / structural arms (default OFF) and parameter overrides   (exec'd by mkv.py; uses `src`)
import re as _re
for name in ['PIXEL_STD', 'DETECT_MIN_SCORE', 'GRID_X', 'GRID_Y', 'KLT_ITERS', 'MAX_UPDATE_FEATURES', 'MAX_CLONES', 'CLONE_EVERY', 'KLT_R', 'LEVELS']:
    m = _re.search(r'^#define ' + name + r' (\S+)(.*)$', src, _re.M)
    assert m, name
    src = src.replace(m.group(0), '#ifndef %s\n%s\n#endif' % (name, m.group(0)), 1)
src = src.replace('#ifndef F_PYR', '''#ifndef A_KLTF32
#define A_KLTF32 0  /* KLT in f32x4 (approximate) */
#endif
#ifndef DET_PERIOD
#define DET_PERIOD 1 /* re-score an empty detection cell only every DET_PERIOD-th frame */
#endif
#ifndef A_SPREAD4
#define A_SPREAD4 0  /* leaving tracks spread over 4 frames (quarters) instead of 3 (thirds) */
#endif
#ifndef F_PYR''', 1)
src = src.replace('i += clone_every - 1) {', 'i += (A_SPREAD4 ? clone_every : clone_every - 1)) {')
src = src.replace('        if (occupied[cell]) continue;\n', '        if (occupied[cell]) continue;\n        if (DET_PERIOD > 1 && (cell + frame_no) % DET_PERIOD) continue;\n', 1)
assert 'DET_PERIOD > 1 &&' in src

_a = src.index('static int klt(')
_end = src.index('\n}\n', _a) + 3
_klt_old = src[_a:_end]
_f32 = open('klt_f32.inc').read()
src = src.replace(_klt_old, '#if A_KLTF32\n' + _f32 + '#else\n' + _klt_old + '#endif\n')
