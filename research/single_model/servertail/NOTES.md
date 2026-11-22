# servertail NOTES (server-tail agent; own dir only; no git; holdout/fold-4/sealed untouched; never probe server episodes)

Base: HFG = audit/a.c HARDEN=1 F_REUSE=1 GATE_MODE=0 (final_hfg/t4ub_hfg.wasm sha 1945902e..1816b). Fresh-711 table: audit/tables/hFg.json
(results research/results/single_model/aud_f_hFg/eval/hFg-1945902e/<ep>/).
Server bad: 004c5894 3.46 (72.7 m, rot 0.28), cd6dc704 2.69 (58.9 m, scale 0.81), 21494468 2.28 (80.4 m), 8950399d 0.90 (39.5 m); e7aa5aee 0.47 (74.0 m).

## Session log
- S1 (start): read audit/lateinit/atepush/fuelpush notes. Local travel distributions (audit.travel_m):
  fresh-711 44.6 +- 9.6 (p90 56.7); raw-holdout 51.2 +- 11.3 (p90 65.1); raw-speed 36.5; server 59.6 +- 11.9.
  fresh = 2 planner settings: cruise 3-4.5/acc 6/jerk 30 (366) and cruise 4-6/acc 8/jerk 40 (345); travel limited by scene size.
  Generator: research/native_campaign.py generate --gen-roster R --gen-raw DIR (task_overrides), launcher gen/run_speed.sh; 8 GPUs free.
- Jobs running: none yet.
- HFG fresh-711 per-flight metrics (servertail/mets.py -> tables/m_hFg.json; report.json has the SAME metrics as the server):
  corr(log ATE): log vel RMSE 0.75, log rot RMSE 0.57, distance 0.37, v90 0.34, sim3 scale -0.32.
  dist>55 m (101 flights) mean 0.602 vs dist<40 0.278 => ATE grows with path length; server mean path 59.6 vs fresh 44.6.
  Planner pace: phase_acc = min(PHASE_ACCELERATION=0.2 default, ...) caps K-spec flights; PHASE_ACCELERATION/PHASE_JERK/MAX_YAW_RATE/TRACKING_MARGIN are overridable.
- PROBE generation (running, nohup, 24 workers, GPUs 0-7): roster servertail/gen/probe.json (72 flights = 6 planner variants K,P1..P5 x 12,
  half static/half mid; fresh-711 scenes minus holdout scenes; seeds 4410000+), raw -> /data/backups/rganapa/Sebastian/gen/raw-servertail/bench,
  logs gen/logs-bench/stprobe-worker-*.log. Launcher: gen/run_speed.sh (N ROSTER TAG RAWDIR env). Goal: pick a spec giving 55-80 m.
- HFG vs b17_exact (16 M) on fresh-711 by path length (tables/m_hFg.json, m_b17x.json): ratio HFG/B17 1.03-1.06 in all bins except 55-60 m (1.38,
  driven by a few tails: 100-02 10.1 vs 1.6, 64-01 3.5 vs 1.8). Low-fuel loss = tail flights.
- Tools: bp.sh NAME SRC "DEFS" POOL.. (build to results/st_NAME + runpool), rp.sh, runpool.py (tables/NAME__POOL.json via mets.py).
  st.c = copy of fuelpush/fp.c: with HARDEN=1 F_REUSE=1 GATE_MODE=0 it is NOT byte-identical to HFG (its F_REUSE is a different impl); a.c is.
- QUEUE q1 (nohup, logs/q1.txt): GB6 (a.c HFG + GOV_B=6e6), GB12 (GOV_B=12e6 GOV_UMAX=60) on fresh-711 (diagnostic: is the row budget the loss?).
- PROBE (57 flights, pool tmp/st_pools/probe): HFG 0.456 | b17x 0.411 | GB6 (HFG budget 6 M) 0.364. HFG tails show the SERVER SIGNATURE:
  rot RMSE 0.22-0.30 rad + sim3 scale 0.24-0.65 where B17/GB6 have rot 0.04-0.18 (85-000 3.26 vs 0.91/1.01; 130-011 1.80 vs 0.44/0.42).
  Travel per variant: K 46.7, P1 49.3, P2 44.8, P3 53.2 (spacing 1.5 conn 9), P4 49.5, P5 ~41 -> use P3 + P6 (spacing 2 conn 12).
  => hypothesis: the 3.6 M governor row budget (rows deferred/dropped at speed) causes heading/rotation error on fast flights.
- fresh-711: GB6 0.356, GB12 0.370 (HFG 0.366): budget barely matters on fresh (noise ~0.01-0.02).
- st1 generation RUNNING (40 workers, roster gen/st1.json 400 flights P3/P6, seeds 4420000+, half mid; raw-servertail/bench; logs gen/logs-bench/st1-worker-*).
- QUEUE q3 (logs/q3.txt): Z0 = st.c HFG-equivalent (probe); C34/C30 = st.c + fuelpush cheap rows (S1+F32PU F32HP GATEM NS_COST ITER_GOV GC_ROW 50k)
  + HARDEN GATE_MODE=0 at GOV_B 3.4/3.0 M (probe + fresh-711). Idea: spend the fuel the cheap kernels save on rows.
