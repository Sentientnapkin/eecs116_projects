# Learned Inertial Odometry and Learned Motion Priors for Drones as a Cheap Substitute for the Visual Front End

Scope: whether a small learned IMU-only (or IMU + very sparse vision) model can carry a drone VIO estimator at about 1 M wasm ops per frame. The learned part should cost no more than about 0.3 M ops per frame. Target is low mean unaligned ATE on 60 s, about 60 m indoor simulated quadrotor flights: 20 Hz frames, gyro noise 0.07 rad/s, accel noise 0.28 m/s^2, Bezier-roadmap planner, max yaw rate about 0.65 rad/s, **no rotor drag in the simulator**. The current system is MSCKF plus a learned startup-velocity CNN. The dominant remaining error is translation offset that builds up while vision is starved.

Research note: arXiv PDFs could not be text-extracted in this environment. Numbers below come from arXiv HTML or ar5iv renderings, project pages, and search abstracts. When a number appears only in a paper's figures, these notes say so rather than estimate it.

---

## Q1. What do TLIO, RoNIN, RNIN-VIO, AirIO, IMO (Cioffi), DIDO, Deep IMU Bias Inference and similar methods report on accuracy, network size, inference rate and fusion?

### Takeaway
Every published learned-IO system feeds an EKF or factor graph with a network-regressed displacement or velocity, usually with a learned diagonal covariance, at 1–20 Hz. On real drones the best IMU-only systems reach about 0.4–1.3 m ATE on Blackbird-style flights. The networks are 30–70 MFLOPs and 0.3–5 M parameters, which is roughly 100–200x over our 0.3 M-op budget. Even so, the fusion recipe itself is cheap and fits easily into an MSCKF.

### Cited Findings

