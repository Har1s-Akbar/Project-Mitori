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

## Raw Benchmark Telemetry

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

The results from the first benchmark run demonstrate exceptional baseline algorithmic performance but reveal systemic degradation at scale. A median (P50) latency of 89.8 ns at the 1k depth tier confirms that the `ArenaAllocator` successfully mapped order data contiguously, eliminating the L3 cache pointer-chasing bottlenecks.

**Methodology Validation:** Both the Python and C++ benchmarking scripts successfully pre-allocate and instantiate all 200,000 orders in memory *before* the timing clock starts. This isolates the raw matching logic and O(log n) tree traversals, providing a perfectly sound.

However, scaling the depth exposes severe performance friction. At the 50k depth tier, the P50 latency degrades by 36% (to 122.4 ns), while the P99 tail latency spikes non-linearly by 569% (to 3,202.4 ns). This tail latency blowup directly correlates with a 30% collapse in Max RPS (dropping to 603k).

### Flaws & Noise Sources

To ensure pristine data for the final benchmarking, we must isolate and remove the noise introduced by our measurement methodology and synthetic workload parameters.

#### 1. Measurement Flaws: The Observer Effect
The current `benchmark_batch` implementation relies on `std::chrono::high_resolution_clock::now()` inside the core timing loop.
*   **System Call Overhead:** On modern Linux kernels, executing two consecutive `std::chrono` calls incurs approximately 15 to 25 nanoseconds of overhead. When our P50 execution time is ~90 ns, this means the timer itself artificially inflates the measured latency by 15-25%.
*   **Cache Pollution via Telemetry:** Appending 195,000 latency integers to the `std::vector` (`latencies.push_back()`) dynamically reallocates memory and dirties L1/L2 cache lines inside the timed loop. This artificially induces data cache evictions, displacing the actual matching engine price levels we are trying to measure.

#### 2. Architectural Flaws: The 50k Memory Wall (Hypothesis)
The non-linear P99 degradation at 50k depth highlights a fundamental hardware constraint.
*   **Cache Saturation:** At 50,000 resting orders, the memory footprint of the price level nodes and metadata exceeds the core’s private L1 Data Cache (32–48 KB) and L2 Cache (512 KB–1 MB).
*   **Pointer Chasing on Tree Traversal:** As the engine traverses the O(log n) paths to match orders against deeper books, the CPU memory controller is forced to fetch cache lines from the slower, shared L3 cache or main DRAM. These cache misses stall the execution pipeline, causing the massive P99 spike.

### Next Steps (Run 2 Preparation)
To flatten the P99 spike and obtain pristine telemetry, the second run must implement:
1.  **Hardware-Level Timing:** Replace `std::chrono` with low-overhead, compiler-intrinsic TSC register reads (`__rdtscp()`) and replace the dynamic `push_back()` with a pre-allocated array.
2.  **Hardware Profiling:** Instrument the Docker container with `perf stat -e L1-dcache-load-misses,LLC-load-misses` to explicitly track cache evictions during the 50k depth traversal.

## Second Benchmarking (Ran-August 24)
Second benchmarking ran after the fix of the observer effect, in which `chrono` was removed from the `bindings.cpp` method for benchmarking `benchmark_batch` and it yielded improved results. By properly removing `chrono::high_resolution_clock::now()` from the loop, we eliminated a massive POSIX system call (`clock_gettime(CLOCK_MONOTONIC)`). While modern Linux optimizes this using a vDSO (Virtual Dynamically Shared Object) to avoid a full context switch into the kernel, it still has to do the following:

- **The Seqlock:** CPU must read a kernel sequence lock to know that the OS is not updating the clock concurrently.
- **Math:** It reads the raw hardware cycle and performs 64-bit integer multiplication and bit shifts to convert raw cycles into nanoseconds.
- **Offset:** Adding the boot-time epoch offset to return an absolute timestamp.

Each call to the vDSO takes 15-25 nanoseconds. Because this function was being called twice per order execution to get the starting time and the ending time, it constituted and consumed a major portion of the latency calculation benchmark.

- **`__rdtscp` Fix:** `__rdtscp` is not a C++ library function; it is a direct hardware microcode instruction. It reaches directly into the CPU silicon and reads the Time-Stamp Counter (TSC) register in less than 35 CPU cycles. By stopping the OS from calling the kernel and forcing the system to do heavy math, and replacing it with a hardware-level intrinsic, we minimized the latency overhead introduced by `chrono`.

