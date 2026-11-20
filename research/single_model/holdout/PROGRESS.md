# Holdout generation progress log
- 10:28 start. All GPUs idle at start (nvidia-smi); load ~70. Plan: stage1 = one static pilot/candidate per eligible scene (132 ProcTHOR + 94 HSSD-train not in gen/raw-fast, 15 HSSD-val dev x2 reused scenes); stage2 = extra static + mid candidates in scenes with high stage-1 extent (truth statistics only); select 120+120 by truth-stat calibration (select_final.py).
- Eligible scene facts: every scene in the three catalogs appears in SOME existing roster/training manifest; 0 are entirely new. Excluded: reserved test scenes (ProcTHOR 162-165/172-175, 28 HSSD-Val43 test houses), crashers (ProcTHOR 121,124; HSSD 103997940_171031257).
- 10:36 hyperlux cache: copied /dev/shm/sebastian-gen/shared-hyperlux to /dev/shm/sebastian-holdout/hyperlux-hl with same-length path rewrite (copy elsewhere re-runs cmake FetchContent which fails offline). venv-sim/bin must be on PATH (cmake>=3.24).
- 10:38 stage1 launched: gen_driver.py (24 workers, batches of 120, GPUs 7 + idle 1-6).
- 11:13 stage1 done 256/256, 0 failures (~7 flights/min with 24 workers).
- 11:15 stage2 launched (48 workers, batch 192): extra static + mid candidates in scenes with stage-1 extent >=2.8 m (plan cfg/stage2_plan.json).
- 17:50 stage2 done; selecting.
- verify_zips: 240/240 load + gates pass. Scoring base, G, G+C1 (score_build.sh, one shot each).
- 18:10 scored base/gate/gatec1; RESULTS.md written.
