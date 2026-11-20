# Preflight of fgt (gate G + tails T merged)
Source final/fgt.c (= fg.c + T hand-merged), wasm final/fgt_merged.wasm = results/single_model/fgt_merged/solution.wasm,
SHA-256 73c81cedcca4684bec95112a50765b1d50fd9c86cbaa0a3341453a65412d6eb5 (rebuild byte-identical).
Switches: GATE_MODE=0 -> T alone; VI_MODE=0 TAILS_DET=0 TAILS_KLT=0 -> G alone; FGT_GUARD=0 -> no G/T coordination.
Interaction (see comment block in fgt.c): clones at frames 0,4,8,12,16 (FAST_FRAMES=0). G decides in vision_zupt at the 2nd valid pair (frame 8,
t~0.45 s; frame 12 if a pair lacked 10 matches). T runs at the 4th clone = frame 12 (t~0.65 s; NOT 16), before vision_zupt, retried at later
clones while last_t-t_start<1 s. FGT_GUARD 1: T skips if G already released, or if G has >=1 valid pair all <2 px but no decision yet (T retries,
so never fires if G releases next clone). G held/latched or no pair: T as without G. G release after T fired: forced ZUPT still applies.
Also fixed: T's g_ema "have" flag and tex_scale now reset at init (fresh-instance behaviour unchanged).
## Scores (single run; search n=119 / val n=25)
f0 1.033/0.524 | G 1.028/0.543 | T 0.831/0.539 | merged 0.845/0.559 (static 0.586/0.654, mid 1.075/0.471) | merged FGT_GUARD=0 0.847/0.559
3 chaos replicates (search): f0 1.033/1.227/1.297 (1.186) | T 0.831/0.918/0.980 (0.910) | merged 0.845/0.927/0.990 (0.921); merged vs f0 -0.265 [-0.543,-0.042], static -0.100 [-0.310,+0.013]
 val rep-mean merged 0.547 vs f0 0.527 (+0.020 [-0.019,+0.064]). >5 m flights in every merged replicate are exactly T's set (100-02, 143-01, 151-00 [10.9/9.4 also in f0 reps], 158-07);
 no new >10 m flight. Merged is within noise of T (+0.011 rep-mean).
## Checks
| Check | Result | Evidence |
|---|---|---|
| ABI `viobench check` (private TMPDIR) | PASS | check: ok (5 steps), exit 0 (abi_check.txt) |
| Zero wasm imports, same exports | PASS | wasm_imports.txt |
| Bit-identity T off == G (preflight_gate_a) | PASS | 171/171 estimate.tum and ate_full identical (bits.txt) |
| Bit-identity G off == T (tails_adopted) | PASS | 171/171 (bits.txt) |
| Determinism (two builds, two evaluator runs) | PASS | 171/171 estimate.tum identical, wasm byte-identical (determinism.txt) |
| Causality: poison+prefix+repeat | PASS | 19 fixtures x 18 prefixes (1,2,8-12,15-17,19-21,40,41,120,600,1199) = 342/342 cases; fixtures from corrected f0win generator, folds 0-3 only, include G-release (frame 8/12), T-fire (frame 12), held, undecided, static, worst tails |
| Reset/re-init | PASS | 5 flights x (re-init replay, partial replay + re-init) bit-equal (reset_check.txt) |
| Filled frames 0, all completed | PASS | 171/171 (stats.txt) |
| Fuel | PASS | peak 22.98 M/frame (0.115% of 2e10), worst p95 16.37 M (identical to T) |
| Merged vs T per flight | note | 2 flights >0.3 m: 174226329-02 (T 1.76, merged 3.91) and 176000019-00 (0.57 -> 1.07) |
## Per-flight differences vs f0 (>0.3 m, folds 0-3; 20 flights, plus 4 fold-4 not analysed); see perflight_cmp.txt and audit.txt
Improved (T): 174226329 static-00 8.04->2.45, mid-00 8.50->3.28, -01 4.90->3.17 (flat-scene front end); 123-00 4.14->0.73, 178-01 3.39->0.70, 102344457-01 3.82->0.88, 176710602-01 5.37->2.03, -00 1.28->0.42 (T flow reset fired at frame 12, speeds 0.7-2.5 m/s); 151-09 static 1.47->0.60.
Regressed (T chaos/low-contrast, same as T alone): 57-02 1.17->2.89, 158-07 2.75->4.26, 100-02 4.37->5.36, 191-02, 154-09 (T: flow said direction agrees; chaotic), 106-01 static 0.90->1.45, 160-02 static 0.75->1.06, 102344280-01.
G-specific: 176000019-00 0.57->1.07 (G released at frame 8, true start speed 0.23 m/s rising to 0.42 at 0.65 s: slow-start release regression, same as G alone); 174226329-02 5.85->3.91: G released at frame 12 (true start speed 0.11 m/s) only because T's flat-scene fix gives G enough matches; T alone has 1.76 there, i.e. the release itself costs ~2 m on this flight though the release was correct (vehicle ~at rest).
## When each feature fired (audit.txt, audit_all171.json; all 171, static flights: neither feature active, 85/85)
86 moving-start flights: G released 5 (frame 8 on 4, 12 on 1; true speeds at start 0.04-0.5 m/s), G held (first latch frame 4: 69, 8: 5, 12: 4, later 3) 81.
T decision always at frame 12 (63 flights): flow velocity applied on 10 (direction >75 deg from axis), kept heading prior on 53; 18 had no decision (<8 matched features or flat scene).
G released and T fired on the same flight: none. T blocked by G release: 5 flights (3 of them 176000019-00, 121-00, 107-00, 5-02 all true slow starts), deferred 2; the guard changed the result on only 2 flights (0.847 vs 0.845 mean).
## Server note
The gated build (G alone) lost 0.918->7.70 m on one server episode that looks like the wrong-direction lock-out. T fires only on that failure class (10 of 86 moving flights locally, 4 of 5 clearly wrong-direction ones recovered), and the merged build equals T where G holds, so merged should address it; this is an inference, no private episode was opened.
