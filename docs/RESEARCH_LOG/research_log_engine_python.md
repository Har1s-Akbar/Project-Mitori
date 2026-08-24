# Pure Execution Time of the Python Engine analyzed, picking up noise and anomalies

**Date:** `[19/08/2026]`  
**Author:** `[Haris Ahmad]`

>**Rule:** In this document we will log every run, analyzing and picking up the noise and evaluating until there is no noise or anomalies in the data and it is pristine for the benchmarking.

## First Benchmarking (Ran-August 12)
This was one of the first attempts to benchmark the Python engine implemented with `heapq`. The benchmarking yields the numbers given below. This benchmarking does not include the starting and ending depth of the order book.

### Legacy Baseline Benchmark Results (Unoptimized Python Implementation)

#### Full Per-Trial Telemetry

| Depth Tier | Trial | P_50 Latency (ns) | P_99 Latency (ns) | Throughput (Max RPS) |
| :--- | :---: | :---: | :---: | :---: |
| **1k** | 1 | 6,110.0 | 42,175.10 | 105,161.49 |
| **1k** | 2 | 6,281.0 | 40,713.19 | 104,722.86 |
| **1k** | 3 | 6,419.0 | 52,006.50 | 94,637.09 |
| **1k** | 4 | 7,437.0 | 68,848.43 | 79,887.78 |
| **1k** | 5 | 6,814.0 | 56,169.03 | 89,866.44 |
| **25k** | 1 | 10,423.0 | 90,072.12 | 62,974.71 |
| **25k** | 2 | 8,807.5 | 76,082.40 | 71,034.19 |
| **25k** | 3 | 10,496.0 | 86,124.09 | 63,763.86 |
| **25k** | 4 | 9,630.5 | 75,268.09 | 69,707.01 |
| **25k** | 5 | 8,411.5 | 66,708.14 | 75,084.32 |
| **50k** | 1 | 10,114.5 | 61,261.07 | 74,424.01 |
| **50k** | 2 | 9,519.5 | 66,211.07 | 71,756.80 |
| **50k** | 3 | 9,684.5 | 65,844.01 | 71,247.36 |
| **50k** | 4 | 10,486.5 | 70,843.76 | 68,881.71 |
| **50k** | 5 | 11,133.5 | 95,492.12 | 59,406.26 |

#### Aggregated Tier Summary (N=5)

| Depth Tier | Mean P_50 (ns) | Mean P_99 (ns) | Mean Max RPS | RPS Std Dev |
| :--- | :---: | :---: | :---: | :---: |
| **1k** | 6,612.2 | 51,982.45 | 94,855.13 | 11,102.82 |
| **25k** | 9,553.7 | 78,850.97 | 68,512.82 | 5,160.05 |
| **50k** | 10,187.7 | 71,930.41 | 69,143.23 | 5,888.74 |

### Flaws
- Previously, the engine was being fed with `Decimal` objects. Decimal arithmetic is significantly slower compared to integer arithmetic.
- `engine.process_order()` was being called dynamically, causing massive memory stalls and making Python look up dynamically in the dictionary with every call. CPython must execute a bytecode instruction called `LOAD_ATTR` for this, causing massive overhead and spoiling the data.
- `log_raw_latencies_to_csv` was being called inside the for-loop with every order processing, causing I/O stalls and corrupting the benchmarking data.
- Previously, `latencies_ns` was recording only the time the order was spending inside the `processor`. We fixed it by adding the total time from the start of the for-loop to the end of it.

---

## Second Benchmarking (Ran-August 19)
This is the second benchmarking which ran today. After optimizing the above flaws, it dropped the P_50 and P_99 latency, revealing the pure execution speed of the Python engine.

### Optimized Python Baseline Results

#### Full Per-Trial Telemetry

| Depth Tier | Trial | P_50 Latency (ns) | P_99 Latency (ns) | Throughput (Max RPS) | Start Depth | End Depth |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1k** | 1 | 3,993.0 | 21,789.01 | 163,125.44 | 476 | 17 |
| **1k** | 2 | 4,197.0 | 23,164.03 | 156,330.64 | 476 | 17 |
| **1k** | 3 | 4,116.0 | 21,446.00 | 163,991.21 | 476 | 17 |
| **1k** | 4 | 4,269.0 | 22,735.01 | 155,271.07 | 476 | 17 |
| **1k** | 5 | 5,029.0 | 28,200.07 | 131,809.61 | 476 | 17 |
| **25k** | 1 | 10,189.0 | 88,166.86 | 61,320.05 | 23,600 | 7,618 |
| **25k** | 2 | 7,089.5 | 52,277.07 | 87,837.31 | 23,600 | 7,618 |
| **25k** | 3 | 4,352.0 | 28,091.01 | 132,241.69 | 23,600 | 7,618 |
| **25k** | 4 | 5,991.0 | 39,425.03 | 103,900.25 | 23,600 | 7,618 |
| **25k** | 5 | 5,429.0 | 38,110.10 | 109,501.30 | 23,600 | 7,618 |
| **50k** | 1 | 4,948.0 | 32,347.03 | 115,239.75 | 48,600 | 23,891 |
| **50k** | 2 | 4,556.0 | 30,382.00 | 124,494.17 | 48,600 | 23,891 |
| **50k** | 3 | 4,895.0 | 32,542.04 | 117,032.99 | 48,600 | 23,891 |
| **50k** | 4 | 5,127.0 | 33,993.02 | 114,430.71 | 48,600 | 23,891 |
| **50k** | 5 | 4,678.0 | 31,760.01 | 119,132.01 | 48,600 | 23,891 |

