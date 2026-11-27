"""mkorc.py SRC OUT.c : insert ORC oracle hooks (ORC bit1 = oracle body velocity at frame K for the startup net measurement,
bit2 = oracle frame-0 tilt). Table from ana/oracle.json keyed by the first frame-0 IMU accel row. Offline diagnostics ONLY."""
import sys, json
src, out = sys.argv[1], sys.argv[2]
R = json.load(open('/data/backups/rganapa/Sebastian/gen3/research/r2/ana/oracle.json'))
s = open(src).read()
tab = ['#ifndef ORC\n#define ORC 0\n#endif\n#ifndef ORC_SD\n#define ORC_SD 0.03\n#endif\n#if ORC\n#define ORC_N %d\n' % len(R)]
f = lambda v: '{' + ','.join('%.12g' % x for x in v) + '}'
tab.append('static const double orc_key[ORC_N][3]={' + ','.join(f(r['key']) for r in R) + '};\n')
tab.append('static const double orc_vb5[ORC_N][3]={' + ','.join(f(r['vb'][5]) for r in R) + '};\n')
tab.append('static const double orc_ub0[ORC_N][3]={' + ','.join(f(r['ub0']) for r in R) + '};\n')
tab.append('static int orc_i=-1;\nstatic void orc_find(const double *imu){orc_i=-1;for(int i=0;i<ORC_N;i++){if(fabs(imu[1]-orc_key[i][0])<1e-7&&fabs(imu[2]-orc_key[i][1])<1e-7&&fabs(imu[3]-orc_key[i][2])<1e-7){orc_i=i;return;}}}\n#endif\n')
a = '#include <wasm_simd128.h>\n'; assert s.count(a) == 1; s = s.replace(a, a + ''.join(tab))
a = '    align_to_z(f, R);\n    memcpy(R0, R, sizeof R);\n'; assert s.count(a) == 1
s = s.replace(a, '    align_to_z(f, R);\n#if ORC & 2\n    if (orc_i >= 0) { double u[3]; for (int i = 0; i < 3; i++) u[i] = 9.81 * orc_ub0[orc_i][i]; align_to_z(u, R); }\n#endif\n    memcpy(R0, R, sizeof R);\n')
a = '        sd[i] = s < fl ? fl : s; mu[i] = lc_out[6 + i];\n    }\n'; assert s.count(a) == 1
s = s.replace(a, a + '#if ORC & 1\n    if (orc_i >= 0 && tc_nanch == 0) for (int i = 0; i < 3; i++) { mu[i] = orc_vb5[orc_i][i]; sd[i] = ORC_SD; }\n#endif\n')
a = '    imu = hz_filter(imu, &imu_count);\n#endif\n    if (!initialized) {\n'; assert s.count(a) == 1
s = s.replace(a, a + '#if ORC\n        if (imu_count > 0) orc_find(imu);\n#endif\n')
open(out, 'w').write(s)
