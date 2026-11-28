# Multi-agent loop

Type `/vio-round <focus>` in Claude Code (opened in `eecs116_projects/`). The main session becomes the
**coordinator** and runs these agents:

| Role | Defined in | Can | Cannot |
|---|---|---|---|
| Coordinator ("keeps everyone in check") | `.claude/skills/vio-round/SKILL.md` | pick ideas, launch agents, own BOARD.md | submit |
| Ideator | `.claude/agents/vio-ideator.md` | read code, notes, other teams' work, web | write files |
| Solver | `.claude/agents/vio-solver.md` | build in `agents/exp/<TAG>/` only | edit originals, tune on twin120 |
| Verifier | `.claude/agents/vio-verifier.md` | re-measure, run the checks | edit files, see the solver's reasoning |

Examples: `/vio-round low fuel under 40k`, `/vio-round beat 0.44 m at 4M fuel`,
`/vio-round --skip-ideas port alternating select/track frames to C`.
You can also call one agent directly: "use vio-verifier on agents/exp/r1/r1.wasm".

## Shared tools
- `area_gain.py FUEL ATE [--refresh]`: the server's exact area formula against the live baselines.
- `eval_twin120.sh WASM TAG` (WSL): the twin120 proxy score, fuel and gain -> `results/TAG.json`.
- `leak_check.py SET --exclude ids_excl_nb_twin.txt`: no twin flights in training.
- `heavy.sh CMD`: run a heavy WSL job under the shared lock (one at a time).
- `BOARD.md`: shared state such as verdicts, experiments, ideas and rejected ideas.
