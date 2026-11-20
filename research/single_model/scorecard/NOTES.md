# scorecard: per-class risk scorecard + certification for "no server episode above 3 m ATE"

Files: certify.py (the procedure), make_feats.py + feats.json (class features), out/<build>.md (full scorecard per build B0..B11), out/SUMMARY.md, out/PERSISTENCE.md (chaos floor), out/REQUIREMENTS.md, out/summary.json.
Run for all builds: `cd eecs116_projects; /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B research/single_model/scorecard/certify.py --all` (12 s, numpy only).
New candidate: `... certify.py --name X --fresh t.json --sel t.json --holdout t.json` (tables = json list of {episode, ate} or dict episode->ate). The script only READS tables; it never scores.
Rules kept: read-only elsewhere, no git, no holdout scoring (existing holdout/table_*.json only), fold-4 selected flights / sealed_aggregate.json never opened (selected flights = the 144 visible), private server episodes never touched, guard_fusion/campaign/server_training untouched.

## Data and honesty
* Sets: holdout 240 (clean, one shot, path 59.4 m ~ server 59.6; the only honest set), fresh 711 (never tuned but used for adoption decisions; mildly optimistic), sel 144 visible (tuned on: optimistic).
* Builds on disk: B0 B1 B2(G) B3 B4 B5 B6 B7 B8 B9 on fresh+sel (matrix/store); B10/B11 on sel (learned_c r0) and only 107 fold-3 fresh flights (f3; the net was selected on fold 3 val; sel/f3 scenes overlap net training rosters). Holdout tables exist for base(B0), G(B2), G+C1(B4=B5), B7(=B6), B10(=B11) only. So B10/B11 "fresh" numbers are not comparable with the 711-flight rows; on the same 107 flights: B0 9 flights >3 m, G 4, B4 3, B7 2, B10 1.
* Class features: start type, start speed v0 and angle to the optical axis (+z of camera-frame truth velocity, first 0.5 s), flat/dark fractions, path, extent, catalog, planner setting. fresh from fresh/truth_feats.json, sel from learned_c/feats.json, holdout recomputed here from the pose csv (validated on 10 fresh flights: speed within ~0.05 m/s, angle within ~5 deg, one slow flight 24 vs 14 deg). Yaw rate: every pool flight saturates (generator cap), no variation, so it is not a class. Dark fraction is ~0 except a few scenes.
* Primary classes (exclusive, priority order): flat/dark scene (flat>0.2 or dark>0.2; n=33 pooled flights, essentially scenes 106366104_174226329 and ProcTHOR-166), static, mid slow (v0<0.3), mid fast (v0>=1.8), mid wrong-direction (0.3<=v0<1.8, angle>=90), mid forward (rest). Overlay tags: reverse>=135, flat>0.05, path/extent bins, catalog, K/K2.
* Server link is INFERENCE only: server per-episode data in the repo are ATE of B0 and G, path length, and for e7aa5aee Sim(3) scale 0.572 / rot 0.235 rad / vel 1.52 m/s (the other metrics were not saved). Start type/speed of any episode is unknown; the class posterior is the prior (mid share pm 0.5 / 0.75) updated by the episode's (B0, G) result bins using the pooled joint distribution per class (e7aa also the scale<0.75 signature). It moves little off the prior: e.g. everything is 45-85% "mid forward". Do not read it as identification.
* Statistics: Wilson 95% intervals; scene-cluster bootstrap for rates; class rates Jeffreys, and for P(12 clean) shrunk toward the pooled-all-sets rate (m=10) because holdout classes are tiny (flat/dark n=2, wrongdir 11, slow 17, fast 18). Replicate chaos: the same build moves fresh means 0.02-0.04 and search 0.2, and >3 m counts move ~15% relative (G: 36/37/42 flights >3 m over 3 replicates on the 726-flight pool); intervals here do NOT include that.

