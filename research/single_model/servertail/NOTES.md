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
