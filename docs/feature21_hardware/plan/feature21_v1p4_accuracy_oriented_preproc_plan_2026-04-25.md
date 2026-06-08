# Feature21 v1.4 Accuracy-Oriented Hardware Preprocessor Plan

Date: 2026-04-25

## Background

Feature21 v1.3 has closed the board-level functional chain on Nexys Video:

```text
DMA MM2S -> Feature21 fixed-point preprocessor -> QMLP -> DMA S2MM
```

The current bitstream under test is:

```text
/home/soooarr/chipyard/fpga/deliverables/radar_nexysvideo_bits/646-feature21-v1p3-preproc-qmlp-2026-04-22.bit
```

The v1.3 board test passed against its own fixed-point approximation reference. A software-golden characterization test was then added and run against the original Feature21 software golden subset.

Current software-golden subset result:

```text
samples              = 16
total points         = 230
feature bytes        = 336
matched bytes        = 247
mismatched bytes     = 89
feature match rate   = 73.5%
exact sample matches = 0/16
mean abs int8 error  = 1.181
max abs int8 error   = 73
cycles avg/min/max   = 404 / 356 / 690
```

Related logs:

```text
logs/radar_nexysvideo/runtime/653-feature21-golden-subset-board-test-2026-04-25-2026-04-25-172617.log
logs/radar_nexysvideo/runtime/654-feature21-golden-subset-summary-2026-04-25.md
```

The result shows that the current hardware preprocessor is fast enough for the present chain, but its approximation quality should be improved before it is presented as a stronger Feature21 hardware implementation.

## Goal

The next iteration should move from a minimal runnable approximation to a timing-aware accuracy-oriented approximation.

Proposed v1.4 targets:

```text
feature-level match rate >= 85%
mean abs int8 error      <= 0.8
maintain 50 MHz timing closure
keep preproc latency small relative to the board-level DMA/software overhead
preserve the existing AXI-Stream protocol and QMLP chain integration
```

The v1.4 goal is not to blindly copy the floating-point software implementation into RTL. Previous attempts at direct implementation were risky for timing. The preferred direction is a hardware-native approximation architecture with explicit error characterization.

## Stage 1: Per-Feature Error Attribution

Before changing RTL, add an offline breakdown that reports error by feature index.

Required metrics:

```text
per-feature match rate
per-feature mean absolute error
per-feature maximum absolute error
top mismatch samples
overall vector exact match rate
```

This should identify which features dominate the mismatch. The likely high-impact features are:

```text
f3  std_x
f4  std_y
f10 azimuth_span
f11 eig_major
f12 eig_minor
f13 density_2d
f15 doppler_std
f19 rcs_std
```

Expected output:

```text
tools/feature21_hw_approx_eval.py
logs/radar_nexysvideo/runtime/655-feature21-v1p4-error-breakdown-2026-04-25.md
```

## Stage 2: Hardware Approximation Mirror

Create a software mirror of the hardware approximation before changing Chisel. This mirror should be bit-consistent with the intended RTL behavior.

Purpose:

```text
software Feature21 golden
vs
hardware-approx Feature21 mirror
```

The mirror allows full 1000-sample evaluation before synthesis and bitstream generation. A change should only be moved into RTL after it improves the software-golden metrics enough to justify the extra hardware cost.

Suggested files:

```text
tools/feature21_hw_approx_eval.py
tests/feature21_hw_approx_reference.h
```

The mirror should model:

```text
Q8.8 input conversion
fixed-point accumulation
mean approximation
range approximation
std approximation
density approximation
feature quantization
int8 clamp and rounding behavior
```

## Stage 3: Low-Risk High-Impact RTL Improvements

### 1. Mean Division via Reciprocal LUT

Current v1.3 uses bucketed shifts in `meanApproxQ8p8`. For example, counts from 9 to 16 are divided by 16, which systematically biases the mean toward zero.

Proposed v1.4:

```text
mean = round(sum * recip[count] >> shift)
count = 1..511
```

Implementation options:

```text
small reciprocal LUT
multi-cycle constant multiply
one shared multiplier reused by mean_x, mean_y, mean_doppler, mean_rcs
```

Expected impact:

```text
f1  mean_x
f2  mean_y
f9  centroid_range
f14 doppler_mean
f18 rcs_mean
```

Risk: low to medium. The computation can be multi-cycle and fully registered.

### 2. Improved Range Approximation

Current v1.3 range approximation:

```text
range ~= max(abs(x), abs(y)) + min(abs(x), abs(y)) / 2
```

Possible v1.4 replacement:

```text
range ~= max(abs(x), abs(y)) + 3/8 * min(abs(x), abs(y))
```

or a small piecewise approximation:

```text
if min/max < 1/4:
  range ~= max + min/4
else:
  range ~= max + min/2 - max/16
```

Expected impact:

```text
f7 range_min
f8 range_max
f9 centroid_range
```

Risk: low. This can be implemented with shifts and adds, without a full sqrt.

### 3. Density Approximation

Current v1.3 uses point count as a proxy for `density_2d`.

Software formula:

```text
density_2d = N / max(span_x * span_y, eps)
```

Proposed v1.4:

