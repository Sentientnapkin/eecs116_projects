# fuelpush NOTES (FUEL-AXIS agent; own dir only; no git; holdout untouched; fold-4/sealed never read)

Base: fp.c = tier1m/t1m_T4uB.c with the top defines wrapped in #ifndef (builds byte-identical to t1m_T4uB.wasm, sha e13ccbbf...).
New switches default 0 (= T4uB exact). Tools (copied from tier1m, retargeted): ev.sh NAME SRC "X=1 .." [rep] (fresh-711 -> tables/NAME.json;
LMAX=200 to skip load wait; W workers), prof.sh SRC TAG "-DX=1" [N] [REF] (profile + pose bit-compare; 64 mark slots, raw marks for frames<40),
brk.py TAG (breakdown heavy/zero-row frames), fc.py NAME [r1 r2] (vs T4uB 3 reps and B17; dev f0-2, confirm f3; area), preflight.sh, run_sel.py.
TMPDIR -> /data/backups/rganapa/Sebastian/tmp/fp_tmp (root fs / is 100% full: never write /tmp).

## Profile of T4uB (60 search flights): peak 3.99 M, p99 3.67, p95 3.27, median 1.66, mean 1.84
Peak frames = governor-capped MSCKF frames (25-29 rows). Per row (base): update 44k + solve_dx 23k + gate ~10k + null/tri 4k ~ 80k.
update() split (mean/frame): HP .170 S .057 chol .026 Kt .112 dx .008 Pupd .217; solve_dx HP .153 S .053 chol+dx .028.
Zero-row frames (30% of frames) cost 0.87-0.90 M: klt .22 pyr .21 detect .175 priors(update k=2-3) .146 map .03 prop .03.
Second MSCKF pass happens in ~11% of row frames (+~45k/row there).

## Exact / near-exact rewrites
| switch | what | check | effect |
|---|---|---|---|
| F_REUSE | update() after solve_dx on the same rows reuses HP and chol(S) | poses bit-identical 60/60 | mean 1.84->1.62, p99 3.67->3.09 |
| VKDYN | VK+pad block (6 states) only exists from frame K until the net lands (D 60->54) | bit-identical 60/60 | mean ->1.55, p99 2.99 |
| F_FWD | W=L^-1 HP (forward only), P-=W^T W, dx=W^T L^-1 r | rounding only | Kt .101->.051, mean 1.50 |
| F_LAZYH0 | ITER_BACK fallback rows copied only when a 2nd pass runs | exact | memcpy costs ~1 fuel/byte |
| F32PU / F32HP | f32x4 products for P-=W^T W and HP (P stays f64), k>=F32_KMIN(6) | approx | heavy frames 2.25->2.08 M |
| ITER_GOV, GC_ITER | 2nd pass only if budget has k*GC_ITER left | approx | for low budgets |
S1 = F_REUSE VKDYN F_FWD F_LAZYH0 (T4uB governor): fresh 0.384 (= T4uB r0 0.384, d +0.000), peak 3.74 M (T4uB 4.10), 0 filled.

Net micro-step costs (measured, S2 build): gray steps 0-31 47k each; prep 32-55 50-60k; var 56-59 117k; pool 60-61 ~100k;
conv0 62-73 ~102k; conv1 75-85 160k; conv2 86-91 98-147k; conv3 92-94 88-132k; head 95/96 174k/268k (head 1 includes lc_apply update).
GC_UNIT=160k overestimates gray/prep steps ~3x -> a per-step cost table lets the governor land the net much sooner at low budgets.

NS_COST (+NS_CM 1.12 margin, NS_UMAX): governor runs net micro-steps while gov_used + ns_cost(step) <= GOV_B (cost table above).
Jobs run with nohup (pj.sh = profiles of G configs, logs/prof_g*.txt). Session interrupted twice: always check `ps` before relaunch.

F_GATEM (near-exact): gate S from 2x6 observation blocks of Hx P Hx^T + the 3 null-space reflections; gate decisions/poses identical
on 30 profiled flights; gate 262k -> 70k on 27-row frames. F32KT: forward substitution + dx in f32 (~-60k on 27-row frames).
Profile peak overshoot over GOV_B ~0.2-0.3 M (estimate error).

## fresh-711 results
| name | config | peak M | fresh | vs T4uB d | dev/conf | >3/5/10 | area vs B16 / vs T4uB |
|---|---|---|---|---|---|---|---|
| S1 | REUSE VKDYN FWD LAZYH0 | 3.74 | 0.384 | +0.000 | +0.001/-0.000 | 3/1/1 | +0.44 / +0.02 |
| G24 | S1+F32PU F32HP GATEM NS_COST ITER_GOV GC_ROW=50k GC_ITER=45k B=2.4M | 2.71 | 0.390 | +0.006 | +0.005/+0.037 | 2/0/0 | +0.54 / +0.12 |
| G20 | same, B=2.0M | 2.22 | 0.406 | +0.022 | +0.011/+0.063 | 5/1/0 | +0.53 / +0.11 |
| G20d | f64 kernels (no F32*), GC_ROW=56k, B=2.0M | 2.24 | 0.417 | +0.034 | +0.020/+0.096 | 5/0/0 | +0.46 / +0.04 |
