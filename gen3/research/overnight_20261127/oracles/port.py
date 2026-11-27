from pathlib import Path
p=Path('/data/backups/rganapa/Sebastian/gen3')
base=p/'agents/anchors/base_sn.c'; i3=p/'research/i3'; out=Path('/tmp/vio_overnight/oracles'); s=base.read_text(); old=s
o=(i3/'src_or.c').read_text(); macros=o[o.index('#ifndef OR\n'):o.index('static inline int32_t hsum4')]
s=s.replace('#include <wasm_simd128.h>','#include <wasm_simd128.h>\n'+macros,1)
block=(i3/'tools/or_block.c').read_text()
assert s.count('int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {')==1
# Keep all oracle-only code behind OR; do not touch estimator source behavior in OR=0.
needle='int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {'
s=s.replace(needle,block+'\n'+needle,1)
needle='        initialize(imu, imu_count, t);\n'
assert s.count(needle)==1
s=s.replace(needle,needle+'#if OR\n        or_init(imu); or_step();\n#endif\n',1)
needle='    for (int r = 0; r < imu_count; r++) propagate(imu + 7 * r);\n'
assert s.count(needle)==1
s=s.replace(needle,needle+'#if OR\n    or_k++;\n#endif\n',1)
# Apply at end of frame, after regular estimator work.
needle='    write_state(out);\n#if HARDEN\n    hz_out_guard(out);\n#endif\n    if (GATE_DEBUG'
assert s.count(needle)==1
s=s.replace(needle,'#if OR\n    or_step();\n#endif\n'+needle,1)
(out/'sn_or.c').write_text(s)
# Add explicit diagnostics so lookup, attempted, and accepted velocity updates are auditable per flight.
pf=Path('/tmp/vio_overnight/oracles/sn_or.c'); z=pf.read_text()
z=z.replace('static double or_s[40]; static long or_cnt; static long or_tri_h[8];','static double or_s[40]; static long or_cnt; static long or_tri_h[8]; static long or_vlook, or_vtry, or_vok;')
z=z.replace('    if (or_i < 0) { fprintf(stderr, "ORX nomatch\\n"); return; }','    if (or_i < 0) { fprintf(stderr, "ORX nomatch\\n"); return; }\n    or_vlook = 1;')
z=z.replace('        or_upd(r, 3, OR_VEL);','        or_vtry++; or_vok += or_upd(r, 3, OR_VEL);',1)
z=z.replace('            or_upd(r, 1, OR_VEL);','            or_vtry++; or_vok += or_upd(r, 1, OR_VEL);',1)
z=z.replace('            or_upd(r, 3, OR_VEL);','            or_vtry++; or_vok += or_upd(r, 3, OR_VEL);',1)
z=z.replace('        r[0] = vk[2] * (1 + or_scale) + or_noise(C_VZ, 0, OR_VEL, t) - vel[2]; or_H[V + 2] = 1; or_upd(r, 1, OR_VEL);','        r[0] = vk[2] * (1 + or_scale) + or_noise(C_VZ, 0, OR_VEL, t) - vel[2]; or_H[V + 2] = 1; or_vtry++; or_vok += or_upd(r, 1, OR_VEL);')
z=z.replace('            fprintf(stderr, "\\n");\n        }\n    }\n}\n/* GT-pose triangulation','            fprintf(stderr, "\\nORV %d %ld %ld %ld\\n", or_i, or_vlook, or_vtry, or_vok);\n        }\n    }\n}\n/* GT-pose triangulation',1)
pf.write_text(z)
