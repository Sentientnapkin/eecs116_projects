# Autoloop summary

```
== PROGRESS: phase final | step 0.300 gen 0 | budget used 0.66h / 5.0h | ETA 4.34h | 27 vectors ok, 0 failed/ill-posed, 1 fresh-A, 0 fresh-B | 40.6 vec/h | last eval 10:02:01
   state mtime 10:19:13; promotions: 0
== REFERENCE 3bf122401656 search 1.181 (reps [1.028, 1.223, 1.293]) val 0.545 static 0.680 mid 1.627 >3/5/10: 11/8/0 fuel peak 22.55M | fresh-A 0.834
== LEADERBOARD (feasible vs current reference first; sorted by replicate-mean search ATE)
hash         search  val    static mid    >3 >5 >10 fuelM  d_vs_ref fresh-A  feas  delta vs default
f0ebe615b1c0 1.095  0.565  0.613  1.524  12  7  0  22.77  +0.086  -      yes  {"GYRO_NOISE": 0.056}
cfa7cf039c6b 1.123  0.553  0.630  1.562  13  5  0  22.53  +0.058  -      yes  {"ACCEL_NOISE": 0.224}
7dae40d82e82 1.148  0.517  0.608  1.627  11  8  0  22.54  +0.034  -      yes  {"INIT_TILT_STD": 0.0625}
fa3df67f38c4 1.152  0.631  0.617  1.627  11  7  0  22.48  +0.030  -      yes  {"INIT_VELOCITY_STD": 1.25}
2f8046065b72 1.171  0.566  0.657  1.627  11  8  0  22.52  +0.011  -      yes  {"INIT_VELOCITY_STD": 0.8}
7a30e69e165b 1.176  0.528  0.668  1.627  12  8  0  22.50  +0.005  -      yes  {"INIT_TILT_STD": 0.04}
3bf122401656 1.181  0.545  0.680  1.627  11  8  0  22.55  +0.000  0.834  yes  {}
58d324ffe317 1.181  0.545  0.680  1.627  11  8  0  22.55  +0.000  -      yes  {"DET_GYRO": 0.16}
0bee2a90fd80 1.181  0.545  0.680  1.627  11  8  0  22.55  +0.000  -      yes  {"DET_GYRO": 0.25}
9c9b244633af 1.181  0.545  0.680  1.627  11  8  0  22.55  +0.000  -      yes  {"DET_FORCE": 8.75}
== PARETO front (replicate-mean search ATE vs peak fuel), all valid vectors
   f0ebe615b1c0 search 1.095 fuel 22.77M {"GYRO_NOISE": 0.056}
   cfa7cf039c6b search 1.123 fuel 22.53M {"ACCEL_NOISE": 0.224}
   fa3df67f38c4 search 1.152 fuel 22.48M {"INIT_VELOCITY_STD": 1.25}
== SENSITIVITY (phase A one-at-a-time; best/worst = change of replicate-mean search ATE vs default; sorted by effect)
   GYRO_NOISE           default 0.07     best -0.086 worst +0.070  0.056:-0.09 0.0875:+0.07
   ACCEL_NOISE          default 0.28     best -0.058 worst +0.015  0.224:-0.06 0.35:+0.01
   INIT_TILT_STD        default 0.05     best -0.034 worst -0.005  0.04:-0.01 0.0625:-0.03
   INIT_VELOCITY_STD    default 1        best -0.030 worst -0.011  0.8:-0.01 1.25:-0.03
   MOVE_TILT_STD        default 0.15     best +0.054 worst +0.155  0.12:+0.05 0.1875:+0.16
   DET_FORCE            default 8.8      best +0.000 worst +0.041  8.75:+0.00 9.3:+0.04
   ACCEL_BIAS_WALK      default 0.001    best +0.016 worst +0.053  0.0008:+0.02 0.00125:+0.05
   GYRO_BIAS_WALK       default 0.0006   best +0.023 worst +0.057  0.00048:+0.06 0.00075:+0.02
   START_T              default 2        best +0.021 worst +0.055  1.6:+0.06 2.5:+0.02
   GATE_PAIRS           default 2        best +0.004 worst +0.007  1:+0.01 3:+0.00
   GATE_DISP            default 2        best +0.003 worst +0.004  1.6:+0.00 2.5:+0.00
   DET_GYRO             default 0.2      best +0.000 worst +0.000  0.16:+0.00 0.25:+0.00
   GATE_PAIRS_MAX       default 5        best +0.000 worst +0.000  4:+0.00 6:+0.00
== CATEGORIES (mean over visible flights; reference | default | best feasible)
   all                  n=144 ref 1.071 default 1.071 best 1.003  worst flight fastmid-ProcTHOR-Train-100-02 8.51
   wrong_dir_gt90       n= 10 ref 3.715 default 3.715 best 3.078  worst flight fastmid-ProcTHOR-Train-100-02 8.51
   fast_start_gt1.5     n= 14 ref 2.022 default 2.022 best 1.899  worst flight fastmid-108294897_176710602-01 7.47
   slow_start_lt0.3     n=  7 ref 2.001 default 2.001 best 2.296  worst flight fastmid-106366104_174226329-02 5.67
   static_start         n= 68 ref 0.662 default 0.662 best 0.617  worst flight fast-106366104_174226329-00 7.99
   textureless_dark     n= 12 ref 3.530 default 3.530 best 3.237  worst flight fastmid-ProcTHOR-Train-100-02 8.51
   long_path_gt58m      n= 56 ref 1.319 default 1.319 best 1.180  worst flight fastmid-106366104_174226329-00 8.38
   high_yaw_top25       n= 36 ref 0.921 default 0.921 best 0.851  worst flight fastmid-ProcTHOR-Train-123-00 5.91
   clean_scene          n= 21 ref 1.240 default 1.240 best 1.109  worst flight fastmid-ProcTHOR-Train-151-00 7.73
   mid_ang_0_45         n= 48 ref 0.915 default 0.915 best 0.918  worst flight fastmid-106366104_174226329-00 8.38
   mid_ang_45_90        n= 16 ref 1.420 default 1.420 best 1.364  worst flight fastmid-ProcTHOR-Train-151-00 7.73
   mid_ang_90_135       n=  6 ref 3.331 default 3.331 best 2.694  worst flight fastmid-ProcTHOR-Train-100-02 8.51
   mid_ang_135_180      n=  4 ref 4.292 default 4.292 best 3.654  worst flight fastmid-ProcTHOR-Train-123-00 5.91
== FRESH-A (475 unselected flights, tuning confirmation)
   3bf122401656 mean 0.834 static 0.599 mid 1.076 >3/5/10 24/14/1 ang135-180 1.33
```
