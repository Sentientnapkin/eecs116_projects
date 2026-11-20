# Autoloop summary

```
== PROGRESS: phase final | step 0.150 gen 8 | budget used 3.80h / 4.0h | ETA 0.20h | 192 vectors ok, 0 failed/ill-posed, 12 fresh-A, 4 fresh-B | 50.5 vec/h | last eval 13:40:16
   state mtime 14:08:59; promotions: 2
== REFERENCE ba7c9bb8d93e search 0.953 (reps [0.939, 0.952, 0.968]) val 0.587 static 0.496 mid 1.359 >3/5/10: 10/2/0 fuel peak 21.61M | fresh-A 0.688
   default (gate build): search 1.079 val 0.537 -> improvement +0.126
== LEADERBOARD (feasible vs current reference first; sorted by replicate-mean search ATE)
hash         search  val    static mid    >3 >5 >10 fuelM  d_vs_ref fresh-A  feas  delta vs default
25579ce5fe59 0.908  0.585  0.514  1.257   9  2  0  21.41  +0.045  0.755  yes  {"ACCEL_NOISE": 0.252967, "INIT_VELOCITY_STD": 0.591716, "START_STD_X"
509d9bc35289 0.922  0.608  0.498  1.300  10  2  0  22.26  +0.030  0.692  yes  {"ACCEL_NOISE": 0.23265, "INIT_VELOCITY_STD": 0.591716, "ZUPT_DISPARIT
4e06068e24bf 0.929  0.582  0.488  1.321   8  3  0  21.72  +0.024  0.704  yes  {"INIT_VELOCITY_STD": 0.591716, "START_STD_X": 0.532307, "SPEED_STD": 
99dae1b82d0a 0.938  0.592  0.496  1.330   9  2  0  21.35  +0.015  0.655  yes  {"INIT_TILT_STD": 0.0410968, "INIT_VELOCITY_STD": 0.594969, "ZUPT_DISP
45ef8f98c348 0.939  0.570  0.499  1.330   9  2  0  21.45  +0.014  0.649  yes  {"INIT_VELOCITY_STD": 0.591716, "ZUPT_DISPARITY": 0.52, "MIN_DEPTH": 0
7b04a1522e34 0.943  0.572  0.507  1.330   9  2  0  21.33  +0.010  -      yes  {"INIT_VELOCITY_STD": 0.769231, "ZUPT_DISPARITY": 0.52, "MIN_DEPTH": 0
74d629e3261d 0.943  0.583  0.497  1.339   9  3  0  21.54  +0.010  -      yes  {"INIT_VELOCITY_STD": 0.769231, "ZUPT_DISPARITY": 0.52, "MIN_DEPTH": 0
4da146733d31 0.949  0.581  0.488  1.359  10  2  0  21.87  +0.004  -      yes  {"INIT_VELOCITY_STD": 0.591716, "ZUPT_DISPARITY": 0.52, "MIN_DEPTH": 0
32ecf58ec9d9 0.951  0.576  0.500  1.352  10  2  0  21.52  +0.002  -      yes  {"ACCEL_NOISE": 0.273772, "INIT_VELOCITY_STD": 0.769231, "ZUPT_DISPARI
e32a2ab5d235 0.952  0.578  0.494  1.359  10  2  0  21.75  +0.001  -      yes  {"INIT_VELOCITY_STD": 0.769231, "ZUPT_DISPARITY": 0.52, "MIN_DEPTH": 0
== PARETO front (replicate-mean search ATE vs peak fuel), all valid vectors
   25579ce5fe59 search 0.908 fuel 21.41M {"ACCEL_NOISE": 0.252967, "INIT_VELOCITY_STD": 0.591716, "START_STD_X": 0.532307
   99dae1b82d0a search 0.938 fuel 21.35M {"INIT_TILT_STD": 0.0410968, "INIT_VELOCITY_STD": 0.594969, "ZUPT_DISPARITY": 0.
   7b04a1522e34 search 0.943 fuel 21.33M {"INIT_VELOCITY_STD": 0.769231, "ZUPT_DISPARITY": 0.52, "MIN_DEPTH": 0.338, "KLT
   a6f598e0a5e9 search 0.955 fuel 21.11M {"INIT_VELOCITY_STD": 0.769231, "ZUPT_DISPARITY": 0.52, "ZUPT_STD": 0.026, "MIN_
   2305bd6411d0 search 0.957 fuel 21.03M {"INIT_VELOCITY_STD": 0.769231, "ZUPT_DISPARITY": 0.52, "ZUPT_STD": 0.0153846, "
   21d47f2d5b0e search 1.087 fuel 16.98M {"MAX_CLONES": 5}
== SENSITIVITY (phase A one-at-a-time; best/worst = change of replicate-mean search ATE vs default; sorted by effect)
   GYRO_NOISE           default 0.07     best -0.095 worst +0.047  0.035:-0.05 0.056:-0.10 0.0875:+0.02 0.14:+0.05
   KLT_MIN_EIG          default 2        best -0.055 worst +0.062  1.6:+0.06 1.92308:-0.04 2.5:-0.06 3.25:-0.03
   INV_VZ               default 0.3      best -0.048 worst +0.022  0.24:-0.05 0.375:+0.02
   START_STD_X          default 0.5      best -0.047 worst +0.005  0.4:-0.05 0.625:+0.01
   MIN_DEPTH            default 0.2      best -0.044 worst +0.010  0.16:+0.01 0.25:-0.04
   HOLD_T               default 1        best -0.041 worst -0.014  0.8:-0.01 1.25:-0.04
   ZUPT_DISPARITY       default 0.4      best -0.042 worst -0.023  0.32:-0.02 0.5:-0.04
   INV_LAT              default 0.5      best -0.033 worst +0.015  0.4:-0.03 0.625:+0.02
   INIT_VELOCITY_STD    default 1        best -0.034 worst +0.002  0.8:-0.03 1.25:+0.00
   MIN_OBS              default 3        best +0.008 worst +0.162  2:+0.01 4:+0.16
   ZUPT_STD             default 0.02     best -0.032 worst -0.013  0.016:-0.03 0.025:-0.01
   START_MEAN_FWD       default 0.9      best +0.049 worst +0.194  0.72:+0.19 1.125:+0.05
   KLT_MAX_ERR          default 25       best -0.013 worst +0.067  20:-0.01 31.25:+0.07
   CHI2_Z               default 1.645    best +0.057 worst +0.188  1.316:+0.06 2.05625:+0.19
   INIT_TILT_STD        default 0.05     best -0.030 worst -0.022  0.04:-0.02 0.0625:-0.03
   ACCEL_NOISE          default 0.28     best -0.019 worst +0.024  0.14:-0.02 0.224:+0.02 0.35:+0.02 0.56:-0.01
   SPEED_STD            default 0.5      best -0.019 worst +0.017  0.4:-0.02 0.625:+0.02
   DETECT_MIN_SCORE     default 1000     best -0.025 worst -0.016  800:-0.02 1250:-0.02
   MOVE_TILT_STD        default 0.15     best +0.050 worst +0.156  0.12:+0.05 0.1875:+0.16
   THRUST_GATE          default 9.21     best -0.017 worst +0.006  7.368:-0.02 11.5125:+0.01
   START_STD_Z          default 0.6      best +0.052 worst +0.142  0.48:+0.05 0.75:+0.14
   HOLD_T0              default 0.4      best -0.012 worst +0.016  0.32:-0.01 0.5:+0.02
   CLONE_EVERY          default 4        best +0.150 worst +0.214  3:+0.15 5:+0.21
   ACCEL_BIAS_WALK      default 0.001    best -0.009 worst +0.015  0.0008:-0.01 0.00125:+0.02
   THRUST_MODEL_STD     default 0.05     best -0.006 worst +0.022  0.04:-0.01 0.0625:+0.02
   HOLD_TAU             default 1        best -0.007 worst +0.018  0.8:+0.02 1.25:-0.01
   GYRO_BIAS_WALK       default 0.0006   best -0.004 worst +0.028  0.00048:-0.00 0.00075:+0.03
   DET_FORCE            default 8.8      best +0.000 worst +0.034  8.75:+0.00 9.3:+0.03
   HOLD_GN              default 0.12     best -0.000 worst +0.029  0.096:+0.03 0.15:-0.00
   MAX_DEPTH            default 40       best +0.035 worst +0.064  32:+0.06 50:+0.04
   KLT_ITERS            default 5        best +0.097 worst +0.124  4:+0.12 6:+0.10
   KLT_EPS              default 0.03     best +0.016 worst +0.042  0.024:+0.02 0.0375:+0.04
   PIXEL_STD            default 1.5      best +0.026 worst +0.047  1.2:+0.03 1.875:+0.05
   START_T              default 2        best +0.011 worst +0.031  1.6:+0.03 2.5:+0.01
   TRI_MIN_EIG          default 1e-06    best -0.004 worst -0.002  8e-07:-0.00 1.25e-06:-0.00
   SPEED_TAU            default 2        best +0.081 worst +0.095  1.6:+0.08 2.5:+0.09
   START_STD_Y          default 0.35     best +0.055 worst +0.068  0.28:+0.06 0.4375:+0.07
   MAX_CLONES           default 6        best +0.008 worst +0.011  5:+0.01 8:+0.01
   MAX_UPDATE_FEATURES  default 20       best +0.000 worst +0.003  16:+0.00 25:+0.00
   ZUPT_MIN_FEATURES    default 10       best +0.000 worst +0.000  8:+0.00 12:+0.00
== CATEGORIES (mean over visible flights; reference | default | best feasible)
   all                  n=144 ref 0.889 default 0.985 best 0.852  worst flight fastmid-106366104_174226329-00 7.81
   wrong_dir_gt90       n= 10 ref 2.724 default 3.380 best 2.467  worst flight fastmid-ProcTHOR-Train-100-02 7.57
   fast_start_gt1.5     n= 14 ref 1.830 default 1.918 best 1.758  worst flight fastmid-107734146_175999971-01 4.90
   slow_start_lt0.3     n=  7 ref 1.634 default 1.741 best 1.648  worst flight fastmid-106366104_174226329-01 4.17
   static_start         n= 68 ref 0.516 default 0.589 best 0.527  worst flight fast-106366104_174226329-00 3.30
   textureless_dark     n= 12 ref 2.672 default 2.862 best 2.577  worst flight fastmid-106366104_174226329-00 7.81
   long_path_gt58m      n= 56 ref 1.040 default 1.213 best 1.043  worst flight fastmid-106366104_174226329-00 7.81
   high_yaw_top25       n= 36 ref 0.775 default 0.844 best 0.763  worst flight fastmid-ProcTHOR-Train-178-01 3.33
   clean_scene          n= 21 ref 0.933 default 1.086 best 0.784  worst flight fastmid-ProcTHOR-Train-158-07 4.51
   mid_ang_0_45         n= 48 ref 0.977 default 0.906 best 0.924  worst flight fastmid-106366104_174226329-00 7.81
   mid_ang_45_90        n= 16 ref 0.877 default 1.237 best 0.829  worst flight fastmid-106366104_174226329-02 3.47
   mid_ang_90_135       n=  6 ref 2.373 default 2.959 best 2.403  worst flight fastmid-ProcTHOR-Train-100-02 7.57
   mid_ang_135_180      n=  4 ref 3.249 default 4.013 best 2.563  worst flight fastmid-ProcTHOR-Train-158-07 4.51
== FRESH-A (475 unselected flights, tuning confirmation)
   ba7c9bb8d93e mean 0.688 static 0.495 mid 0.887 >3/5/10 14/4/0 ang135-180 0.97
   ef0f886b140c mean 0.685 static 0.490 mid 0.887 >3/5/10 15/5/0 ang135-180 0.97
   a5ba5851c3d3 mean 0.690 static 0.487 mid 0.899 >3/5/10 15/4/0 ang135-180 1.05
   25579ce5fe59 mean 0.755 static 0.517 mid 1.000 >3/5/10 25/6/0 ang135-180 1.72
   509d9bc35289 mean 0.692 static 0.491 mid 0.899 >3/5/10 15/6/0 ang135-180 1.05
   4e06068e24bf mean 0.704 static 0.494 mid 0.921 >3/5/10 17/5/0 ang135-180 1.62
   99dae1b82d0a mean 0.655 static 0.474 mid 0.841 >3/5/10 14/4/0 ang135-180 0.98
   45ef8f98c348 mean 0.649 static 0.463 mid 0.841 >3/5/10 14/3/0 ang135-180 0.98
== FRESH-B (held out, final top-3 only)
   ba7c9bb8d93e mean 0.756 >3/5/10 12/3/0 
   7ad38c135773 mean 0.755 >3/5/10 12/2/0 (default)
   45ef8f98c348 mean 0.743 >3/5/10 12/3/0 
   99dae1b82d0a mean 0.726 >3/5/10 11/3/0 
```