## RESULTS
1. Flight-level >3 m rate (>5 m), Wilson 95%:
| build | holdout 240 | fresh 711 | sel 144 |
|--|--|--|--|
| B0 baseline | 17.9% [13.6,23.3] (9.2%) | 9.4% (4.8%) | 18.8% (13.2%) |
| B2 = G (server 1.244) | 7.9% [5.1,12.0] (3.3%) | 5.2% (2.4%) | 6.9% (2.8%) |
| B4 G+C1 | 6.2% [3.8,10.1] (2.9%) | 4.1% (1.1%) | 9.0% (2.1%) |
| B7 G+C1+FB exact (=B6) | 6.2% [3.8,10.1] (3.3%) | 3.0% [1.9,4.5] (1.1%) | 8.3% (2.8%) |
| B10 = B11 | 3.3% [1.7,6.4] (1.2%) | 0.9% on 107 flights only | 7.6% (2.1%) |
Per-class holdout >3 m (k/n), B2 -> B7 -> B10: static 1/119, 0/119, 1/119 | mid slow 2/17, 2/17, 1/17 | mid forward 6/73, 4/73, 2/73 | mid wrong-dir 3/11, 2/11, 0/11 | mid fast 5/18, 5/18, 2/18 | flat/dark 2/2, 2/2, 2/2. So the net's gain is in forward/wrong-dir/fast starts; flat/dark is untouched by every build (6 of 6 flights with flat fraction >=0.5 fail in B2 and B7; dose-response with flat+dark fraction on the 1095 flights).
Overlay (B10 holdout, post-hoc, small n, Wilson wide): path>=65 m 4/59 (6.8%) vs 4/173 for 45-65 m; extent>=5 m 5/77 (6.5%) vs 3/122 (3-5 m) and 0/41 (<3 m); hssd-val 4/29; flat>0.05 3/16. The server has 3 paths >=72 m and one at 63 m, so long/extended flights matter more than the pool average (the path-matched proxy includes this).
2. P(all 12 episodes <= 3 m) (pm = mid share 0.5 / 0.75; ranges are 90% bootstrap / Beta intervals):
| build | class-conditional (holdout shrunk) | path-matched proxy on holdout | history-conditioned | flat-rate (1-r)^12 holdout Jeffreys |
|--|--|--|--|--|
| B0 | 0.04 / 0.03 | 0.09 / 0.03 | 0.00 | 0.09 |
| B2 (G) | 0.33 / 0.28 | 0.38 / 0.25 | 0.05 | 0.37 |
| B4 | 0.44 / 0.39 | 0.47 / 0.32 | 0.23 | 0.45 |
| B7 | 0.45 / 0.40 | 0.41 / 0.26 | 0.31 | 0.45 |
| B10 = B11 | 0.64 / 0.61 [0.45,0.75] | 0.68 / 0.61 [0.41,0.83] | 0.56 | 0.65 (Wilson-upper rate 6.4% -> 0.45) |
Consensus for B11: P(12 clean) about 0.6 (plausible 0.4-0.8). Not 0.9. Calibration check on the server: the model says expected # episodes >3 m = 2.7-3.1 for B0 (observed 3) and 1.1-1.2 for G (observed 1); G's clean probability was ~0.3 and it missed once.
Per-episode (B11, class-conditional; INFERENCE): every episode has p(>3 m) ~2-5% (they are all "probably mid forward"); the history-conditioned view is sharper: the 5 episodes with both B0 and G <=1.5 m have ~0.9% each (1/165 in holdout), the 3 base-tail episodes fixed by G (8950399d, 89f8c99e, cd6dc704) 4.5% each (1/32), the 3 with max in (1.5,3] 2% (0/24), and e7aa5aee (G 7.7 m, base 0.92) ~28% (2/8 flights with that history failed under B10; Wilson [7,59]%). So the miss probability splits roughly: e7aa5aee ~25-30% + the other 11 episodes ~10-15% together.
3. Requirements (equal rates, 12 episodes): P>=0.5 needs r<=5.6%, P>=0.8 needs <=1.84%, P>=0.9 needs <=0.87% per flight. B11 holdout 3.33% (upper 6.4%): meets 0.5 by point estimate, misses 0.8 and 0.9. In class terms (REQUIREMENTS.md, same profile as B11, pm 0.75): 0.8 needs all class rates x0.46 (static 0.4%, mid fwd 1.3%, slow 3%, fast 6%, flat/dark 36%), 0.9 needs x0.22 (static 0.2%, fwd 0.6%, slow 1.4%, fast 2.8%, flat/dark 17%). Exact-binomial evidence for a new clean set: for 0.8/0.9 certify at 95%: 162 / 342 flights with zero failures (256 / 541 with one).
4. Chaos floor (out/PERSISTENCE.md, post-hoc): failures are only ~50-65% persistent across builds. Holdout: 8 flights fail in all four of G/G+C1/B7/B10, 4 in three, 9 in two, 11 in one. P(later build fails | earlier build ok) = 1.8% (G->G+C1), 2.2% (G+C1->B7), 1.3% (B7->B10), fresh 1.3% / 0.9%; P(fails | earlier failed) 33-67%. So ANY changed build re-rolls ~1-2% of its clean flights: even a flight set that is perfectly clean for build A has ~(1-0.015)^11 = 85% chance to stay clean for a modified build. The B10 vs B7 holdout gain (15 -> 8 flights >3 m) is 10 flights fixed vs 3 new (sign test p~0.09 two-sided): real-looking but not proven.

## Which class to attack first (B11, holdout-shrunk class rates, class-conditional model, pm 0.75; gain in P(12 clean) if the class never fails / if its rate is halved)
1. mid forward (regular mid starts; 2 of B10's 8 holdout failures, 12.4 m and 6.4 m, no identifiable mechanism: startup chaos / late drift): +0.14 / +0.07. Largest because it is ~70% of episodes; needs a generic tail-containment mechanism (tailcap monitor, extent/speed-envelope prior, early-warning re-anchor), not a class fix.
2. flat/dark scenes (6/6 fail at flat>=0.5, mechanism: tracks dead, textureless; 2/2 holdout, 5/5 sel, all builds): +0.07 / +0.035 but nearly deterministic when it occurs and prior share is only ~1.5% per episode; a gated textureless fallback (live tracks <5: IMU+speed-envelope coasting) is the one class with a clear mechanism. The b6fix classifier marks them 'textureless' (tracks dead) or 'starved coasting'.
3. fast starts v0>=1.8 (B10 2/18 holdout, 3/10 sel; net sigma over-confident for fast starts, direct error 0.40 m/s, cov1 0.56): +0.057 / +0.028.
4. slow mid starts v0<0.3 (B10 1/17, sel 1/5): +0.037 / +0.018.
5. static (+0.011) and wrong-direction (+0.006; fixed by the net 3/11 -> 0/11, n tiny): leave alone.
Realistic target: halve the mid-forward and fast rates and cut flat/dark: P 0.61 -> ~0.75; zeroing all classes gives ~0.95, i.e. the model says class-level work alone reaches 0.8 only if mid-forward tails drop ~3x. Additional lever independent of class: do not change the build further than needed (chaos floor 1-2% per flight per change).
Mechanism tags for failures: only B6-era flights have b6fix diagnostics (diag); other failures carry observable rule tags (post-hoc suspicion only), see worst-flight tables.