**TLIO (Liu et al., RA-L 2020; pedestrian headset)**
- Network: a "1D version of ResNet18" with two FC heads, one for displacement and one for uncertainty. Input is N×6 IMU samples with N = 200 at 200 Hz, a 1 s window, rotated into a gravity-aligned frame built from the window-start orientation. Training applies random yaw augmentation, bias perturbation (±0.2 m/s^2 accel, ±0.05 rad/s gyro) and gravity perturbation up to 5°. — [TLIO ar5iv](https://ar5iv.labs.arxiv.org/html/2007.01867)
- Output: 3D displacement plus 3 log-std values, giving Σ = diag(e^{2u}). Loss is MSE for 10 epochs, then Gaussian NLL for about 10 more. — [TLIO ar5iv](https://ar5iv.labs.arxiv.org/html/2007.01867)
- Fusion: a stochastic-cloning EKF propagated by raw IMU. The network displacement between two clones is applied as an update at 20 Hz, with at most 21 past states for a 1 s window. The displacement is expressed in a gravity-aligned frame at clone i, so it injects no yaw information. A χ² gate uses 11.345 (99%, 3 DOF). The network covariance is **multiplied by 10** to account for temporal correlation between overlapping windows. — [TLIO ar5iv](https://ar5iv.labs.arxiv.org/html/2007.01867)
- Learned covariance matters. Fixed-covariance variants lost track on at least one dataset, and over 99% of errors fall inside 3σ. Versus the best RoNIN-style velocity-integration baseline, TLIO cuts yaw drift by 27% and position drift by 31–33%; the paper gives both figures in different sections. Absolute ATE values appear only in figures. — [TLIO ar5iv](https://ar5iv.labs.arxiv.org/html/2007.01867)
- Compute, as measured by TinyIO: TLIO is 39.4 MFLOPs and 5.42 M parameters per inference. — [TinyIO arXiv 2507.15293](https://arxiv.org/html/2507.15293v4)

**RoNIN / RNIN family (pedestrian)**
- Compute per TinyIO Table I: RoNIN-ResNet is 38.3 MFLOPs and 4.64 M parameters; RoNIN-LSTM is 57.5 MFLOPs and 13.6 M parameters; RNIN is 72.0 MFLOPs and 5.26 M parameters. — [TinyIO](https://arxiv.org/html/2507.15293v4)
- RNIN-VIO (Chen et al., ISMAR 2021) is a tightly coupled EKF that fuses visual, IMU and neural-inertial measurements. Visual constraints "can be removed at any time" and estimation continues on IMU plus network. Accuracy in challenging scenes (weak texture, motion blur, dynamic scenes) is "significantly better than VIO". The public repo holds only the inertial network. — [RNIN-VIO project page](https://zju3dv.github.io/rnin-vio.github.io), [GitHub](https://github.com/zju3dv/rnin-vio)

**AirIO (Qiu et al., 2025; UAVs, IMU only, no thrust)**
- Architecture: a body-frame IMU encoder plus a CNN attitude encoder (attitude as an so(3) vector), concatenated and passed to **bidirectional GRU** layers. MLP decoders output **body-frame velocity** and its uncertainty, not displacement. The regular model has latent size 256 and is 2.524 MB; "Light" variants use 128 and 64. The window is 1000 IMU frames at 200 Hz, about 5 s. Training uses ground-truth attitude and testing uses EKF attitude. — [AirIO HTML](https://arxiv.org/html/2501.15659v2)
- EKF: a 15-dim error state (R, v, p, b_a, b_g) propagated by AirIMU-corrected IMU with learned IMU noise. The measurement is h(X) = Rᵀv (body velocity) with the network's covariance. Only the current-frame velocity is constrained. — [AirIO HTML](https://arxiv.org/html/2501.15659v2)
- ATE (m), Blackbird SEEN / UNSEEN / EuRoC averages: RoNIN 2.193 / 13.487 / 6.75; TLIO 1.189 / 3.478 / 6.969; IMO 0.929 / 9.015 / –; AirIO Net 0.486 / 1.300 / 3.846; AirIO EKF 0.403 / 1.309 / 3.177. The EKF adds about 17.4% over the raw network on EuRoC. — [AirIO HTML](https://arxiv.org/html/2501.15659v2)
- Runtime (network plus EKF, 1000-frame buffer): 74.23 ms on Jetson Orin AGX and 28.92 ms on an RTX 2060 desktop. — [AirIO HTML](https://arxiv.org/html/2501.15659v2)

**IMO: "Learned Inertial Odometry for Autonomous Drone Racing" (Cioffi et al., RA-L 2023)**
- Network: a TCN regressing 3-DoF displacement from a 0.5 s buffer of **mass-normalized collective thrust plus world-frame, bias-removed gyro** at 100 Hz. Accelerometer data is not a network input. No layer or parameter counts are given. — [IMO ar5iv](https://ar5iv.labs.arxiv.org/html/2210.15287)
- Fusion: an IMU-propagated EKF updated with network displacement at 20 Hz, keeping up to 10 past states. Measurement noise is a **fixed** σ = 0.01 m, not learned. The full system runs at about 180 Hz on a Jetson TX2. — [IMO ar5iv](https://ar5iv.labs.arxiv.org/html/2210.15287)
- ATE_T (m) on Blackbird, IMO vs TLIO vs OpenVINS: Clover 0.41 / 0.75 / 0.50; Egg 1.15 / 1.31 / 1.07; Half Moon 0.76 / 1.20 / 0.37; Star 1.22 / 2.04 / 2.78; Winter 0.22 / 1.13 / 0.12. — [IMO ar5iv](https://ar5iv.labs.arxiv.org/html/2210.15287)
- Racing track (about 6 s laps, up to about 70 km/h): IMO 0.56 m, TLIO 1.21 m, Gate-IO (camera gate detection) 0.48 m, SVO 47.2 m, OpenVINS 98.2 m. — [IMO ar5iv](https://ar5iv.labs.arxiv.org/html/2210.15287)
- Ablations: a model-only EKF using thrust-derived displacements reaches 10.10 m ATE, so learning the thrust mismatch is essential. Concatenating network outputs without the filter gives 3.20 m versus 0.56 m with it. — [IMO ar5iv](https://ar5iv.labs.arxiv.org/html/2210.15287)
- Training data is about 10 min of Blackbird flights and about 5 min of racing-track flights, all real. There is no simulation training. — [IMO ar5iv](https://ar5iv.labs.arxiv.org/html/2210.15287)

**DIDO (Zhang et al., RA-L/IROS 2022; quadrotor, IMU + rotor tachometers)**
- Cascaded networks: (a) De-Bias Nets, small 1D ResNets with one residual block each, for accel and gyro bias; (b) a Res-Dynamics Net (ResNet over a 20-sample window of body velocity, angular velocity and **rotor speeds**) outputting residual force and covariance; (c) per-axis GRU V-P Nets with hidden sizes 2, 64, 128 or 256 tried, outputting velocity and position. — [DIDO ar5iv](https://ar5iv.labs.arxiv.org/html/2203.03149)
- Fusion is a two-stage EKF: a rotation stage, then a translation stage using **quadrotor dynamics** (quadratic thrust minus linear drag plus learned residual) as the process model, updated with network velocity and position. The authors argue that dynamics-based propagation preserves the tilt–velocity coupling that accel-driven propagation breaks. — [DIDO ar5iv](https://ar5iv.labs.arxiv.org/html/2203.03149)
- Data: 274 real trajectories, 325 min and 19.92 km. Results appear only as CDF plots; the text gives no ATE numbers. The paper claims DIDO beats TLIO and RoNIN. — [DIDO ar5iv](https://ar5iv.labs.arxiv.org/html/2203.03149)

**Deep IMU Bias Inference (Buchanan et al., RA-L 2022/23)**
- Learns bias evolution, not motion. A 2-layer LSTM (hidden 256, about 30 MB, under 6 ms) takes 1 s IMU windows plus the previous bias at 2 Hz. A Transformer (about 200 MB) runs at 1 Hz. The output is a unary bias factor with **fixed** covariance (Σ_ba = 2.5e-3·I, Σ_bg = 2.5e-5·I). — [Buchanan HTML](https://arxiv.org/html/2211.04517v1)
- EuRoC APE (m), baseline → LSTM / Transformer: MH02 0.37 → 0.23 / 0.13; V101 0.17 → 0.08 / 0.08; V202 0.29 → 0.23 / 0.10; V103 0.27 → 0.27 / 0.17. The headline is "average 15% reduction in drift rate". A 5 s blackout on Spot gave mean 5 m RPE: baseline 0.26, LSTM 0.22, Transformer 0.20. — [Buchanan HTML](https://arxiv.org/html/2211.04517v1)
- A related 2025 approach predicts IMU bias with a seq2seq network inside an invariant MSCKF, with bias removed from the state, and reports good performance during long vision outages. — [Altawaitan et al. arXiv 2505.06748](https://arxiv.org/html/2505.06748v2)

### Inferences
- The dominant fusion pattern fits our MSCKF directly. It is a relative-displacement update between two existing clones in a gravity-aligned, yaw-anchored frame (TLIO), or a current-frame body-velocity update (AirIO), with a learned diagonal covariance inflated about 10x and χ² gating. Per update this costs a 3-row EKF update, which is trivial next to the network.
- Real-drone IMU-only ATE of 0.4–1.3 m comes from about 1–3 min Blackbird flights with real aerodynamics. These numbers are not directly transferable to our setting (see Q2).

### Gaps
- TLIO and DIDO absolute ATE numbers exist only in figures. RNIN-VIO numeric results and network size could not be extracted (PDF unreadable).
- No parameter or MAC counts were found for IMO's TCN or for AirIO's light variants beyond the latent sizes.

---

## Q2. Does learned IO work for drones without rotor drag, given controller-induced dynamics? What about AirIO's body-frame claims and Cioffi's thrust input?

### Takeaway
Published drone learned-IO successes all rely on physical information that our simulator lacks or that we do not observe. IMO uses thrust and learns drag. DIDO uses rotor speeds and a drag model. AirIO's simulated data includes linear drag. With no drag and no thrust input, the IMU's horizontal specific force carries essentially no information about velocity. A learned network could then only exploit statistical regularities of the planner and controller, acting as a learned motion prior. That is a much weaker signal, and no published result addresses it.

### Cited Findings
- AirIO abstract: existing learned IO "fail[s] to generalize to UAVs" because drone motion is highly dynamic and nonlinear compared with pedestrians. Converting IMU data to the global frame "undermines the observability of critical kinematic information in UAVs". A body-frame representation gives a 66.7% average accuracy gain across three datasets, and explicit attitude encoding adds a further 23.8%. — [AirIO abstract](https://arxiv.org/abs/2501.15659)
- AirIO's simulated Pegasus dataset (Isaac Sim) uses a "quadratic thrust curve and linear drag model" with no external disturbances. It was used for ablations and representation analysis. AirIO uses no thrust signal; IMO does. — [AirIO HTML](https://arxiv.org/html/2501.15659v2)
- IMO feeds collective thrust instead of accelerometer data and "learns to predict drag along the body x and y axes". A pure physics thrust model without learning gives 10.1 m ATE versus 0.56 m with learning. — [IMO ar5iv](https://ar5iv.labs.arxiv.org/html/2210.15287)
- DIDO's process model is thrust minus linear drag (D·v) plus a learned residual force from rotor speeds. It argues that this coupling between tilt and velocity is what pure accelerometer propagation loses. — [DIDO ar5iv](https://ar5iv.labs.arxiv.org/html/2203.03149)

### Inferences (not directly sourced; physics reasoning)
- On a quadrotor the accelerometer measures specific force, which is thrust plus drag divided by mass, in the body frame. Without rotor drag, body-x/y specific force is about zero and body-z equals thrust/m, regardless of velocity. Velocity information in real-drone IMU data comes mostly from drag (the "drag-as-velocity-sensor" effect that IMO and DIDO exploit). **Our simulator removes that channel**, so the main mechanism behind real-drone learned IO is absent.
- What remains is a learned motion prior. The network can learn statistical regularities of the Bezier-roadmap planner and controller, for example:
  - typical speed ranges and speed limits;
  - acceleration and attitude history implying a phase within a segment (accelerating, cruising or braking);
  - start or stop at rest.

  This resembles RoNIN's use of gait regularity for pedestrians. It can bound velocity drift (a velocity-magnitude prior with learned variance) but cannot measure velocity.
- AirIO's body-frame plus attitude finding likely still applies in that the network needs attitude, since tilt encodes commanded acceleration under a controller. AirIO's evidence comes from drag-containing data, though.
- Recommendation for testing: before building a network, measure how much information exists. Train a tiny model on simulated windows to regress body velocity, and check its error against a constant "mean speed" prior. If it does not beat the prior substantially, learned IO is not worth integrating here.

### Gaps
- I found no paper that evaluates learned IO on drag-free simulated quadrotors or that ablates drag out. This is the critical unknown for our setting.

---

## Q3. What are the smallest networks that still help, and what are their MAC counts, accuracy-versus-size curves and int8 results?

### Takeaway
Mainstream IO networks cost 15–72 MFLOPs per inference, 50–240x our 0.3 M-op budget. Even the compact versions (TinyIO, Deeplite, TinyOdom) stay in the multi-MFLOP range or report only size reductions. A network under 0.3 M MACs per frame is not represented in the literature. It is feasible as a small causal TCN or GRU, but its accuracy would have to be validated empirically.

### Cited Findings
- TinyIO Table I (FLOPs M / params M): R-ResNet 38.25 / 4.64; R-LSTM 57.47 / 13.59; RNIN 72.03 / 5.26; I-IMUNet 18.84 / 3.66; DeepILS 15.29 / 2.29; Deeplite 59.05 / 0.297; TLIO 39.44 / 5.42; TinyIO 26.19 / 3.57. On RoNIN, ATE is TinyIO 4.68 m vs TLIO 5.52 m vs R-ResNet 6.12 m, so cutting 31% of FLOPs did not hurt accuracy. The paper has internal inconsistencies in its claimed reductions and in the deploy FLOPs. — [TinyIO](https://arxiv.org/html/2507.15293v4)
- TinyOdom (IMWUT 2022) uses hardware- and quantization-aware Bayesian NAS over TCNs. It reports models **31–134x smaller** than state of the art, with 2.5–12 m error over 60 s across pedestrian, animal, **aerial** and underwater dead-reckoning, on microcontrollers using TFLite-Micro C++ code. Exact per-model MAC and flash figures were not found in the summaries I read. — [TinyOdom NSF PAR](https://par.nsf.gov/biblio/10385251-tinyodom-hardware-aware-efficient-neural-inertial-navigation)
- DIDO tried GRU hidden sizes down to **2** for its per-axis V-P nets, a sign that tiny recurrent units were considered viable for quadrotor velocity. Accuracy per size appears only in plots. — [DIDO ar5iv](https://ar5iv.labs.arxiv.org/html/2203.03149)
- ICD-Net (2025) uses a very small feature extractor: two Conv1D branches (kernel 2, stride 2, 7 channels), two FC layers with layernorm, and velocity and log-variance heads over 1 s IMU windows. Parameters and runtime are not reported. — [ICD-Net](https://arxiv.org/html/2512.00037v1)

### Inferences (budget arithmetic, not sourced)
- **Recompute-from-scratch TCN at 20 Hz.** The window is 1 s of IMU downsampled to 100 Hz, 6 channels plus gravity-aligned attitude. The layers are:
  - conv 6→16, k5 s2: about 24 k MACs
  - conv 16→32, k5 s2: about 64 k MACs
  - conv 32→32, k3 s2: about 40 k MACs
  - FC 416→64: about 27 k MACs
  - heads: under 1 k MACs

  Total is about 155 k MACs, or about 310 k ops if a multiply and an add count separately. This is at the edge of the budget, with no single-frame spikes.
- **Streaming alternatives:** these are far cheaper and fit the per-frame rule naturally.
  - A **causal dilated TCN with cached activations** computes only new samples per frame, typically a few to tens of k MACs.
  - A **GRU with hidden size 32** costs about 3.7 k MACs per IMU sample, or about 37 k per frame at 200 Hz IMU.
- int8 or fixed-point inference is supported by the TinyOdom pipeline (quantization-aware NAS). For wasm SIMD128, int16 or f32 dot products of this size are cheap either way. Quantization matters more for model size than for our op budget.

### Gaps
- No published accuracy-versus-MACs curve below about 1 MFLOP for inertial odometry was found. No published int8 accuracy-loss numbers for IO nets were extracted; TinyOdom likely has them in the full paper.

---

## Q4. How would a learned IO measurement complement sparse vision (8–20 features at 5 Hz) in an EKF, and are there published hybrid results?

### Takeaway
Hybrids exist and help mainly during visual degradation or blackout: RNIN-VIO, ICD-Net + VINS-Fusion, learned bias in VIO and in invariant MSCKF. Reported gains run from about 15% drift reduction in nominal conditions to 60–98% during multi-second camera blackouts. The cleanest integration for an MSCKF is a TLIO-style clone-to-clone displacement update, or a learned bias or velocity prior, that is active all the time and weighted by learned covariance.

### Cited Findings
- **ICD-Net + VINS-Fusion** (UZH-FPV real drone racing): network displacement and variance become a velocity residual weighted by diag(1/σ²) plus a smoothness term in Ceres. Results:
  - Nominal mean APE averaged 4.59 → 2.79 m (−38.8%).
  - With **4–7 s camera blackouts**, mean APE averaged 72.98 → 6.16 m (−60.6%); on one sequence it fell from 190.29 to 3.12 m, a case where the baseline lost track.

  Caveats: only 3 test sequences, and possible train/test leakage from the same trajectories. — [ICD-Net](https://arxiv.org/html/2512.00037v1)
- **RNIN-VIO**: a tightly coupled EKF with network measurements that lets visual constraints drop out at any time. The authors call it significantly better than VIO in weak or repeated texture and motion-blur scenes. — [RNIN-VIO](https://zju3dv.github.io/rnin-vio.github.io)
- **Deep IMU Bias Inference**: learned bias factors cut EuRoC APE by 21–66%, depending on sequence and model. Errors during a 5 s blackout dropped from 0.26 m to 0.20–0.22 m. — [Buchanan](https://arxiv.org/html/2211.04517v1)
- **Learned bias in invariant MSCKF** reports good performance during long periods without vision. — [Altawaitan et al.](https://arxiv.org/html/2505.06748v2)
- IMO's own comparison: an IMU-only learned EKF (0.56 m) nearly matches a camera system that uses known gates (0.48 m). Generic VIO failed at racing speeds (OpenVINS 98 m). — [IMO ar5iv](https://ar5iv.labs.arxiv.org/html/2210.15287)
- "Extended Model-Based Learned Inertial Odometry" (arXiv 2611.09584, Nov 2026) explicitly frames learned IO as a short-term VIO fallback when cameras fail in darkness, low texture or smoke. Its full text could not be read. — [arXiv 2611.09584](https://arxiv.org/pdf/2611.09584)

### Inferences
- **Which measurement to use:** for our dominant error (translation offset building up in vision-starved stretches), a displacement or velocity measurement with honest covariance is the right type. It directly limits velocity-error growth, which integrates into position offset.
  - Bias-only learning (Buchanan) helps less when accel bias is already observable from vision.
  - In a drag-free simulator with no thrust input, bias-only learning may still be one of the few things an IMU network can genuinely learn, because bias is physically present in the IMU signal.
- **Clone-based update:** the MSCKF already keeps clones, so a TLIO-style relative displacement between clone pairs costs almost nothing beyond the network. Express it in a yaw-anchored, gravity-aligned frame so it adds no spurious yaw information.
- **Weighting and gating:** inflate the covariance (TLIO uses 10x) because overlapping windows are correlated. Gate with χ². Otherwise a confident but wrong motion prior will bias the filter during well-observed stretches and raise unaligned ATE.

### Gaps
- No published hybrid result uses very sparse vision (8–20 features at 5 Hz). All hybrids above use full VIO front ends with dropouts. The gain in our regime must be measured.

---

## Q5. What does training need? Can a fully simulated model generalize to similar simulated flights?

### Takeaway
Published systems train on small real datasets: about 10–15 min (IMO), about 5–8 min (ICD-Net), up to 325 min (DIDO). They report reasonable generalization to unseen trajectories of the same platform. With unlimited simulated data drawn from the same planner and IMU noise model, data volume is not a constraint. The real risk is that the drag-free simulator carries little learnable velocity signal (Q2), not overfitting.

### Cited Findings
- IMO trained on about 10 min of Blackbird data and about 5 min of racing-track data, all real. — [IMO ar5iv](https://ar5iv.labs.arxiv.org/html/2210.15287)
- AirIO generalizes from 5 Blackbird SEEN sequences to 5 UNSEEN ones: 0.40 → 1.31 m ATE, versus TLIO 1.19 → 3.48 m and IMO 0.93 → 9.02 m. Generalization degrades about 3x, and more for thrust-based IMO. AirIO also trains on a simulated Pegasus dataset but does not report sim-to-real transfer. — [AirIO HTML](https://arxiv.org/html/2501.15659v2)
- DIDO used 200 of 274 real random trajectories for training (19.92 km in total). — [DIDO ar5iv](https://ar5iv.labs.arxiv.org/html/2203.03149)
- Buchanan's bias network transferred from handheld to quadruped without retraining, with mixed gains (0.31 → 0.27 m on Spot Easy for the LSTM; the Transformer showed no gain). — [Buchanan](https://arxiv.org/html/2211.04517v1)
- TLIO's training augmentations make networks robust to filter-provided orientation and bias errors at runtime:
  - random yaw rotation;
  - bias perturbations of ±0.2 m/s^2 and ±0.05 rad/s;
  - gravity-direction perturbation of 5°.

  — [TLIO ar5iv](https://ar5iv.labs.arxiv.org/html/2007.01867)

### Inferences
- Train on simulated windows matching the evaluation planner, adding TLIO-style augmentations and attitude noise similar to what the filter produces at runtime. Train with ground-truth attitude and test with filter attitude, as AirIO and IMO do.
- **Server-mismatch risk:** server flights are about 60 m, while the project's local flights are about 17 m per project memory. Train on the server-like distribution (longer, faster flights), or the learned prior will be miscalibrated on speed.

### Gaps
- No study of sim-to-sim generalization across planner or parameter shifts for learned IO was found.
- No published evidence was found on how much velocity information drag-free quadrotor IMU data contains (see Q2). This should be measured directly with a quick offline regression experiment before any integration work.