- q3 RESULTS: Z0 (st.c HFG-equiv) probe 0.4562 = HFG. C34 (cheap rows, B 3.4 M): probe 0.377, fresh 0.354 (HFG 0.366), peak 4.22 M (too high).
  C30 (B 3.0 M): probe 0.370 peak 3.96 M; fresh pending. => cheap rows + spend budget on rows is the fix direction.
- C30 fresh 0.361 @ 3.98 M (HFG 0.366 @ 4.02); probe 0.370 (HFG 0.456). CANDIDATE. cheap.defs = the fuelpush cheap-row define set.
- QUEUE q4 (logs/q4.txt): hfg_r1/r2 (a.c HFG reps, fresh+probe), C30_r1/r2, C30m (C30 + TC_MAXANCH=40 TC_RE_SCALE=1.0).
- q4 RESULTS (fresh-711 / probe57): HFG r0-2 fresh 0.366/0.367/0.361 (mean 0.364), probe 0.456/0.416/0.420 (0.431).
  C30 r0-2 fresh 0.361/0.363/0.364 (0.362), probe 0.370/0.370/0.377 (0.372), peaks 3.84-4.00 M. C30m (+m40s1) fresh 0.355 probe 0.395 (1 rep).
  Z0 (st.c HFG-equivalent) estimate/twist bytes identical to HFG on 57/57 probe flights.
- QUEUE q5: K30 (cheap + F32KT GC_ROW 45k B 3.0M) probe+fresh; Z0 on fresh (exactness check vs HFG).
- q5: K30 (F32KT, GC_ROW 45k, B 3.0) probe 0.382 fresh 0.371 -> worse than C30, drop. Z0 fresh-711 estimate/twist IDENTICAL to HFG 711/711
  (st.c + HARDEN=1 F_REUSE=1 GATE_MODE=0 == HFG outputs; wasm bytes differ only by the F_REUSE implementation).
- st1 pools (mkpool.py): tmp/st_pools/st1dev (221 so far) / st1conf (141; scene md5%3==0). QUEUE q6: hfg,C30,b17x,reps,C30m,GB6 on both (runset.sh).
- st1 (P3/P6 large-roadmap fast flights) turned out EASY: HFG dev 0.248 conf 0.306, C30 0.243/0.299, b17x 0.235/0.268. Speed/path length alone
  does not make flights hard; probe hard flights were K/P4 flights in hard ProcTHOR scenes (85,130,57,122,166) with rot 0.2-0.3 + scale<0.7.
- st2 generation RUNNING (32 workers, gen/st2.json, 240 flights: 20 hardest non-holdout fresh scenes x 12, variants K/P1/P4, half mid, seeds 4430000+).
- q6 st1 done (HFG conf 0.301 avg vs C30 0.304: neutral on easy flights). q7: hfg,C30,b17x,GB6 on partial st2 pools (st2dev/st2conf).
- st2 (partial 87 flights) is SERVER-LIKE: HFG dev 1.111 / conf 0.545; C30 1.158/0.531; b17x 0.977/0.440; GB6 0.926/0.469.
  Tails (ATE 2-8 m, vel RMSE 0.5-1.3, sim3 scale 0.1-0.6, rot 0.1-0.5) in scenes 100/166/85/64 for ALL builds incl. B17 => class =
  vision-starved (untextured ProcTHOR) fast flights: velocity diverges while unobserved -> over-extension. Low budget adds rot error.
  No drag in the simulator (l2f), so IMU gives no velocity info; only vision + net re-anchor.
- q8: hm40 / hm200 / hm200p (HFG + TC_MAXANCH 40/200, RE_SCALE 1.0, PV_PERIOD 10) on st2dev/conf + fresh: more net re-anchors in starved flights.
- q8: hm40 (HFG + TC_MAXANCH=40 TC_RE_SCALE=1.0 = 'm40s1'): st2dev 1.111 -> 0.853, st2conf 0.545 -> 0.491, fresh 0.366 -> 0.3545, peak 4.04 M.
  hm200 == hm40 exactly (re-anchors are spaced > 30 frames, so <= ~38/flight: 40 is effectively unlimited).
- sa.c = audit/a.c + TC_GAP switch (default 30 = a.c). q9: sa0 (byte check), m40, s1 (separate), g20 (MAXANCH 60 RE 1.0 GAP 20), m40s07 (RE 0.7).
- q9: sa0 (sa.c + HFG defines) wasm sha 1945902e... == HFG BYTE-IDENTICAL. st2dev/conf (87 flights, 1 rep): m40 alone 1.005/0.542; s1 alone 0.932/0.493;
  m40s1 0.853/0.491; g20 (MAXANCH 60 RE 1.0 GAP 20) 0.868/0.485 fresh 0.352; m40s07 (RE 0.7) 0.928/0.533. => m40s1 is the arm; GAP 20 no extra gain.
