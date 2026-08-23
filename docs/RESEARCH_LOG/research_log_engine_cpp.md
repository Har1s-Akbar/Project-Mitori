# Pure Execution Time of the CPP Engine analyzed

**Date:** `[23/08/2026]`  
**Author:** `[Haris Ahmad]`

>**Rule:** In this document we will log every run, analyzing and picking up the noise and evaluating until there is no noise or anomalies in the data and it is pristine for the benchmarking.

## First Benchmarking (Ran-August 22)
Benchmarking ran on 22nd of August required a lot of preparation
- **CPP Benchmarking Script**
- **Introduction of `benchmark_batch` in bindings.cpp**

### CPP Benchmarking Script
When writing the benchmarking script and the benchmark_batch method in the bindings.cpp , There was an arhcitectural decision which was 
- if the benchmarking order and warmup orders be sliced up and fed to the binding separately 
- if the whole active stream orders were passed to the benchmark_batch and it slices the orders on it's own and warmup the cpp engine , run the allocateArena to secure the 10k ram memory block..
For the purpose of minimizing the role of python in the benchmarking and staying clear of Python Global Interpreter , second is implemented.

python script splits the original order_owner_id UUID 128 bit into two uint64_t order_owner_id_high and order_owner_id_low each of 64 bit , it also scales the decimal type number_of_shares and price into 10^8 uint64_t int, and also casts the python enums into cpp enums using if else.

### Benchmark_batch
In the benchmark_batch , cpp library `chrono` is implemented which issues a system call and directly reads from hardware `CPU TSC` calculating the latency of the orders being matched in real time saving them in latencies <uint64_t> vector and returning the vector at the end of the benchmarking of each trial.


# Project Mitori: C++ Engine Benchmark Results

## 📊 Raw Benchmark Telemetry

| Depth Tier | Trial | P50 Latency (ns) | P99 Latency (ns) | Max RPS | Start Depth | End Depth | Order Drift |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1k** | 1 | 89.0 | 514.0 | 890,192.34 | 1000 | 1196 | +196 |
| **1k** | 2 | 89.0 | 507.0 | 815,378.10 | 1000 | 1196 | +196 |
| **1k** | 3 | 90.0 | 690.0 | 770,867.53 | 1000 | 1196 | +196 |
| **1k** | 4 | 89.0 | 518.0 | 903,819.52 | 1000 | 1196 | +196 |
| **1k** | 5 | 92.0 | 584.0 | 947,714.97 | 1000 | 1196 | +196 |
| **25k** | 1 | 100.0 | 1,415.0 | 938,847.93 | 25000 | 25145 | +145 |
| **25k** | 2 | 97.0 | 1,762.0 | 785,443.06 | 25000 | 25145 | +145 |
| **25k** | 3 | 99.0 | 1,571.0 | 815,765.02 | 25000 | 25145 | +145 |
| **25k** | 4 | 94.0 | 1,277.0 | 961,167.62 | 25000 | 25145 | +145 |
| **25k** | 5 | 131.0 | 1,719.0 | 808,900.89 | 25000 | 25145 | +145 |
| **50k** | 1 | 128.0 | 4,409.0 | 584,879.63 | 50000 | 50050 | +50 |
| **50k** | 2 | 106.0 | 2,826.0 | 658,647.43 | 50000 | 50050 | +50 |
| **50k** | 3 | 131.0 | 2,978.0 | 567,317.83 | 50000 | 50050 | +50 |
| **50k** | 4 | 109.0 | 2,158.0 | 587,764.84 | 50000 | 50050 | +50 |
| **50k** | 5 | 138.0 | 3,641.0 | 616,851.14 | 50000 | 50050 | +50 |

---

## Aggregated Tier Summary (N=5 Trials)

| Depth Tier | mean P50 (ns) | mean P99 (ns) | mean Max RPS | Net Liquidity Drift |
| :--- | :--- | :--- | :--- | :--- |
| **1k** | 89.8 | 562.6 | 865,594.49 | +196 (+19.6 %)|
| **25k** | 104.2 | 1,548.8 | 862,024.90 | +145 (+0.58 %) |
| **50k** | 122.4 | 3,202.4 | 603,092.17 | +50 (+0.1 %) |

### Result Evaluation