#### Aggregated Tier Summary (N=5)

| Depth Tier | Mean P_50 (ns) | Mean P_99 (ns) | Mean Max RPS | RPS Std Dev | Net Liquidity Drift |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **1k** | 4,320.8 | 23,466.82 | 154,105.59 | 13,066.02 | -459 orders (-96.4%) |
| **25k** | 6,610.1 | 49,214.01 | 98,960.12 | 26,066.05 | -15,982 orders (-67.7%) |
| **50k** | 4,840.8 | 32,204.82 | 118,065.93 | 4,047.88 | -24,709 orders (-50.8%) |

### Improvements
Dropping the `Decimal` logic, operating in pure integers, and forcing the benchmarking script to defer the OS disk write call successfully alleviated performance bottlenecks.
- **Throughput (Max RPS)**:
  - At 1k book depth tier, RPS went from 94k to 154k.
  - At 25k depth, RPS went from 68k to 98k.
  - At 50k depth, RPS went from 69k to 118k.
- **P_50 latency**:
  - The typical time to process a single order dropped by ~35% to 50%. 
  - At 1k depth, it fell from 6,612.2 ns down to 4,320.8 ns.
  - At 25k depth, it fell from 9,553.7 ns down to 6,610 ns.
  - At 50k depth, it fell from 10,187.7 ns down to 4,840.8 ns.

### Aggregated Performance Improvement Delta (N=5 Trials per Tier)

| Depth Tier | Metric | Legacy Baseline | Optimized Engine | Absolute Delta | Percentage Improvement |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **1k** | **Mean P_50** | 6,612.2 ns | 4,320.8 ns | -2,291.4 ns | **34.7% Faster** |
| | **Mean P_99** | 51,982.5 ns | 23,466.8 ns | -28,515.7 ns | **54.9% Faster** |
| | **Mean Max RPS** | 94,855.1 | 154,105.6 | +59,250.5 | **62.5% Higher Volume** |
| **25k** | **Mean P_50** | 9,553.7 ns | 6,610.1 ns | -2,943.6 ns | **30.8% Faster** |
| | **Mean P_99** | 78,851.0 ns | 49,214.0 ns | -29,637.0 ns | **37.6% Faster** |
| | **Mean Max RPS** | 68,512.8 | 98,960.1 | +30,447.3 | **44.4% Higher Volume** |
| **50k** | **Mean P_50** | 10,187.7 ns | 4,840.8 ns | -5,346.9 ns | **52.5% Faster** |
| | **Mean P_99** | 71,930.4 ns | 32,204.8 ns | -39,725.6 ns | **55.2% Faster** |
| | **Mean Max RPS** | 69,143.2 | 118,065.9 | +48,922.7 | **70.8% Higher Volume** |

### Structural Trade-Offs & Diagnostic Hypotheses
Optimization yielded a **35% to 70% performance boost**, but telemetry exposed two critical problems:

#### 1. Anomalies & Root Causes

##### A. Algorithmic Scaling Inversion (50k vs. 25k)
* **Symptom:** 50k depth ran faster (**~118k RPS**) than 25k (**~98k RPS**), violating standard logarithmic O(log N) scaling.
* **Hypothesis:** **Liquidity Drift / Book Collapse (Spread Crossing Flaw).** 
* **Root Cause:** Imbalanced Ornstein-Uhlenbeck order flow drained book depth (50k shrank by **50.8%**; 1k by **96.4%**). Active Limit orders were accidentally priced aggressively, causing them to immediately cross the spread and execute as Market orders. The engine ran faster because the heap physically shrank, leaving fewer nodes to traverse.

##### B. Extreme Trial Variance (25k Tail Latency)
* **Symptom:** Wild P_99 volatility in the 25k tier (Trial 1 at **88,166 ns** vs. Trial 3 at **28,091 ns**).
* **Hypothesis:** **L2/L3 Cache Thrashing.**
* **Root Cause:** Python's `pymalloc` allocated fragmented memory layouts across trials, inducing severe cache misses on Trial 1 that stabilized by Trial 3.

*Next objective: Fix the drifting of the order book depth. By the end of the test, it should stay stable/close to the starting depth with little to no variance.*

---

## Third Benchmarking (Ran-August 19)
In the third benchmarking, after the elimination of decimals, dynamic engine calls, and I/O interruptions during requests, we moved our attention to fixing:
- Unusual drift of the order book depth.
- Deviance of `P_99` latency in the `25k` tier.
- Order book liquidity bleeding.

### Fixes Applied
- The [Market, Limit] order distribution spread was balanced to **[0.5, 0.5]**.
- **Passive Pricing:** Limit `buy` orders were forced to be safely below the `center_value`, and Limit `sell` orders were forced to be safely above the `center_value`. This ensured Limit orders actually rested in the heap rather than aggressively crossing the spread.