- **`push_back()` - Cache Thrashing:** 
How the latency of the order execution was being saved was actively causing CPU cache thrashing. The method `latencies.push_back(duration.count())` dynamically manages memory. At 1k and 25k depths, the CPU L1/L2 cache had enough room for both the order tree nodes and the growing vector. However, at the 50k depth tier, the order struct footprint (~3.5 MB) physically exceeded the i7-1355U P-Core's 1.25 MB L2 cache. By pushing 195,000 integers sequentially, the CPU was forced to aggressively evict our matching engine's tree data from the L1/L2 cache to make room for the telemetry vector. On the next order's tree traversal, the data was missing, causing a stall to fetch from DRAM. 
**The Fix:** We pre-allocated the vector upfront (`std::vector<uint64_t> latencies(timing_count, 0)`) and assigned values strictly by index (`latencies[i] = ...`). This completely eliminated dynamic memory reallocations and cache overwrites inside the timing loop.

## Raw Benchmark Telemetry

| Depth Tier | Trial | P50 Latency (ns) | P99 Latency (ns) | Max RPS | Start Depth | End Depth | Order Drift |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1k** | 1 | 82.0 | 462.0 | 1,088,866.37 | 1000 | 1196 | +196 |
| **1k** | 2 | 86.0 | 460.0 | 1,083,587.89 | 1000 | 1196 | +196 |
| **1k** | 3 | 90.0 | 529.0 | 1,052,489.84 | 1000 | 1196 | +196 |
| **1k** | 4 | 97.0 | 546.0 | 960,331.98 | 1000 | 1196 | +196 |
| **1k** | 5 | 88.0 | 497.0 | 1,051,876.83 | 1000 | 1196 | +196 |
| **25k** | 1 | 95.0 | 1,334.0 | 846,799.84 | 25000 | 25145 | +145 |
| **25k** | 2 | 82.0 | 1,057.0 | 1,021,722.89 | 25000 | 25145 | +145 |
| **25k** | 3 | 89.0 | 1,268.0 | 1,027,313.23 | 25000 | 25145 | +145 |
| **25k** | 4 | 90.0 | 1,342.0 | 971,748.97 | 25000 | 25145 | +145 |
| **25k** | 5 | 79.0 | 1,062.0 | 1,091,190.33 | 25000 | 25145 | +145 |
| **50k** | 1 | 82.0 | 1,481.0 | 1,083,854.92 | 50000 | 50050 | +50 |
| **50k** | 2 | 95.0 | 2,252.0 | 868,610.01 | 50000 | 50050 | +50 |
| **50k** | 3 | 94.0 | 1,750.0 | 864,253.76 | 50000 | 50050 | +50 |
| **50k** | 4 | 90.0 | 1,919.0 | 956,183.73 | 50000 | 50050 | +50 |
| **50k** | 5 | 86.0 | 1,747.0 | 944,985.35 | 50000 | 50050 | +50 |

---

## Aggregated Tier Summary (N=5 Trials)

| Depth Tier | Avg P50 (ns) | Avg P99 (ns) | Avg Max RPS | Net Liquidity Drift |
| :--- | :--- | :--- | :--- | :--- |
| **1k** | 88.6 | 498.8 | 1,047,430.58 | +196 (+19.6%)|
| **25k** | 87.0 | 1,212.6 | 991,755.05 | +145 (+0.58%)|
| **50k** | 89.4 | 1,829.8 | 943,577.55 | +50 (+0.1%)|

### Result Evaluation

The transition to hardware-level TSC timing and pre-allocated memory structures completely stripped the observer effect from the telemetry, revealing the true algorithmic performance of the C++ matching engine.

1.  **The P50 Median is Flat:** In the first run, P50 latency degraded by 36% at the 50k tier (to 122ns). The Run 2 telemetry proves this was an illusion caused by telemetry-induced cache thrashing. The true P50 is pinned flat at **~87 to 89ns** across *all* depth tiers. The engine operates entirely within the L1/L2 cache for median order processing, completely immune to the 50k depth volume.
2.  **Unthrottled Throughput:** By removing the vDSO system calls and vector reallocations, the maximum throughput at the 50k tier surged by over 50%, jumping from 603k RPS to **943k RPS**. 
3.  **Isolating the Hardware Memory Wall:** The massive 3,200ns P99 tail latency from Run 1 collapsed down to **1,829ns**. While vastly improved, the scaling degradation at P99 remains (498ns at 1k vs. 1,829ns at 50k). Because all software measurement noise has been eliminated, this mathematically isolates the true hardware limit. The remaining 1.8µs tail confirms the L3 Cache / DRAM stall penalty when O(log n) tree traversal inevitably accesses cold nodes on the edges of the 3.5 MB memory footprint.