```text
area = span_x * span_y
density_q = clamp(round(N * scale / area))
```

The division does not need to be exact. A leading-one based reciprocal LUT or coarse bucketed reciprocal should be enough for a better match than the current count proxy.

Expected impact:

```text
f13 density_2d
```

Risk: medium. Area multiplication and reciprocal approximation must be pipelined.

## Stage 4: Medium-Risk Accuracy Improvements

### 1. Variance-Lite Standard Deviation

Current v1.3 std approximation:

```text
std ~= span / 4
```

Proposed v1.4 or v1.5:

```text
sum_x2 += x * x
sum_y2 += y * y
sum_d2 += doppler * doppler
sum_r2 += rcs * rcs

var = mean(x^2) - mean(x)^2
std ~= sqrt_approx(var)
```

The sqrt can use a leading-one or piecewise approximation instead of an iterative exact sqrt.

Expected impact:

```text
f3  std_x
f4  std_y
f15 doppler_std
f19 rcs_std
```

Risk: medium to high. This adds per-point square accumulation and additional finalization states. Because the preprocessor is not currently the chain bottleneck, a multi-cycle finalization stage is acceptable.

### 2. Variance-Based Eigen Proxy

Avoid exact covariance eigenvalue hardware in the first accuracy-oriented version.

Instead, after variance-lite is available:

```text
eig_major_proxy = max(std_x, std_y)
eig_minor_proxy = min(std_x, std_y)
```

This is still an approximation, but should be better than span-based std proxies.

Expected impact:

```text
f11 eig_major
f12 eig_minor
```

Risk: low after variance-lite exists.

## Stage 5: High-Risk Features to Defer

The following should not be implemented exactly in the first v1.4 RTL pass:

```text
f10 azimuth_span exact atan2
f11/f12 exact covariance eigenvalues
exact floating-point-compatible sqrt and division
```

Possible future proxies:

```text
azimuth_span ~= span_y / max(abs(mean_x), eps), with saturation
eig terms    ~= variance-based major/minor proxy
range terms  ~= piecewise shift-add sqrt approximation
```

These proxies should only be accepted after software mirror evaluation shows useful improvement.

## RTL Architecture Direction

Keep the existing streaming protocol and add a multi-cycle finalization pipeline.

Current shape:

```text
sIdle
sAccum
sMeanX
sMeanY
sMeanDoppler
sMeanRcs
sFeatureSelect
sFeatureQuant
sEmit
```

Proposed v1.4 shape:

```text
sIdle
sAccum
sMeanX
sMeanY
sMeanDoppler
sMeanRcs
sRangeFinalize
sDensity
sFeatureSelect
sFeatureQuant
sEmit
```

If variance-lite is included:

```text
sStdX
sStdY
sStdDoppler
sStdRcs
sEigProxy
```

Design principles:

```text
keep one AXI beat per input point
register every complex approximation result
avoid large combinational mux plus quantization in the same cycle
reuse one multiplier or approximation unit across finalization states
prefer multi-cycle post-accumulation over timing-heavy single-cycle logic
preserve the 4-beat 32-byte output format
```

## Verification Plan

Each v1.4 candidate should go through four levels of validation:

```text
1. Software mirror evaluation on the full 1000-sample golden dataset
2. Chisel elaboration / Verilog generation
3. Bare-metal RTL reference test against the hardware mirror
4. Nexys Video board test against software golden subset and then larger subsets
```

Required metrics:

```text
feature-level match rate
vector exact match rate
mean absolute int8 error
maximum absolute int8 error
per-feature error table
preproc transaction cycles
Feature21 -> QMLP chain cycles
QMLP logits stability
```

Board-side tests should retain:

```text
/dev/ttyUSB0
baudrate 115200
uart_tsi +selfcheck
```

## Proposed Iteration Order

### v1.4a

Implement only the safest high-impact improvements:

```text
1. reciprocal-LUT mean
2. improved range approximation
3. density reciprocal approximation
```

Expected target:

```text
feature-level match rate: 73.5% -> about 80-85%
mean abs error: noticeable reduction
timing risk: controlled
```

### v1.4b or v1.5

Add the more expensive statistics:

```text
1. sum-of-squares accumulation
2. variance-lite std approximation
3. variance-based eig proxy
```

Expected target:

```text
feature-level match rate: >= 85%, possibly closer to 90%
better alignment on std and eig-related features
```

## Thesis Framing

The recommended thesis framing is:

```text
1. The board-level experiment shows that preprocessor latency is not the current system bottleneck.
2. A direct software-equivalent hardware implementation is timing-risky on the target FPGA.
3. A hardware-native fixed-point approximate Feature21 preprocessor is designed instead.
4. The design is evaluated by comparing against software golden outputs.
5. Approximation error is reported per feature and end-to-end through the QMLP chain.
6. The final architecture balances accuracy, timing closure, resource use, and board-level throughput.
```

This is stronger than claiming exact software equivalence when the RTL intentionally uses hardware-friendly approximations.

## Immediate Next Step

Start with the per-feature error breakdown and software approximation mirror. Do not change RTL until the mirror shows which approximation changes provide the best accuracy gain per hardware cost.
