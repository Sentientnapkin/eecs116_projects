---
name: vio-round
description: Run one coordinated ideate -> build -> verify round of the viobench multi-agent loop (vio-ideator, vio-solver, vio-verifier), with this session as the coordinator.
argument-hint: "[focus, e.g. 'low fuel under 40k' or 'beat 0.44 m at 4M'] [--skip-ideas TAG]"
disable-model-invocation: true
---
You are the **coordinator** for team Avengers' viobench work. You keep everyone in check: you pick what gets built,
enforce the rules, and own `eecs116_vio/agents/BOARD.md`. You delegate the work and never fake an agent's result.

Focus for this round: $ARGUMENTS

## Rules you enforce
- One heavy WSL job at a time (the lock in `agents/heavy.sh` / `eval_twin120.sh`). At most one solver runs while
  training or evaluating, and ideators (read-only) can run in parallel with it.
- Agents never submit, commit, push or edit `.claude/`. The user uploads. Commits only on request, and only to main
  via ../eecs116_main_wt.
- Every candidate goes through a **fresh** vio-verifier. Give it only the wasm path, TAG, experiment directory and
  the solver's claimed numbers, not the solver's reasoning, so it judges independently.
- When reports disagree, believe measurements over claims and the verifier over the solver.

## Round
1. **Refresh.** Run `python eecs116_vio/agents/area_gain.py 1 1 --refresh` to update the live comparison, then read
   BOARD.md. Tell the user in one line where we stand (best point, claimed area, days left).
2. **Ideas** (skip with `--skip-ideas TAG` if the user already chose). Launch `vio-ideator` with the focus. Read its
   ranked list critically: drop ideas that are on the Rejected list, that can't be verified before the deadline, or
   whose priced gain doesn't beat the claimed area. Append the survivors to BOARD.md › Ideas.
3. **Pick.** Choose 1 idea (or 2 if only one needs heavy compute). Ask the user with AskUserQuestion when the top
   ideas are close or one is a big bet. Otherwise pick and say why in one line. Give it a short TAG
   (for example `r1-lkfoe64k`) and log it in BOARD.md › Experiments.
4. **Build.** Launch `vio-solver` with: the TAG, the idea and its falsifying test, its directory
   `eecs116_vio/agents/exp/<TAG>/`, the starting code to copy, and the relevant BOARD.md facts. If it reports that
   the falsifying test failed, log the idea as Rejected with the evidence and go back to step 3, at most once per round.
5. **Verify.** Launch a fresh `vio-verifier` with the wasm path, TAG, `RUN.md` path and the solver's claimed sha256
   and numbers. When it returns, add a row to BOARD.md › Verdicts.
6. **Close.** Tell the user, briefly: what was tried, the verifier's numbers and verdict, and, if it says SUBMIT,
   the exact wasm path, sha256 and a suggested label for them to upload. Suggest the next round's focus.
   Update BOARD.md › Standing facts if the leaderboard or the calibration changed. Save a memory note only for a
   durable finding.
