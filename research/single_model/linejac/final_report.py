from pathlib import Path
import json,hashlib
w=Path(__file__).resolve().parent
A=json.loads((w/'tables/ajc_final.json').read_text());B=json.loads((w/'tables/ajgb4_final.json').read_text())
assert len(A)==len(B)==7
GA=json.loads((w/'tables/ajc_gates.json').read_text());GB=json.loads((w/'tables/ajgb4_gates.json').read_text())
assert not GA['pass'] and not GB['pass']
for p in [w/'final/preflight',w/'final/preflight_arith']:
 assert '738/738 PASS; reset 8/8 PASS' in (p/'summary.txt').read_text()
lines=['# Task 1 final summary — analytic line Jacobians','',
'**Outcome: implementation and evaluation complete; no build passes all Task 1 gates. No build is recommended for holdout scoring.**','',
'Arithmetic-only (`ajc`) preserves accuracy within the plan\'s noise allowance, but exceeds the 4.5 M fuel target. Measured-cost/budget (`ajgb4`) reaches the fuel target, but regresses accuracy and creates a new >5 m flight. See the exact gate results in `tables/ajc_gates.json` and `tables/ajgb4_gates.json`.','',
'All entries below are means over 3 reps. Tails >3/>5/>10 m are summed over reps; peak is the maximum across frames/reps and p99 pools all frames. CIs use 10,000 paired scene-bootstrap resamples with all three replicates kept together per flight. All 4,368 flights/build completed with zero filled frames.','',
'## Compact comparison','',
'| set | GSLV ATE m | arithmetic ATE m | budget ATE m | arithmetic peak/p99 M | budget peak/p99 M |',
'|---|---:|---:|---:|---:|---:|']
for p in ['st2dev','st3','st2conf','fdev','fconf','st1dev','st1conf']:
 a,b=A[p],B[p];lines.append(f"| {p} ({a['n']}) | {a['base']:.4f} | {a['arm']:.4f} | {b['arm']:.4f} | {a['peak']:.3f}/{a['p99']:.3f} | {b['peak']:.3f}/{b['p99']:.3f} |")
lines += ['', '## Full arithmetic table (candidate only; fuel gate failed)','',(w/'tables/ajc_final.md').read_text(), '## Full budget table (rejected: accuracy/tails)','',(w/'tables/ajgb4_final.md').read_text(), '## Artifacts and validation','']
for name in ['gslv_linejac_arith','gslv_linejac_budget']:
 sha=hashlib.sha256((w/'final'/f'{name}.wasm').read_bytes()).hexdigest()
 lines += [f'- `{name}`: `final/{name}.c` and `final/{name}.wasm`; wasm SHA256 `{sha}`.']
lines += ['', 'Both: CMake -O3; zero imports; ABI PASS; 738/738 poison/prefix/repeat PASS (18 fixtures ×41 prefixes); reset 8/8 PASS; byte-identical rebuild; zero filled frames. Full outputs are in `final/preflight_arith/` and `final/preflight/`. All new switches off reproduce GSLV SHA256 `5e4d2a0d40333b3f5152d60de84a688abc5d0eec8c1c73fa402dc9907839d196` (also verified for the fused experimental source).','',
'Analytic implementation covers free, vertical, horizontal and heading-snapped models plus clone right rotation and translation with arbitrary camera extrinsics. Numeric checks: >210k real observation blocks; pose/constrained derivatives <3e-8 relative at eps=1e-6. Rare ill-conditioned free fits show central-difference truncation (max 4.85e-5 at eps=1e-6 → 4.85e-7 at eps=1e-7); a near-zero snapped block has small absolute but large relative finite-difference noise. Independent ~12k nondegenerate synthetic geometries pass <2.6e-8 for line and <5.3e-10 for pose at eps=1e-6. `analytic.h`, `tables/check*.txt`, `tables/synthetic_numeric.txt` contain derivation/check evidence. SIMD line kernels and Cholesky preserved trajectories on 156/156 flights each.','',
'## What failed','',
'- Analytic line Jacobians alone: st2dev r0 ATE 0.40416 vs GSLV 0.40421, peak 5.976M. Profiling showed substantial line null-space/gating and general EKF costs beyond finite differences.',
'- Exact SIMD line backend, forward-only EKF and SIMD Cholesky reduce fuel substantially, but the full protocol still exceeds 4.5M.',
'- Measured-cost governor alone: peak 4.830M on dev. With 3.2M budget: ATE +9.55%, new 5.406m flight (rejected). With 3.4M budget: full 3-rep results above; significant st3 regression and new 5.268m dev flight (rejected).',
'- Triangular normal-equation accumulation did not improve peak. Fusing line residual/Jacobian work preserves outputs on seven peak fixtures but saves only 22–44k; peak remains 5.006M, not adopted.',
'- No retry of EDGE_LCACHE, EDGE_LMAXF or blind EDGE_LROWX; measured admission costs were considered only after analytic/exact savings missed the target, as permitted by step 6. No governor variant was adopted.',
'', 'Holdout/fold 4/sealed data remained untouched; no training, private-server access, commits, pushes or uploads. All source changes and staged final artifacts are inside this work directory; canonical build/eval outputs are under `research/results/single_model/lj_*`.','', '## Historical session log','']
old=(w/'NOTES.md').read_text();old=old.replace('Status: IN PROGRESS. No candidate recommended yet.','Historical startup status: in progress; final outcome is above.')
text='\n'.join(lines)+old
(w/'NOTES.md').write_text(text)
status='No recommended build under Task 1 gates.\n\n'+ '\n'.join(f"{name}: {'PASS' if gate['pass'] else 'FAIL'}" for name,gate in [('arithmetic',GA),('budget',GB)])+'\n\nBoth preflights passed completely. Both source rebuilds match their evaluated wasm bytes.\nSee ../NOTES.md for full results, tails, confidence intervals and SHA256 values.\nNo holdout scoring was performed.\n'
(w/'final/STATUS.txt').write_text(status)
print('\n'.join(lines[:18]))
