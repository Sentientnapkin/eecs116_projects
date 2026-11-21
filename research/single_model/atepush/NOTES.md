# atepush NOTES (ATE-axis agent; own dir only; no git; holdout/fold-4-sealed never touched)

Goal: lower mean unaligned ATE (and >3 m tails) on B17 (16 M) and T4uB (4.1 M) without >1.5x peak fuel.
Rules: dev = fresh folds 0-2, confirm = fresh fold 3; 3 reps for recommendations; switches-off bit-identical.

## Tooling (copied/adapted from tier1m)
- ap.c = tier1m/t1m_T4uB.c minus its 23 top defines. Configs: B17.defs (LI_GATENET=0.2 LI_PVS=1), T4uB.defs (23 defines).
  VERIFIED: ap.c+T4uB.defs wasm byte-identical to t1m_T4uB.wasm (e13ccbbf...); ap.c+B17.defs (+TC_LOG) fresh-711 ATE
  identical to B17 (gnp_r0) 711/711 (peak 16.1 M, = b17_exact outputs). One source for both bases.
- ev.sh NAME CFG "EXTRA" [rep] (build + fresh-711, W=48, table tables/NAME.json, results results/single_model/apf_NAME);
  q.sh JOBFILE (2 parallel); cmp.py BASECFG NAME [r1 r2] (paired vs gnp_r* / T4uB r*: dev f0-2, conf f3, tails f0-3).
- runpool.py NAME WASM POOLDIR: small pools pool_bad (40 worst dev flights by B17+T4uB ATE), pool_good (40 random dev), pool_e4.
- dg.py RUNDIR OUT (TC_LOG=1 runs): per-flight oracle attribution; dgsum.py summary. dg_B17log.json, dg_T4uBlog.json.
- mk_ape.py: ap.c + edge_mod.c + edge_rows.c -> ape.c with EDGE switch. EDGE=0 builds byte-identical (B17 81aebdfb..., T4uB e13ccbbf...).

## 1. Diagnosis (B17 / T4uB fresh f0-3, n=582)
- mean 0.342 / 0.381; removing best rigid translation 0.222 / 0.251.
- Oracle 'zero the error increments in frames of class X' (post hoc): starved classes (accepted feats <3 per 1 s, live<20)
  make it WORSE (the corrections happen in good frames, so increment attribution is confounded); only Pv>0.10 (36-47 % of
  frames) helps (+0.03 / +0.07) and removes all >3 m tails. => error is velocity error while velocity is weakly observed.
- Worst flights are ProcTHOR untextured houses (scenes 85, 100, 166, 154, 142, 122, 151, 176): live corner tracks <20 for
  60-95 % of frames, ~10 accepted features/s vs ~50 on good flights, pv re-anchor saturated at TC_MAXANCH=12.
  Images: flat-shaded untextured wall polygons against black; frames fully black at times. Information left = polygon
  vertices (few corners) and long straight polygon EDGES -> edgelet idea.

## 2. Cheap arms on B17 (1 rep, vs gnp_r0)
| arm | dev d | conf3 d | >1/3/5 f0-3 (base 20/3/0) | all711 | peak |
| m40 TC_MAXANCH=40 | -0.001 | -0.003 | 19/3/0 | 0.336 | 16.09 |
| m40p15 + TC_PV_THR=0.15 | -0.001 | +0.010 | 19/4/0 | 0.336 | 16.75 |
| m40s1 m40 + TC_RE_SCALE=1.0 | -0.001 | -0.030 [-0.089,+0.002] | 17/1/0 | 0.333 | 16.07 |
| p15 TC_PV_THR=0.15 | +0.017 | +0.079 | 21/6/2 | 0.364 | REJECT |

## 3. EDGE (edgelets as point-on-line MSCKF features), first try
Design: edge_mod.c (1-D normal search tracking every frame, gyro de-rotated; spawn in 8x6 cells free of corners while
live corners < EDGE_LIVE=30), edge_rows.c (point anchored on first ray, 1 residual/obs n.(z - pi(P)), null space on the 2
directions orthogonal to the 3-D line, gate as feature_rows, noise EDGE_PIX=1 px).
pool_bad (40): B17 1.067 -> EDGE 1.284 (mixed: 176-06 1.67->0.52, 85-01(mid) 1.97->1.32 but 85-01 2.63->4.33, 171-05 0.74->2.80).
Rows are used (~17 rows/s on 85-01). Next: validate measurement model against truth poses (EO debug lines).
- Truth-pose check of logged edgelet features (echk.py, frame mapping verified: offset 0 best): rms normal residual median
  0.2-0.6 px, p90 1.1-3.3 px, 1-14 % of features > 2 px (outlier tracks); NIS median 0.08-0.14 => the chi2 gate is weak in
  starved flights (large P), outliers get through. Added EDGE_RMAX (reject if post-depth-fit rms normal residual with the
  estimated clone poses > EDGE_RMAX px). pool.sh NAME CFG "EXTRA" POOL runs pool tests (nohup).
- (interruption 2: m40s1_r1/r2 kept running from jobs2.txt; Tm40s1, s1 queued after them)
- 3-rep m40s1 (TC_MAXANCH=40 TC_RE_SCALE=1.0) on B17: dev +0.002 [-0.001,+0.005], conf3 -0.019 [-0.061,+0.002], >3 m f0-3
  2.3 -> 0.7 per rep, all711 0.337 -> 0.336. Tail-only effect, dev does not support; not adopted alone.
