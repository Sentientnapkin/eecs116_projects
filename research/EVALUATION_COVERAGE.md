# Development coverage and stress-set design

The [roster audit](results/eval/evaluation-coverage.json) counts parent flight hashes separately from replay records. It uses the same 30-second cap and backward/lateral rules as the odometry evaluator. An initial speed above 0.1 m/s is an additional diagnostic.

| Current roster | Replays | Unique flights | Scenes | Backward/lateral replays | Backward/lateral flights |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original dev, ProcTHOR | 14 | 7 | 6 | 2 | 1 |
| Campaign dev, ProcTHOR | 60 | 30 | 6 | 8 | 4 |
| Campaign dev, HSSD | 60 | 30 | 15 | 2 | 1 |
| Proxy validation, ProcTHOR | 69 | 68 | 12 | 31 | 31 |

Campaign dev has 60 nominal and 60 five-second crops. Each pair shares 24.95–25.00 scored seconds. All nominal starts are at or below 0.1 m/s, but only 39 five-second crops exceed 0.1 m/s, including 15 of 30 ProcTHOR and 24 of 30 HSSD. Two of the five backward/lateral moving crops exceed that threshold. Keep the historical crop groups for continuity and report measured start-speed bins separately.

## Fresh native stress set

Generate **192 independent scored flights**, 12 per catalog × condition × start cell, on at least 16 fresh scenes per catalog and with 12 different scenes per cell. Balance scene contributions across cells. Run a feasibility pilot of two independent flights per cell before locking the final roster. Use disjoint simulator seeds, parent hashes, and scene identities from all earlier data. Retain campaign dev and the 84 reserved test flights in their current roles.

| Primary condition | Simulation and acceptance |
| --- | --- |
| Ordinary forward motion | Use the current benchmark autopilot and match the 60-second horizon, camera adaptation, sensor packet delivery and noise. |
| Backward/lateral | Control yaw relative to the route and require measured backward fraction above 5% or lateral fraction above 10% in the scored prefix. Balance the assigned backward and lateral maneuvers. |
| Independent yaw | Vary heading independently of course. Record realized body-frame motion separately so heading policy and backward/lateral occupancy can be analyzed independently. |
| Low-texture corridors | Choose a corridor route from scene geometry before evaluating any model. Require fewer than 40 detectable FAST corners at 320×240 in at least 20% of moving one-hertz samples. Report darkness and texture separately. |

Use one scored reset per parent. Static starts require at most 0.05 m/s across the initial 0.25 s. Moving starts require at least 0.20 m/s across that interval after a randomly seeded warm-up, with a fresh estimator and no warm-up images or packets delivered to it. Lock accepted flight identifiers with simulator metadata, scene asset hashes, replay lengths and enrollment counts before running models. Replace infeasible flights by a preassigned seed sequence using only route, sensor and truth checks.

Report equal-flight mean unaligned ATE at 30 s and 60 s, using continuous state for both durations. Report catalog, condition and actual start group alongside the overall result, plus initialization coverage and filled frames. Bootstrap scenes with all their flights together and keep training seed variability separate. Use the existing campaign-dev reporting unchanged for continuity. Compare OpenVINS, learned attitude and any qualifying hybrid on the identical frozen enrollment.

The installed simulator exposes ProcTHOR Train200 and HSSD Train125/Val43. All their scene IDs are already in the historical ledger or assigned campaign roster. Fresh-scene enrollment therefore needs additional simulator-compatible scene assets. ProcTHOR-10K beyond the installed 200 and additional HSSD assets are candidate sources. Check source scene IDs and geometry hashes against all existing rosters, confirm asset access and benchmark split provenance, then validate rendering and route generation before selecting IDs. The scene sources are documented by [ProcTHOR-10K](https://github.com/allenai/procthor-10k) and [HSSD](https://huggingface.co/datasets/hssd/hssd-scenes).

## Submitted Wasm discrepancy

The reported submission hash matches the local raw seed-217 artifact exactly. The previous raw parity sample used two nominal 30-second parents and their moving crops. The server summary includes twelve 1,200-frame episodes with no filled frames. A paired local 600-prefix/1,200-full replay with that exact artifact is in progress, using native campaign dev only. The server episodes have not been identified locally.
