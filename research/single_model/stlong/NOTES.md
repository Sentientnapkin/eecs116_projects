# STLONG periodic velocity training

Status: initial teachers and pilots finished; expanded-data generation active (2956 eligible flights cached). Final training, comparisons, and preflight remain. No candidate has passed the goal yet.

## Constraints
All task outputs here, generated data under Sebastian/gen or Sebastian/tmp. No commits, uploads, holdout scoring, sealed/fold-4 payload reads, private episodes, or Sim(3) selection. Train scenes exclude holdout and all st2/st3 scenes. Max 48 CPU evaluation workers and 4 GPUs. Training and generation use nohup; stop all task jobs before ending.

## Milestones
- Read requested instructions, learnvel and learned_c notes, STUDENT_TEACHER index, proxy notes/recipe, and recent LOOP_LOG. No AGENTS.md in applicable ancestor paths.
- Resume process audit: no task training/generation active; GPUs 1–7 idle, GPU 0 has another user's process. Root full; /data has ~11 TB free. TMPDIR must be Sebastian/tmp.
- Existing v700b result: 2308 training flights (more than the instruction's shorthand old+700). Existing lv cache contains 1200 files; roster a and b each 600 and lv_rows contains 1200. Need verify per-file completeness/exclusions before use.
- Partial stlong generation driver is unsuitable unchanged: dynamically consumes GPUs, writes sl_cache_train, and lacks independent roster audit. Will fix before launch.
- Baseline, teachers, 3+ student seeds, calibration, in-filter screens/finalists, and final preflight pending.
- Data audit saved in tables/data_audit.json: 2740 eligible cached flights / 113 scenes (fast 374, speed 47, learned_c new 1119, lv a+b 1200); 337 forbidden-scene older training rows excluded. Both roster a/b complete. Baseline recipe now uses this safe current cache, so it is not an exact data replay of historical v700b (2308 flights).
- Roster c validated: 2400 flights, 113 scenes, seeds 5300000–5302399, no forbidden scene/fold or known roster-seed overlap. CPU GENERIC one-flight smoke running before 400-flight batch (enough to exceed 3000 eligible flights).
- st3 eval preprocessing DONE: all 234 flights in tmp/sl_cache_st3. No holdout evaluated.
- Background jobs tracked in logs/jobs.json. Baseline GPU1, teacher2 GPU2 (2 frames, 128x96, width2, deep), teacher4 GPU3 (4 frames, 128x96, width2, deep); teachers 120 epochs x400 steps, mirror + betaNLL + speed/texture sampling. Student architecture remains 1.794M MAC lcJ.
- GSLV rebuild with new switch off matches reference sha256 5e4d2a0d40333b3f5152d60de84a688abc5d0eec8c1c73fa402dc9907839d196. Student switch nests new header under LV_NET, all baseline defines unchanged.
- New weights present but LV_STLONG=0 also rebuild byte-identically (logs/switchtest.log). Historical v700b direct reproduced: st2dev 0.240375, st3 0.235825 m/s; high-speed >2 m/s 0.54661/0.57362, sigma z-rms 1.1535/1.1510. Full speed-bin results in tables/v700b_direct.json. Speed scale in new reports uses pooled least-squares along-truth ratio, rather than averaging per-anchor ratios.
- Baseline retraining DONE (60x400, safe current 2740-flight mix): st2dev 0.236257 m/s vs historical v700b 0.240375. >2 m/s 0.548525, per-anchor speed scale 0.81095, sigma rms 1.1271. Direct full-bin st2dev/st3 report and r0 pooled filter screen running.
- CPU generation launched (one smoke + remaining399 roster-c flights, 36 workers, batches72, same seeds/60s). Generic renderer is very slow (~0.3–0.6 output frames/s on first scene after compilation). Asked user asynchronously whether CPU simulation + GPU rendering, as supplied driver used, is acceptable; no change pending answer. Generation may require hours if pure CPU retained.
- USER AUTHORIZATION: use GPU rendering with CPU simulation within four GPUs total. Stopped pure-CPU generator groups 2735040 and 3041644; relaunched full c400 roster with CPU worlds + OPTIX renderer exclusively on GPU4. Teachers occupy GPUs2/3; GPU1 available for student. No partial generic flight was accepted into training. Scope exception is explicitly user-approved.
- Baseline r0 in-filter screen DONE: pooled390 GSLV 0.4254 -> retrain 0.4474 (+5.2%, scene CI [-0.0114,+0.0578] m); peak6.82/6.94M, p99both3.58M, tails4/1/0 ->5/0/0. Confirms direct gain alone is insufficient; baseline retrain rejected for recommendation.
- ETA requested by user: current initial teachers 5–8min remaining; expanded-data teacher+3student stages estimated15–25min; full task initially estimated60–90min, refine from GPU generation throughput.
- Pilot student launched on GPU1 using frozen teacher4 snapshot while teachers finish and generation compiles. This is a pipeline/in-filter pilot on2740 flights; final students will use ≥3000 eligible flights. Distillation matches final-frame velocity/sigma across the teacher's 4frame and student's 2frame windows.
- Integration detail found during source review: exporter LC_SIGSCALE macro is not consumed by GSLV. Actual student sigma calibration therefore must be folded into output log-variance biases (2*log(scale)); build.py now does so. Speed calibration supports a zero-cost constant fold or a small optional predicted-speed ramp inside lc_apply; disabled switch still preserves original source path.
- Initial teacher2 finished120epochs x400steps (514s training + data load). Teacher4 still improving near epoch100; reached st2dev~0.172/st3~0.169 m/s. Pilot student running4–5s/epoch after~2min loading; no in-filter claim from teacher accuracy.
- First OPTIX flight completed valid after288.6s including shared renderer/environment compilation; remaining workers are compiling/reusing8 planner variants. Need steady-state generation sample before updating full ETA.
- Pilot recipe observation around epoch32: direct~0.258m/s, slower/worse than baseline. Its KD uses teacher inverse variance, which can over-weight conditional teacher certainty unavailable to a2frame student. For subsequent runs, use beta=.5 variance weighting on soft means and moment-match sigma to teacher variance + detached student/teacher mean disagreement. Keeps explicit soft velocity/sigma + truth objectives and avoids forcing teacher's4frame conditional uncertainty onto student.

## Initial teacher milestone (2740 training flights, 113 scenes)

| model | st2dev mean | st3 mean | st2dev >2m/s | st3 >2m/s | pooled sigma scale |
|---|---:|---:|---:|---:|---:|
| teacher2 | 0.179842 | 0.175567 | 0.380432 | 0.394942 | 1.2958 |
| teacher4 | 0.169574 | 0.167274 | 0.324276 | 0.335429 | 1.2364 |

Teacher4 selected for high-speed accuracy. Selection used only st2dev/st3. Teacher4 120epochs x400steps finished642s training (+loading). Additional pilot_mm launched on GPU2 using moment-matched soft sigma and final teacher; final ≥3000-flight students still pending generation.
- Single-GPU generation reached~64GB/99% utilization and slow throughput. Preserved completed raw archives and restarted immediately on freed GPUs1/3/4 (GPU2 reserved for pilot_mm), rather than waiting for entire first72flight batch; canceled the pending batch-switch watcher to prevent duplicate launches. No accepted cache data lost. Subsequent batches use all four GPUs once pilot exits, and generation stops once >=260new flights cached.
- Original pilot r0 screen: pooled390 ATE0.4438 vs GSLV0.4254 (+4.3%, CI[-0.0130,+0.0432]), peak6.66M; rejected. Speed rampk=.02 improves fast direct but worsens overall direct slightly; no in-filter calibration claim. For final students use clean audited baseline initialization plus lowerLR0.0008, three independent sampling/augmentation seeds,100epochs, expanded teacher soft targets; avoids repeating scratch-pilot convergence cost. Restarted waiting next-stage supervisor to load this explicit recipe update.
- pilot_mm r0 screen also rejected: pooledATE0.4437 vs0.4254 (+4.3%, CI[-0.0138,+0.0458]), peak7.06M vs6.82M. Sigma direct calibration improved (z-rms~1.08 vs original pilot~1.25); mean direct accuracy stayed~0.24. Confirms capacity/information gap despite strong teacher.
- Added optional width1.5 student seeds0/1/2 (90epochs, same2frame64x48input), trained in parallel on GPUs1/2/4 during expanded teacher continuation GPU3. Then main lcJ seeds0/1/2 run100epochs. Total task GPU use<=4; no generation overlap after>=3000flight threshold.
- Optional C changes in build.py: quantized weights[4][9*48*72+64], SIMD accumulator vector array18 (CO<=72), input buffer proven sufficient; CI<=48 means worst signed32dot sum9*48*2047^2=1,810,170,288<INT32_MAX. Governor step costs: unchanged prep, conv0x1.5, conv1–3x2.25, headx1.5. All guarded by LV_STLONG, original branch retained. Width1.5 candidate must independently pass switch-off identity, measured peak<=GSLV, and full preflight; no claim yet.
- First new-data batch DONE:72/72 generated+cached, zero preprocessing errors; eligible mix now2812 flights. Next generation batch using GPUs1/2/3/4 because both pilots exited. Target stop>=260new (>=3000total).
- Width1.5 C off-switch verification PASS with a random shape-only checkpoint: same GSLV sha5e4d2a0d...; width1.5 has172876 trainable parameters /3,559,008MACs (lcJ105292/1,794,144). Shape-only checkpoint is not trained or evaluated and is not a candidate. On-switch compilation also being checked before training.
- Width1.5 C prototype compiles with all changes enabled; all changes disabled reproduces exact GSLV SHA (logs/wide_off.log). Prototype uses random weights solely for compile/off-switch checks, never evaluated or trained; not a candidate.
- Automated wider-model r0 screens will overlap main lcJ training once wider models finish. Evaluation remains sequential48workers; direct inference uses freed GPU4. Includes each seed, disabled-switch identity, best raw model's sigma-only and predicted-speed calibration screens. Selection remains tuning pools only.
- 2026-11-22 22:24:59 UTC: data cache milestone 144 new eligible flights, 2884 total; generation audit/exclusions unchanged.
- 2026-11-22 22:26:14 UTC: data cache milestone 216 new eligible flights, 2956 total; generation audit/exclusions unchanged.
- 2026-11-22 22:32:59 UTC: data cache milestone 288 new eligible flights, 3028 total; generation audit/exclusions unchanged.
- 2026-11-22 22:33:01 UTC: Expanded-data training threshold reached: 3028 flights. Starting selected teacher continuation; estimate ~8min including loading, then three parallel100epoch students ~10min.
- 2026-11-22 22:33:01 UTC: Launched teacher_final, GPU3, pid3517106.
- 2026-11-22 22:33:01 UTC: Launched wide0, GPU1, pid3517107.
- 2026-11-22 22:33:01 UTC: Launched wide1, GPU2, pid3517108.
- 2026-11-22 22:33:01 UTC: Launched wide2, GPU4, pid3517109.
- Startup coverage correction: long-context KD formerly sampled only windows ending at frame15 or later. Corrected final trainer to sample ALL valid2frame student windows, apply truth loss to all, and KD only when two additional past anchors exist; same final frame, no future data. Restarted just-started expanded stage (about10teacher/12wide epochs interrupted) to apply consistently. Cached3028flights untouched. Prior pilot results reflect old sampler and are rejected, not final evidence.
- 2026-11-22 22:35:40 UTC: Expanded-data training threshold reached: 3028 flights. Starting selected teacher continuation; estimate ~8min including loading, then three parallel100epoch students ~10min.
- 2026-11-22 22:35:40 UTC: Launched teacher_final, GPU3, pid3521036.
- 2026-11-22 22:35:40 UTC: Launched wide0, GPU1, pid3521037.
- 2026-11-22 22:35:40 UTC: Launched wide1, GPU2, pid3521038.
- 2026-11-22 22:35:40 UTC: Launched wide2, GPU4, pid3521039.
- Sampler invariant check PASS on2audited real flights: all4early student windows retained; KD windows stay within flight and end at exactly the student final timestamp.