- q10: C30m on st2; mpv20 (m40s1 + TC_PV_THR 0.20), mfl10 (m40s1 + TC_RE_FLOOR 0.10) on st2.
- q10: mpv20 st2 0.936/0.496, mfl10 0.958/0.479 (not better than m40s1 0.853/0.491). (C30m run failed: rp.sh needs absolute wasm path.)
- st2 generation DONE (240). Rep wasms built: st_hm40{,_r1,_r2} (sa.c m40s1, sha hm40 4920835f...), st_C30m{,_r1,_r2} (st.c C30+m40s1, C30m 8c13f573...).
- QUEUE q11 (W44): hfg,hm40,hfg_r1,hm40_r1,hfg_r2,hm40_r2,C30m,C30m_r1,C30m_r2,b17x,C30,g20 on full st2dev/st2conf.
  q12 (W40): hm40_r1/r2, C30m_r1/r2 on fresh-711.
- RULE FIX: fresh numbers now reported on folds 0-2 (dev, 475) / fold 3 (conf, 107) only (cmpr.py excludes fold 4; earlier 'fresh 711' means above include it).
- hm40 (m40s1) vs HFG fresh 3 reps: dev 0.3605 -> 0.3567 (-1.1%), conf 0.3929 -> 0.3740 (-4.8%); per-rep CIs straddle 0. Peak 4.02-4.03.
- FULL st2 (240: dev 156 / conf 84), 3 reps: HFG dev 0.713/0.646/0.796 (0.7185), conf 0.545/0.501/0.494 (0.5135).
  hm40 dev 0.631/0.650/0.700 (0.660, -8.1%; >3 m 6/4/8 -> 4/3/2, >5 m 3/1/6 -> 1/1/1), conf 0.512 (-0.3%).
- C30m (st.c C30 + m40s1) 3 reps: st2dev 0.664 (-7.6%), st2conf +1.6%, fresh dev -2.4%, conf +0.1%; peak 3.78-4.00. b17x st2dev 0.631 / conf 0.472 (1 rep).
  C30 (no m40s1) st2dev 0.713 = HFG => the st2 gain is from m40s1, cheap rows buy fuel not accuracy here. g20 st2 0.639/0.512 (1 rep) ~ hm40.
- DECISION so far: accuracy fix = m40s1 (TC_MAXANCH=40 TC_RE_SCALE=1.0) on HFG (sa.c/a.c; switch-off byte-identical).
- q13 (W48): G24m / G27m (st.c cheap rows + m40s1 at GOV_B 2.4/2.7 M) x 3 reps on st2dev/st2conf/fresh: secondary fuel cut.
- final/hfg_m40s1.c (5 #defines + sa.c) builds BYTE-IDENTICAL to hm40 (sha 4920835f2d8269c0275213f66d503ed1680bff8b2e829cbbf662d26b31620c98) -> final/hfg_m40s1.wasm. PREFLIGHT running (final/preflight, logs/preflight.txt).
- PREFLIGHT hfg_m40s1.wasm (4920835f...): ABI ok (5 steps), zero imports, poison/prefix/repeat 738/738 PASS, reset PASS, rebuild byte-identical.
## FINAL SUMMARY (3 reps each, means over reps; vs HFG; fresh = folds 0-2 dev / fold 3 conf, fold 4 excluded; tables/summary1.txt)
| build | st2dev (156) | st2conf (84) | fresh dev | fresh conf | st2dev >3/>5 per rep | peak |
| HFG | 0.7185 | 0.5135 | 0.3605 | 0.3929 | 6,4,8 / 3,1,6 | 3.97-4.11 M |
| hm40 = HFG+m40s1 (RECOMMENDED, preflighted) | 0.6604 (-8.1%) | 0.5122 (-0.3%) | 0.3567 (-1.1%) | 0.3740 (-4.8%) | 4,3,2 / 1,1,1 | 3.97-4.04 M |
| C30m (cheap rows B3.0 + m40s1) | 0.6640 (-7.6%) | +1.6% | -2.4% | +0.1% | 3,3,3 / 1,2,1 | 3.77-4.00 M |
| G27m (cheap rows B2.7 + m40s1) | 0.6643 (-7.5%) | -0.8% | +0.3% | +1.7% | 3,4,4 / 2,1,1 | 2.96-3.55 M |
| G24m (B2.4 + m40s1) | -8.7% | +3.4% | +3.1% | +11.2% | | 2.60-2.72 M | REJECT
| b17x (16 M, 1 rep) | 0.631 | 0.472 | | | | 16 M |
Recommended: final/hfg_m40s1.wasm sha256 4920835f2d8269c0275213f66d503ed1680bff8b2e829cbbf662d26b31620c98 (source final/hfg_m40s1.c).
