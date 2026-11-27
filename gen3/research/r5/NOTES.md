# r5 — depth-aware feature management (NOTES)
## SUMMARY
(in progress)

## Log
- base.c = copy of agents/sweep/baseA160.c + r5 switches (R5_DIAG, R5_DEC, R5_PAR, R5_RANK; all default off). mk.py r5_ref with
  the Ze0 flags -> 670bc1da == frozen baseline (VERIFIED).
- Error decomposition of the baseline (tools/decomp.py sw_a1_Ze0, 358 v3val, harness ATE reproduced exactly 0.655):
  perfect-rotation counterfactual (estimated body-frame increments re-integrated with GT orientation) 0.616 (-6%), yaw-only 0.610;
  yaw rms 2.7 deg (rooms 3.9), tilt rms 0.8 deg. => rotation/heading is NOT the dominant error; ceiling for rotation-only
  feature constraints / gyro-bias work ~ -0.04 m. Rooms 0.468->0.446, warehouse 0.829->0.773, forest 0.716->0.651.
- Row accounting (R5_DIAG on mid40, per flight of 1200 frames): 2254 features attempted, 16.9k MSCKF rows (7.5 rows/feature,
  ~14 rows/frame ~ 1.5 M of the 3.6 M budget), triangulation failures 2.2% (rows 2%), chi2 gate rejects 2%, the row budget binds
  ~940 times per flight. => parallax prescreen can save little; decimating observations (rows 2n-3) is the main row lever.
