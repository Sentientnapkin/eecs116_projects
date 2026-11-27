"""mkprof.py: insert host fuel marks (env.mark(id)) into the preprocessed baseline src/pp.c -> src/prof.c.
A mark records the remaining fuel; the fuel between consecutive marks is charged to the segment named by the LATER mark."""
from pathlib import Path
P = Path(__file__).parent / 'src'
s = (P / 'pp.c').read_text()
def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (old[:80], n)
    s = s.replace(old, new)
hdr = '__attribute__((import_module("env"), import_name("mark"))) extern void i1m(int);\n'
rep('static void msckf_update(Obs *batch, int nbatch) {\n    int k = build_rows(batch, nbatch);\n    if (k) update(rbig, Hbig, k, (1.5 / fx) * (1.5 / fx), __builtin_inff());\n}',
    'static void msckf_update(Obs *batch, int nbatch) {\n    i1m(10); int k = build_rows(batch, nbatch); i1m(11);\n    if (k) update(rbig, Hbig, k, (1.5 / fx) * (1.5 / fx), __builtin_inff()); i1m(12);\n}')
rep('int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {\n    imu = hz_filter(imu, &imu_count);',
    'int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {\n    i1m(0); imu = hz_filter(imu, &imu_count); i1m(1);')
rep('        hz_out_guard(out);\n        return 0;\n    }\n    if (1) { cp_dt', '        hz_out_guard(out);\n        i1m(2); return 0;\n    }\n    if (1) { cp_dt')
rep('    for (int r = 0; r < imu_count; r++) propagate(imu + 7 * r);\n    if (1) propagate_cov();\n    if (imu_count) imu_measurements(imu, imu_count);\n',
    '    i1m(19); for (int r = 0; r < imu_count; r++) propagate(imu + 7 * r); i1m(3);\n    if (1) propagate_cov(); i1m(4);\n    if (imu_count) imu_measurements(imu, imu_count); i1m(5);\n')
rep('    tc_rows = 0;\n    vision(frame);\n', '    i1m(6); tc_rows = 0;\n    vision(frame);\n')
rep('build_pyramid(frame, cur); gov_used += 210e3;', 'i1m(9); build_pyramid(frame, cur); gov_used += 210e3; i1m(7);')
rep('        track_all(prev, cur, Rwc_now);\n', '        track_all(prev, cur, Rwc_now); i1m(8);\n')
rep('    int cap = 0 ? 100000 : gov_rows_cap();', '    i1m(9); int cap = 0 ? 100000 : gov_rows_cap();')
rep('    tc_rows = rw; gov_nb = nb;\n', '    i1m(13); tc_rows = rw; gov_nb = nb;\n')
rep('        detect(cur);\n        gov_used += gov_ncell * 20e3;', '        i1m(13); detect(cur); i1m(14);\n        gov_used += gov_ncell * 20e3;')
rep('    if (gov_maptries > 0 && 3.6e6 - gov_used > 150e3) { map_relocalize(1); gov_maptries--; gov_used += 150e3; gov_mapdid = 1; }\n}',
    '    i1m(13); if (gov_maptries > 0 && 3.6e6 - gov_used > 150e3) { map_relocalize(1); gov_maptries--; gov_used += 150e3; gov_mapdid = 1; } i1m(15);\n}')
rep('{ if (0 && ns_pos >= 16 && lc_frame < 5 + 0) break; if (!ns_do(ns_pos)) break; ns_pos++; }',
    '{ if (0 && ns_pos >= 16 && lc_frame < 5 + 0) break; i1m(16); { int r_ = ns_do(ns_pos); i1m(200 + ns_pos); if (!r_) break; } ns_pos++; }')
rep('    hz_watch();\n    write_state(out);\n    hz_out_guard(out);\n    if (0 == 2)', '    i1m(16); hz_watch(); i1m(17);\n    write_state(out);\n    hz_out_guard(out);\n    if (0 == 2)')
rep('gate_pairs) + 1000 * moving; }\n    return 0;\n}', 'gate_pairs) + 1000 * moving; }\n    i1m(18); return 0;\n}')
(P / 'prof.c').write_text(hdr + s)
print('ok')