- EDGE debugging: edges ALWAYS on (EDGE_LIVE=100) on pool_good hurt 0.265 -> 0.313 although truth residuals are clean
  (rms 0.24 px, no >2 px after RMAX) and clone Jacobians match finite differences (rel err 1e-6). Control with edge rows
  disabled (EDGE_MINOBS=99) = base 0.265 (no side effects). Cause: the edgelet SLIDES along the edge (median 8-46 px, p90
  30-110 px between first and last observation) and the measured normal has 1-3 deg error, so the residual depends on
  where P sits along the 3-D line; eliminating only the 2 directions orthogonal to the line leaves that dependence in the
  update as false information. Slide-dependent noise (EDGE_SANG=0.05) did not help (0.313).
  FIX EDGE_NS3=1: eliminate all 3 directions of P (P free along the line too; m-3 rows): pool_good 0.267 (neutral with
  edges always on), pool_bad 1.022 (base reps 1.067/1.005/0.945, mean 1.006): harmless but no gain yet.
- RELOC ORACLE (reloc_oracle.py, truth, B17 fresh 711): resetting the position error to the keyframe's error whenever the
  true camera is within 1 m / 30 deg of a keyframe from the first 1-5 s: 0.338 -> 0.316-0.327 (revisits ~4-6 % of frames;
  >1 m flights 25 -> 20). Ceiling of 'relocalize against startup keyframes' is only -0.01..-0.02 => idea 2 NOT pursued.
  Startup-group flights (151-03, 74-02, 106878858-01): offset 2-4 m built in 0.5-5 s (dv 1-2.6 m/s), then frozen (dv<0.2).
- EDGE on T4uB (GOV path integrated: tracking cost GC_EDGE/edgelet, rows within budget, detection with EDGE_GCDET reserve):
  pool_bad tS 1.164 / tC 1.170 vs T4uB reps 1.252/1.167/1.037 (mean 1.152): neutral; peak 5.06 M (vs 4.0).
- B17 pool_bad: ens3 1.022, eC(LIVE100) 0.971, eB(PIX0.5,N64,LIVE100) 0.997, eA(PIX0.5) 1.114 vs base 1.006 (reps 1.067/1.005/0.945).
  On the 5 most starved flights (live<20 >50 % of frames): base 1.76 -> 1.47-1.59 (eA 1.79). Fresh-711 runs eS/eC/eB queued.
- NOTE: interruption left a second jobs2 queue; killed its 's1' run to respect <=96 workers. ev.sh default W now 32.
- FRESH-711 EDGE (1 rep, B17): eS (NS3 RMAX1, LIVE30) dev -0.001 [-0.013,+0.010], conf3 +0.023, all 0.341;
  eC (always on) dev -0.006 [-0.016,+0.003], conf3 +0.020, >3 m 3->1, all 0.335, peak 18.2 M. => EDGE NEUTRAL; not adopted.
- STARTUP-GROUP MECHANISM (TC_LOG per 0.5 s, 106878858-01, 74-02): 45-60 live tracks but most attempted features fail the
  chi2 gate or triangulation from ~1.5-3 s (2.5-3.0 s: att 42, gated 19, tri-fail 16, accepted 7) while the velocity runs
  away to 2-3.8 m/s with sqrt(tr Pv) only 0.15-0.3 (overconfident 10x): a gate-rejection divergence spiral. A good static
  flight gates ~3 %. => GINF (gate-consensus velocity covariance inflation, in tc_monitor, both paths): if over the last
  GI_WIN=20 frames >= GI_MINATT=10 features were attempted and >= GI_FRAC=0.5 failed gate/triangulation, add GI_SD^2=0.25 to
  each velocity variance (at most every GI_GAP=20 frames). Also untested so far: INV_HUBER (existing switch).
- pool_bad (1 run each, sd ~0.05): GINF 0.982, GI_SD=1.0 1.038, GI_FRAC=0.4 1.094, INV_HUBER=3 1.149 (base 1.006); GINF pool_good 0.265 (neutral). GINF helps startup-group flights (74-02 0.48, 176-05 0.87, 6-00 0.83). Fresh: jobs4 (gi, Tgi, gi10).
- Tm40s1 (T4uB + TC_MAXANCH=40 TC_RE_SCALE=1.0, 1 rep): dev -0.012 [-0.051,+0.013], conf3 -0.037 [-0.078,-0.003], all711 0.384 -> 0.373, peak 4.00 M. Reps queued (jobs5).
- FRESH (1 rep): GINF B17 dev -0.000 [-0.015,+0.014], conf3 -0.021, >3 m 3->0 | T4uB Tgi dev +0.019, conf3 +0.008 => GINF NOT adopted.
  GREG (immediate re-gate with Pv inflation) pool_bad 0.990 / pool_good 0.274: same as GINF, not pursued on fresh.
- *** eB (EDGE=1 RMAX=1 NS3=1 PIX=0.5 N=64 grid 10x8 LIVE=100, i.e. edgelets ALWAYS on, more of them, tighter noise):
  dev -0.012 [-0.027,+0.004], conf3 -0.020 [-0.052,-0.000], all711 0.338 -> 0.321, >3 m 3->2, peak 23.5 M (1.46x).
  First real ATE gain. jobs7: eB reps, TeB (T4uB), Tm40s1 reps, eD (N=96 12x8), eE (PIX=1.0).
