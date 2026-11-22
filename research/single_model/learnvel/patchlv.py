"""patchlv.py BASE.c OUT.c : wrap the leading #define block in #ifndef, add learnvel switches LV_PERIOD / LV_PSCALE / LV_PLIVE / LV_BGC (all off by default)."""
import sys
s = open(sys.argv[1]).read(); lines = s.split('\n'); i = 0; top = []
while lines[i].startswith('#define '): top.append(lines[i]); i += 1
s = ''.join(f"#ifndef {l.split()[1]}\n{l}\n#endif\n" for l in top) + '\n'.join(lines[i:])
s = """#ifndef LV_PERIOD
#define LV_PERIOD 0         /* learnvel: periodic net re-anchor every LV_PERIOD frames (fire 6), 0 off */
#endif
#ifndef LV_PSCALE
#define LV_PSCALE TC_RE_SCALE /* learnvel: sigma scale of periodic re-anchors */
#endif
#ifndef LV_PLIVE
#define LV_PLIVE 100000     /* learnvel: periodic fire only while live tracks < LV_PLIVE */
#endif
#ifndef LV_BGC
#define LV_BGC 0            /* learnvel: clamp the gyro-bias estimate to +-LV_BGMAX (sim draws +-0.02 rad/s) */
#endif
#ifndef LV_BGMAX
#define LV_BGMAX 0.025
#endif
""" + s
old = "    for (int i = 0; i < 3; i++) { vel[i] += dx[V + i]; pos[i] += dx[P + i]; bg[i] += dx[BG + i]; ba[i] += dx[BA + i]; }"
assert s.count(old) == 1
s = s.replace(old, old + "\n#if LV_BGC\n    for (int i = 0; i < 3; i++) { if (bg[i] > LV_BGMAX) bg[i] = LV_BGMAX; if (bg[i] < -LV_BGMAX) bg[i] = -LV_BGMAX; }\n#endif")
old = "        if (TC_PERIOD > 0 && moving && tc_live_run >= TC_LIVE_N && tc_frame - tc_last_fire >= TC_PERIOD && tt > TC_T1) fire = 2;\n"
assert s.count(old) == 1
s = s.replace(old, old + "\n#if LV_PERIOD > 0\n        if (!fire && live < LV_PLIVE && (moving || (LI_PVS && tt >= LI_PVS_T0)) && tt >= TC_T0 && tc_frame - tc_last_fire >= LV_PERIOD) fire = 6;\n#endif\n")
old = "        tc_fire = 0; tc_nanch++;\n        tc_lcscale = (float)TC_RE_SCALE; tc_lcfloor = (float)TC_RE_FLOOR;"
assert s.count(old) == 1
s = s.replace(old, "#if LV_PERIOD > 0\n        tc_lcscale = (float)(tc_fire == 6 ? LV_PSCALE : TC_RE_SCALE); tc_lcfloor = (float)TC_RE_FLOOR;\n        tc_fire = 0; tc_nanch++;\n#else\n" + old + "\n#endif")
open(sys.argv[2], 'w').write(s); print('ok')
