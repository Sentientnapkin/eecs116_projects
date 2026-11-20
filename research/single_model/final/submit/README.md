# gp_msckf + startup prior + movement gate (wasm)

`gp_msckf_startup_gate.wasm` — plain C (libc/libm only), VIOBench ABI v1, compiled with wasi-sdk 34 (clang 23.1.0). Source: `gate.c`.

SHA-256: `ac8251454f5cf9564a09b93ae37cf258442f4854b84fffbe2fad20d72582a9b6`

Local results on the 171 server-calibrated pool flights (mean unaligned ATE, m): all 0.976 (baseline gp_msckf 2.210), static starts 0.808, mid-flight starts 1.141.
Peak fuel 22.54 M per frame. These are local pool numbers, not server scores. Passed the ABI check, determinism, causality (prefix/future-poison), reset, no-filled-frames checks.

Contents: `gp_msckf_startup_gate.wasm`, `gate.c`, `SHA256SUMS`, this README.