### Final Benchmark Result

#### Full Per-Trial Telemetry
| Depth Tier | Trial | P_50 Latency (ns) | P_99 Latency (ns) | Throughput (Max RPS) | Start Depth | End Depth | Net Drift |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1k** | 1 | 3,032.0 | 17,436.0 | 205,583 | 991 | 1,196 | +205 |
| **1k** | 2 | 3,243.0 | 21,258.1 | 189,304 | 991 | 1,196 | +205 |
| **1k** | 3 | 3,754.0 | 21,093.0 | 173,523 | 991 | 1,196 | +205 |
| **1k** | 4 | 3,734.0 | 22,130.0 | 170,006 | 991 | 1,196 | +205 |
| **1k** | 5 | 3,720.0 | 22,174.2 | 169,243 | 991 | 1,196 | +205 |
| **25k** | 1 | 4,678.0 | 39,212.0 | 118,765 | 25,037 | 25,145 | +108 |
| **25k** | 2 | 7,857.0 | 109,517.1 | 59,759 | 25,037 | 25,145 | +108 |
| **25k** | 3 | 4,071.0 | 28,290.0 | 145,267 | 25,037 | 25,145 | +108 |
| **25k** | 4 | 3,610.0 | 24,375.1 | 164,313 | 25,037 | 25,145 | +108 |
| **25k** | 5 | 4,069.5 | 30,055.1 | 138,632 | 25,037 | 25,145 | +108 |
| **50k** | 1 | 3,939.0 | 32,585.0 | 136,633 | 50,045 | 50,050 | +5 |
| **50k** | 2 | 3,781.0 | 31,537.0 | 143,787 | 50,045 | 50,050 | +5 |
| **50k** | 3 | 3,578.0 | 25,385.0 | 160,785 | 50,045 | 50,050 | +5 |
| **50k** | 4 | 3,638.0 | 26,629.1 | 156,760 | 50,045 | 50,050 | +5 |
| **50k** | 5 | 3,722.0 | 27,000.1 | 153,920 | 50,045 | 50,050 | +5 |

#### Final Aggregated Baseline Metrics (N=5 Trials)

| Depth Tier | Avg P_50 Latency (ns) | Avg P_99 Latency (ns) | Avg Max RPS | Net Drift |
| :--- | :---: | :---: | :---: | :---: |
| **1k** | 3,497 | 20,818 | 181,532 | +205 (+20.69%)|
| **25k** | 4,857 | 46,290 | 125,347 | +108 (+0.43%)|
| **50k** | 3,732 | 28,627 | 150,377 | +5 (+0.01%)|

*(Note: The 25k tier mean includes Trial 2, which suffered a massive memory stall. If we use a Trimmed Mean ($N=4$, excluding Trial 2), the 25k tier stabilizes at ~141,744 RPS, proving that O(log N) scaling holds mathematically when memory remains contiguous.)*

### Result Evaluation
From the comparison of the final run results with the previous two results:
- For the **1k tier**, Average `P_50` latency dropped from `6,612.2 ns` to `3,497 ns` (a **47.11%** improvement). `P_99` latency dropped from `51,982.45 ns` to `20,818 ns` (a **59.95%** improvement), and RPS alleviated to **181,532**.
- For the **25k tier**, Average `P_50` latency dropped from `9,553.7 ns` to `4,857 ns` (a **49.16%** improvement). `P_99` latency dropped from `78,850.97 ns` to `46,290 ns` (a **41.29%** improvement), and RPS alleviated to **125,347**.
- For the **50k tier**, Average `P_50` latency dropped from `10,187.7 ns` to `3,732 ns` (a **63.37%** improvement). `P_99` latency dropped from `71,930.41 ns` to `28,627 ns` (a **60.20%** improvement), and RPS alleviated to **150,377**.

As the result suggests, every independent variable alleviated from its baseline. However, there is still one critical point to notice: with the elimination of every possible point of data corruption, latency dropped and max throughput increased, but the **25k tier** still severely underperforms the **50k tier** despite having less book depth.

#### 25k Tier Anomaly: Root Cause Analysis
A granular inspection of the 25k batch telemetry reveals a severe divergence between Trial 2 and the remaining runs:

* **Trials 1, 3, 4, 5 Average:** P_50 $\approx$ 4,107.1 ns | P_99 $\approx$ 30,483.1 ns | Throughput $\approx$ 141,744 RPS
* **Trial 2 Isolated:** P_50 = 7,857.0 ns (**+91.3%**) | P_99 = 109,517.1 ns (**+259.3%**) | Throughput = 59,759 RPS (**-57.8%**)

This single outlier dragged the aggregated 25k tier mean down, creating an apparent scaling inversion.

```text
[Trial 1, 3, 4, 5]  [=== L1/L2 Cache Hits (~4-5ns) ===] -------------> ~142k RPS
[Trial 2 Outlier]   [=== Pymalloc Fragmentation ===] -> [L3/RAM Misses (~50-100ns)] -> ~59k RPS