## Pipeline results (auto-appended by tools/pipe.py; d vs sweep 3-rep reference at the same GOV_B)
- [pipe 21:53] dec4_b27 (v3val, GOV_B 2.7e6, R5_DEC=4, 1 rep): mean 0.714 vs ref 0.730 d -0.015 [-0.044,+0.013] sw 0.700/0.701 ro/wa/fo 0.598/0.847/0.722 >3m 0 peak 2.73M p95 2.13M dscore +0.029
- [pipe 22:02] dec3_b27 (v3val, GOV_B 2.7e6, R5_DEC=3, 1 rep): mean 0.737 vs ref 0.730 d +0.007 [-0.023,+0.037] sw 0.726/0.701 ro/wa/fo 0.629/0.878/0.720 >3m 1 peak 2.73M p95 2.29M dscore -0.040
- [pipe 22:10] rank1_b27 (v3val, GOV_B 2.7e6, R5_RANK=1, 1 rep): mean 0.709 vs ref 0.730 d -0.020 [-0.044,+0.003] sw 0.687/0.701 ro/wa/fo 0.526/0.911/0.731 >3m 2 peak 2.99M p95 2.09M dscore -0.008
- [pipe 22:18] dec5_b27 (v3val, GOV_B 2.7e6, R5_DEC=5, 1 rep): mean 0.716 vs ref 0.730 d -0.013 [-0.037,+0.011] sw 0.692/0.701 ro/wa/fo 0.543/0.895/0.752 >3m 1 peak 2.98M p95 2.07M dscore -0.028
- [pipe 22:26] rank2_b27 (v3val, GOV_B 2.7e6, R5_RANK=2, 1 rep): mean 0.732 vs ref 0.730 d +0.002 [-0.022,+0.027] sw 0.707/0.701 ro/wa/fo 0.515/0.960/0.770 >3m 3 peak 2.97M p95 2.09M dscore -0.072
- [pipe 22:34] par05_b27 (v3val, GOV_B 2.7e6, R5_PAR=0.5, 1 rep): mean 0.738 vs ref 0.730 d +0.009 [-0.012,+0.029] sw 0.706/0.701 ro/wa/fo 0.514/0.959/0.797 >3m 1 peak 2.97M p95 2.11M dscore -0.093
- [pipe 22:41] dec4rank1_b27 (v3val, GOV_B 2.7e6, R5_DEC=4 R5_RANK=1, 1 rep): mean 0.716 vs ref 0.730 d -0.014 [-0.043,+0.013] sw 0.702/0.701 ro/wa/fo 0.587/0.856/0.732 >3m 0 peak 2.74M p95 2.13M dscore +0.023
- [pipe 22:49] dec4_b36 (v3val, GOV_B 3.6e6, R5_DEC=4, 1 rep): mean 0.710 vs ref 0.665 d +0.045 [+0.022,+0.068] sw 0.680/0.641 ro/wa/fo 0.560/0.898/0.698 >3m 0 peak 3.60M p95 2.91M dscore -0.118
- [pipe 22:57] dec3_b36 (v3val, GOV_B 3.6e6, R5_DEC=3, 1 rep): mean 0.745 vs ref 0.665 d +0.080 [+0.054,+0.106] sw 0.732/0.641 ro/wa/fo 0.614/0.900/0.747 >3m 0 peak 3.60M p95 2.98M dscore -0.224
- [pipe 23:05] rank1_b36 (v3val, GOV_B 3.6e6, R5_RANK=1, 1 rep): mean 0.663 vs ref 0.665 d -0.002 [-0.022,+0.017] sw 0.634/0.641 ro/wa/fo 0.475/0.854/0.704 >3m 0 peak 3.74M p95 2.82M dscore +0.011
- [pipe 23:13] dec4_b21 (v3val, GOV_B 2.1e6, R5_DEC=4, 1 rep): mean 0.808 vs ref 0.834 d -0.026 [-0.060,+0.010] sw 0.797/0.811 ro/wa/fo 0.694/0.974/0.770 >3m 3 peak 2.13M p95 1.63M dscore -0.098
- [pipe 23:20] dec3_b21 (v3val, GOV_B 2.1e6, R5_DEC=3, 1 rep): mean 0.762 vs ref 0.834 d -0.072 [-0.103,-0.041] sw 0.758/0.811 ro/wa/fo 0.691/0.888/0.712 >3m 2 peak 2.14M p95 1.77M dscore +0.026
- [pipe 23:28] rank1_b27 (v3val, GOV_B 2.7e6, R5_RANK=1 PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0, 2 rep): mean 0.718 vs ref 0.730 d -0.012 [-0.029,+0.007] sw 0.693/0.701 ro/wa/fo 0.530/0.917/0.750 >3m 2 peak 2.99M p95 2.09M dscore -0.035
- [pipe 23:36] rank1_b27 (v3val, GOV_B 2.7e6, R5_RANK=1 PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0, 3 rep): mean 0.720 vs ref 0.730 d -0.010 [-0.025,+0.006] sw 0.696/0.701 ro/wa/fo 0.534/0.915/0.754 >3m 1 peak 2.99M p95 2.09M dscore -0.042
- [pipe 23:44] dec4_b21 (v3val, GOV_B 2.1e6, R5_DEC=4 PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0, 2 rep): mean 0.813 vs ref 0.834 d -0.021 [-0.054,+0.013] sw 0.804/0.811 ro/wa/fo 0.700/0.968/0.787 >3m 3 peak 2.15M p95 1.63M dscore -0.118
- [pipe 23:52] dec4_b21 (v3val, GOV_B 2.1e6, R5_DEC=4 PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0, 3 rep): mean 0.804 vs ref 0.834 d -0.030 [-0.059,+0.002] sw 0.797/0.811 ro/wa/fo 0.700/0.945/0.785 >3m 3 peak 2.18M p95 1.63M dscore -0.103
- [pipe 00:00] dec3_b21 (v3val, GOV_B 2.1e6, R5_DEC=3 PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0, 2 rep): mean 0.764 vs ref 0.834 d -0.070 [-0.099,-0.040] sw 0.761/0.811 ro/wa/fo 0.681/0.886/0.734 >3m 2 peak 2.16M p95 1.77M dscore +0.016
- [pipe 00:07] dec3_b21 (v3val, GOV_B 2.1e6, R5_DEC=3 PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0, 3 rep): mean 0.771 vs ref 0.834 d -0.063 [-0.091,-0.033] sw 0.766/0.811 ro/wa/fo 0.680/0.903/0.742 >3m 2 peak 2.16M p95 1.77M dscore -0.005
- [pipe 00:10] dec4_b21_v1 (v1val, GOV_B 2.1e6, R5_DEC=4 PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0, 1 rep): mean 0.686 vs ref 0.703 d -0.016 [-0.076,+0.043] sw 0.663/0.686 ro/wa/fo 0.495/0.942/0.807 >3m 1 peak 2.16M p95 1.65M dscore -0.141
- [pipe 00:13] dec3_b21_v1 (v1val, GOV_B 2.1e6, R5_DEC=3 PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0, 1 rep): mean 0.637 vs ref 0.703 d -0.066 [-0.157,-0.001] sw 0.614/0.686 ro/wa/fo 0.457/0.937/0.698 >3m 1 peak 2.14M p95 1.78M dscore +0.027
