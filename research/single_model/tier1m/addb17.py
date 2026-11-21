"""addb17.py IN OUT [default_on]: add LI_GATENET / LI_PVS (B17 switches, same code as lateinit/li.c) to a B16-path source"""
import sys
s = open(sys.argv[1]).read(); on = len(sys.argv) > 3 and sys.argv[3] == '1'
hdr = '''#ifndef LI_GATENET
#define LI_GATENET %s      /* B17: no gate-forced ZUPT once the startup net has predicted a speed above this (m/s) */
#endif
#ifndef LI_PVS
#define LI_PVS %s            /* B17: the pv re-anchor trigger also for static (hover) starts, from LI_PVS_T0 s on */
#endif
#ifndef LI_PVS_T0
#define LI_PVS_T0 3.0
#endif
''' % (('0.2', '1') if on else ('0.0', '0'))
s = hdr + s
a = 'if (TC_PV_THR > 0 && moving && tt >= TC_T0 && tc_frame - tc_last_fire >= TC_PV_PERIOD'
assert s.count(a) == 1
s = s.replace(a, 'if (TC_PV_THR > 0 && (moving || (LI_PVS && tt >= LI_PVS_T0)) && tt >= TC_T0 && tc_frame - tc_last_fire >= TC_PV_PERIOD')
a = '    if (median < ZUPT_DISPARITY || gate_force_zupt) {'
assert s.count(a) == 1
s = s.replace(a, '    if (LI_GATENET > 0 && gate_force_zupt && lc_active && lc_applied && sqrt(lc_out[6] * lc_out[6] + lc_out[7] * lc_out[7] + lc_out[8] * lc_out[8]) > LI_GATENET) gate_force_zupt = 0;\n' + a)
open(sys.argv[2], 'w').write(s)
