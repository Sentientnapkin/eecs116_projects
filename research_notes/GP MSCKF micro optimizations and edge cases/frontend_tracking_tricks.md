# Front-end (feature tracking and outlier rejection) tricks for a small C MSCKF

Experiments, code and tables: research/single_model/frontend/NOTES.md (fe2.c, adopted_fbh.patch). Findings from literature are marked; anything without a link is my background knowledge and UNVERIFIED.

## Q1. What do OpenVINS, VINS-Mono, ROVIO, DSO and others do that we do not; cost for ~20 M fuel/frame?

### Takeaway
The standard trackers differ from ours mainly in (a) a RANSAC outlier stage (fundamental matrix, or 2-point with gyro rotation), (b) larger pyramids/windows via OpenCV, (c) histogram equalisation/CLAHE, (d) occupancy-mask minimum distance. Our camera is pure pinhole (no distortion), so there is no undistortion issue; the 117-122 deg FOV only stretches patches at the edge. Of the cheap items I could test, only a forward-backward track check helped.

### Cited Findings
- VINS-Mono: KLT tracking, new corners detected to keep 100-300 features with a minimum separation, outlier rejection by RANSAC with a fundamental-matrix model, keyframe by average parallax (gyro-compensated); the paper gives no numeric separation or parallax threshold — [VINS-Mono ar5iv](https://ar5iv.labs.arxiv.org/html/1708.03852), [arXiv 1708.03852](https://arxiv.org/abs/1708.03852)
- OpenVINS TrackKLT: optional equalizeHist or CLAHE (clip 10, 8x8 tiles) before cv::buildOpticalFlowPyramid; calcOpticalFlowPyrLK with OPTFLOW_USE_INITIAL_FLOW and termination 30 iterations / eps 0.01; findFundamentalMat FM_RANSAC with threshold 2/max(focal) on undistorted normalised points, skipped if <10 points; 10 px border; detection only when features needed < min(20, 0.5*num_features); min_px_dist occupancy mask; no forward-backward check in the mono path — [TrackKLT.cpp](https://github.com/rpng/open_vins/blob/master/ov_core/src/track/TrackKLT.cpp). Defaults reported by a secondary source: 5x5 grid, min_px_dist 10, histogram method HISTOGRAM; I did not find a documented pyramid-level default (docs page 404) — [VioManagerOptions via search](http://docs.ros.org/en/melodic/api/ov_msckf/html/VioManagerOptions_8h_source.html)
- 2-point RANSAC for camera-IMU: with gyro rotation known, E=[t]x R reduces to a translation direction, fewer hypotheses than 5-point; Troiani et al. ICRA 2014 — [paper](https://rpg.ifi.uzh.ch/docs/ICRA14_Troiani.pdf) (details from search snippets only; thresholds unverified)
- Forward-backward error: track forward and backward and measure the disagreement to detect failures (Kalal, Mikolajczyk, Matas, ICPR 2010) — [PDF](http://kahlan.eps.surrey.ac.uk/featurespace/tld/Publications/2010_icpr.pdf) (abstract-level only read)
- DSO: full photometric calibration (exposure, vignetting, response) and sampling of pixels evenly with gradient, no detector — [arXiv 1607.02565](https://arxiv.org/abs/1607.02565) (affine a,b model not confirmed in the fetched page)
- ROVIO: EKF with direct photometric multi-level patch updates around FAST corners — secondary sources only via search; original paper not opened.
- Feature selection by information/conditioning: Zhang et al., Good Features to Track for Visual SLAM, CVPR 2015 — [PDF](https://openaccess.thecvf.com/content_cvpr_2015/papers/Zhang_Good_Features_to_2015_CVPR_paper.pdf) (abstract-level)
- Repo facts (read from files): the camera in episode.json is pinhole with empty distortion list, hFOV 122.4 deg on the 640x480 source; the guest sees 320x240. Our pyramid has 2 levels, 9x9 window, 10x6 grid, MAX_OBS 8 but only 7 clones exist (MAX_CLONES 6 + current), so extending MAX_OBS alone cannot lengthen the usable observation set; lifetime would need more clones (fuel and covariance cost).

### Inferences
- Because rotation is known, a 2-point test is cheap (~40 hypotheses x ~50 tracks, no fuel increase seen: peak 21.1 M). But at 0.5 px/frame parallax the epipolar residual is on the order of the KLT noise, so it removes little; see experiments.
- No distortion handling is needed; radius weighting is the only wide-FOV measure available, and it did not help.
- Predicted scale is irrelevant for translation-only KLT at one-frame baselines (<1% scale change).

### Gaps
- Exact OpenVINS pyramid/window defaults, ROVIO patch sizes, and DSO affine brightness details were not verified from primary text. Baker-Matthews / Bouguet not opened.

## Q2. Which address our failure classes?
### Takeaway
Textureless/dark: a weaker-corner fallback (cellfall) and contrast normalisation changed little on the G+C1 base (cellfall search -0.054 n.s., static +0.04, val +0.06; norm +0.01 with 28.9 M fuel). Short tracks / outliers: forward-backward check is the one winner. Startup lock-out is not a front-end problem here (diag NOTES: 80% of bad flights have plenty of tracks).
### Cited Findings (this repo; numbers from the runs)
- Table of all arms and replicates: research/single_model/frontend/NOTES.md. Old-base screen: grid 16x8 +0.288 (sig worse, 37.7 M fuel), KLT_R=5 +0.230 (sig worse), 3 levels +0.298 (worse), radius weighting +0.261 (sig worse), r<=1.4 detection +0.114.
### Inferences
- Denser grids and larger windows hurt because the MSCKF is limited by consistency, not feature count; fewer, cleaner tracks win. This is also why FB (rejecting contaminated tracks) helps.
### Gaps
- Flat/dark class specifically (26329 scenes, 33% >5 m flights): no front-end switch moved it measurably on search; not isolated per class in these runs.

## Q3. Experiments (G+C1 base = inventive/adopted.c, 3 replicates, search n=119 / val n=25 / fresh n=711)
### Takeaway
Adopt FE_FB with half-rate checking (forward-backward KLT check at 0.5 px on alternate frames): search 0.931 vs 1.079 (-0.149 [-0.305,+0.024]; static -0.129 CI excludes 0), val 0.441 vs 0.537, fresh 0.618 vs 0.733 (-0.114 [-0.167,-0.064]; static and mid each significant, no flight >10 m, max 6.9 m). Cost: peak fuel 22.0 M on search/val (unchanged), 24.5 M on the fresh static pool, p95 about +2 M.
### Cited Findings
- Every-frame FB: search 0.978, fresh -0.111 but two new >10 m flights and 26.8 M fuel; not adopted. FB at 1.0 px: search 0.996.
- Gyro 2-point RANSAC (fe2_rs): search -0.078 n.s., val +0.136 [+0.035,+0.252] worse; rejected.
- Contrast normalisation: +0.010, fuel 28.9 M; rejected. Cellfall: -0.054 n.s., static/val worse; rejected.
- Patch: research/single_model/frontend/adopted_fbh.patch (touches only `track_all`; adds one backward `klt` call per track on alternate frames).
### Inferences
- With the fuel rewrite (KLT patch extraction ported), the backward KLT cost should shrink proportionally; re-measure after porting. Effect sizes on search are near the replicate noise (reps range 0.90-0.95 vs ref 1.03-1.29), so the fresh result carries the argument.
### Gaps
- Not tested: affine gain/bias KLT on G+C1 (earlier texture notes: mixed), track retry, information-gain feature selection, 3-level pyramid only for weak tracks, per-class (flat/dark/fast/reverse) breakdown, sealed fold untouched.
