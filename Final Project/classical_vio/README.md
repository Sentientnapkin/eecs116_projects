# Classical VIO

| Source directory | WebAssembly filename | Public mean Sim(3) ATE | Peak fuel per frame |
| --- | --- | ---: | ---: |
| `klt_imu/` | `116_traditional_combination_stage6.wasm` | 1.713 m | 132.47M |
| `imu_avg5/` | `imu_avg5.wasm` | 2.147 m | 1.441M |
| `imu_weighted_avg10/` | `116_dead_reckoning_stage10.wasm` | 2.153 m | 1.632M |

The KLT directory contains the uploaded Stage 6 estimator. It uses gyro-aided
keyframe tracking to estimate a signed translation direction and keeps the
distance predicted by the IMU. The two IMU-only estimators use the same
dead-reckoning update with different inputs to that update. The table reports
the original ten-episode public benchmarks. Earlier experiments and their
benchmark notes are in Git history at `a0d6eb0`.

## Dead reckoning equations

The [LaTeX subsection](imu_avg5_derivation.tex) gives the full derivation
for the latest-five estimator.

Let $p$ and $v$ be the IMU position and velocity in world coordinates, and
let $R$ map vectors from IMU axes into world axes. Let $T$ be the time
between images, typically 50 ms. Each image packet contains accelerometer
specific force $f_i$ and gyro angular rate $\omega_i$, in IMU axes.

**Latest-five average.** For a regular ten-sample packet, the input to one
propagation is the equal-weight mean of samples 6 through 10.

$$
\bar f = \frac{1}{5}\sum_{i=6}^{10} f_i,
\qquad
\bar\omega = \frac{1}{5}\sum_{i=6}^{10}\omega_i .
$$

**Timestamp-weighted average.** For the full packet, let $w_i$ be the
elapsed time from the preceding timestamp to sample $i$. Use the previous
image timestamp for the first interval. If the last sample precedes the
current image, add the remaining time to its weight. For a packet of $n$
samples with timestamps $s_i$ clipped to the image interval
$[t_{\mathrm{prev}}, t_{\mathrm{now}}]$, set $s_0=t_{\mathrm{prev}}$.

$$
w_i = s_i - s_{i-1}\quad (i<n),
\qquad
w_n = t_{\mathrm{now}} - s_{n-1},
\qquad
T = \sum_{i=1}^{n} w_i .
$$

$$
\bar f = \frac{1}{T}\sum_i w_i f_i,
\qquad
\bar\omega = \frac{1}{T}\sum_i w_i\omega_i .
$$

Both variants apply the resulting pair over the **full** image interval. The
gyro average gives the midpoint and end orientations. Here $[x]_\times$
is the skew-symmetric matrix for the cross product with $x$.

$$
\begin{aligned}
R_{\mathrm{mid}} &= R\exp\!\left(\tfrac{T}{2}[\bar\omega]_\times\right),\\
R^+ &= R\exp\!\left(T[\bar\omega]_\times\right),\\
a &= R_{\mathrm{mid}}\bar f + g,\\
p^+ &= p + vT + \tfrac{1}{2}aT^2,\\
v^+ &= v + aT.
\end{aligned}
$$

At startup, $R=I$ and $p=v=0$. The code estimates gravity from the mean
specific force $f_0$ in the first packet, assuming low acceleration,
so $g=-9.81 f_0/\lVert f_0\rVert$ when that mean is usable.

The camera position is $p_C=p+Rr$, where $r$ is the camera center
expressed in IMU axes. With $R_{CI}$ mapping IMU vectors into camera axes
and $\omega_{\mathrm{last}}$ from the latest gyro sample, the reported
camera linear and angular velocities are

$$
v_C = R_{CI}\bigl(R^\top v + \omega_{\mathrm{last}}\times r\bigr),
\qquad
\omega_C = R_{CI}\omega_{\mathrm{last}} .
$$

The reported pose is relative to the first camera pose.

## Build and check

From this directory, use VIOBench and its Python runtime. The original builds
used VIOBench revision `2072fa9b5b4a5eb34160a53f5789a9c4a9d220ca`.
If you need a runtime, run these commands after installing the sibling
VIOBench checkout. Its compiler requires a build path without spaces.

```sh
work=$(mktemp -d /tmp/classical-vio.XXXXXX)
viobench init python "$work"
viobench build-runtime "$work"
mkdir -p build
cp "$work/build/runtime/dist/runtime.wasm" build/runtime.wasm
```

```sh
runtime="$PWD/build/runtime.wasm"
viobench bundle klt_imu --runtime "$runtime" -o build/116_traditional_combination_stage6.wasm
viobench bundle imu_avg5 --runtime "$runtime" -o build/imu_avg5.wasm
viobench bundle imu_weighted_avg10 --runtime "$runtime" -o build/116_dead_reckoning_stage10.wasm
viobench check build/116_traditional_combination_stage6.wasm
viobench check build/imu_avg5.wasm
viobench check build/116_dead_reckoning_stage10.wasm
```
