"""mkgrav.py SRC.c WEIGHTS.h OUT.c : insert the gravity-net module (gr_core.h + weights, all under #if LV_GRAV) and its hooks into SRC."""
import sys
from pathlib import Path
H = Path(__file__).resolve().parent
src, wh, out = Path(sys.argv[1]).read_text(), Path(sys.argv[2]).read_text(), sys.argv[3]
src = '#ifndef LV_GRAV\n#define LV_GRAV 0           /* learnvel: learned gravity-direction measurement */\n#endif\n' + src
a = '/* B: monitor. Per-frame filter-internal signals; fires a re-anchor of the learned net. */'
assert src.count(a) == 1
src = src.replace(a, '#if LV_GRAV\n' + wh + (H / 'gr_core.h').read_text() + '#endif\n' + a)
b = 'static void tc_reset(void) { /* re-init: all tailcap state back to power-on values */'
assert src.count(b) == 1
src = src.replace(b, b + '\n#if LV_GRAV\n    gr_reset();\n#endif')
c = '        for (int u = 0; u < units && lc_active && !lc_applied && ns_pos < NS_STEPS; u++) { if (NS_DELAY && ns_pos >= 16 && lc_frame < LC_K + NS_DELAY) break; if (!ns_do(ns_pos)) break; ns_pos++; }\n    }'
assert src.count(c) == 1
src = src.replace(c, '''#if LV_GRAV
        int u = 0;
        for (; u < units && lc_active && !lc_applied && ns_pos < NS_STEPS; u++) { if (NS_DELAY && ns_pos >= 16 && lc_frame < LC_K + NS_DELAY) break; if (!ns_do(ns_pos)) break; ns_pos++; }
        { int live = 0; for (int i = 0; i < MAX_TRACKS; i++) live += tracks[i].alive; gr_tick(frame, imu, imu_count, units - u, live); }
#else
''' + c[:-6] + '\n#endif\n    }')
Path(out).write_text(src); print('wrote', out)
