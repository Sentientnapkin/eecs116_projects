# fuel_b13 NOTES (fuel agent on B13 code path; own dir only; no git; holdout untouched)

Base: bulk/exact/b13x.c (B13 exact, defs in defs.txt, -O3 CMakeLists copy here). Working source: b13y.c (default = exact rewrites, approximate arms are #ifndef-defined, default off).
Tools: mkprof.py (inserts PH/PM phase marks -> PROF build), pcmp.sh SRC TAG [-Dflags] (profile build, 60 search flights, pose bit-compare vs frozen profile run, peak/median),
an.py (phase tables), ev.sh NAME SRC "DEFINES" REP (cmake build + fresh-711, matched replicate nudges as bulk), cmp.py PREFIX (paired vs frozen xC reps), mkwasm.py, run_fresh_fb.py.
Frozen fresh-711 reference (bulk/tables bk_xC, xCr1, xCr2): mean 0.405/0.418/0.394, >3/5/10 = 10-11/3-6/0, peak 20.17 M.

## 1. Profile of B13 (60 search flights, 72 000 frames; prof_b13.txt). peak 18.26 M, p99 12.8, median 6.50, mean 6.82
Fixed floor every frame (M): klt 3.2 (60 tracks, FB on half) + detect 1.0 + pyramid 0.50 + propagate 0.15 + map_relocalize 0.23 avg (4.9 at one frame/300) = ~5.3 M.
Peak frames (21-23, 61-63, 101-103: the window slide cohort; nbatch only ~8 features but ~62 rows -> QR to 36-42 rows; D = 60 with the transient 7th clone), top 0.5% frames (14.0 M mean):
QR compression 2.0 (4.7 at peak), solve_dx 2.6 (iteration-0 dx; unoptimised scalar code), update() 1.95, gate H0P 0.9 (2.0 at peak, both passes), gate S 0.46, nullspace 0.35, chol 0.14, triangulate 0.15; klt 3.4, detect 1.0.
Startup: frame 0 5.2 (detect 2.95 + gray128 2.1), net prep frame 5 = 9.4 (net prep 3.6 + gray128 2.1 + klt), net conv frame 6 = 8.4-10.5 (conv 4.2); first slide frames 21-23 up to 15-18 M.
Iterated update = two passes of build_rows (feature_rows + QR) + solve_dx + final update.

## 2. Exact rewrites (bit-identical poses on the 60 profiled flights; fresh-711 ATE compare in section 4)
* E1 QR compression (build_rows): column-chunked (6/2/1 columns) register accumulators, same per-element order: QR 4.7 -> 2.8 M at peak.
* E2 solve_dx: same register-blocked HP/S kernels as update() plus SIMD dx: 2.6 -> 0.9 M.
  Peak (60 flights) 18.26 -> 14.67 M, median 6.50 -> 6.06, mean 6.82 -> 6.26.
* Tried and discarded: skipping zero-v rows in the Householder loops (no zero rows: no gain, peak 15.07).
