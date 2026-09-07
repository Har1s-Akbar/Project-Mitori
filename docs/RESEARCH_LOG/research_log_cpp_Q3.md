# Full API Request Latency Overhead Comparison of Python and C++ Engines

**Date:** `[06/09/2026]`  
**Author:** `[Haris Ahmad]`  
**Project:** `[Project Mitori]`  

> **Rule:** This document logs the Python and C++ full API path execution and latency comparison in a polyglot high-frequency trading (HFT) system.

Phase 1 and Phase 2 benchmarks have already established that the native C++ engine scales linearly up to 2 threads (before throughput compromises under mutex locking and context switching). Phase 2 also proved that the isolated execution speed of the C++ matching core is vastly superior to the Python core, maintaining a p50 latency of 79-90 ns and a p99 latency of 462-1750 ns.

## 1. Methodology
In this phase of the research, the objective expands to measure the full path execution of both architectures (`Python Engine` and `C++ Engine`) within a hybrid ASGI web pipeline. 

A Go-based k6 load generator fires a constant stream of [500, 2000, 5000] requests per second for a period of 30 seconds. At the end of each trial, results are aggregated into a summary matrix capturing three critical metrics:
*   `http_req_duration`: Client-side observed roundtrip latency—measured from k6 request transmission to complete HTTP 200 OK resolution after order matching.
*   `engine_latency_ns`: Pure core execution latency—measured strictly from the moment the order enters the internal limit order book logic until a match or resting state is returned.
*   `total_process_ns`: End-to-end server latency—measuring total time elapsed from the FastAPI `/order` route ingestion, through Redis risk validation, to final JSON response serialization.

### Expected Result
The pure microsecond execution speed and throughput exhibited by the C++ core in earlier research phases will be severely attenuated by the I/O processing overhead of Uvicorn and Redis. The hypothesis dictates that total path latency (`total_process_ns`) will converge for both the C++ and Python engines, heavily bounded by the web infrastructure.

---

## 2. Python Engine Benchmarking

This section evaluates the pure Python order matching core subjected to the hybrid REST API (FastAPI) and Redis pre-trade validation layer. 

### 2.1. Telemetry Data
| Engine | Target RPS | Metric | Unit | Min | Avg | Med (p50) | p90 | p95 | p99 | Max |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| PYTHON | 500 | `engine_latency_ns` | ns | 4,830.60 | 12,015.66 | **8,142.20** | 19,884.40 | 24,616.31 | 46,647.24 | 3,238,358.00 |
| PYTHON | 500 | `http_req_duration` | ms | 16.93 | 2,561.35 | **2,542.55** | 4,399.44 | 4,697.78 | 4,742.43 | 5,018.45 |
| PYTHON | 500 | `total_process_ns` | ns | 13,155,359.80 | 1,532,259,393.71 | **1,144,315,613.60** | 3,151,468,368.08 | 3,427,897,796.80 | 3,782,279,581.76 | 4,211,301,657.20 |
| PYTHON | 2000 | `engine_latency_ns` | ns | 4,632.20 | 10,903.97 | **7,579.00** | 16,691.00 | 22,553.31 | 39,393.26 | 2,405,675.40 |
| PYTHON | 2000 | `http_req_duration` | ms | 181.38 | 2,646.07 | **2,463.71** | 4,140.76 | 4,198.79 | 4,342.47 | 5,018.93 |
| PYTHON | 2000 | `total_process_ns` | ns | 163,363,514.00 | 1,891,297,816.85 | **1,637,663,558.70** | 3,103,581,715.56 | 3,283,933,229.07 | 3,633,229,672.90 | 4,600,598,689.80 |
| PYTHON | 5000 | `engine_latency_ns` | ns | 4,444.20 | 10,044.85 | **7,438.90** | 15,623.28 | 21,590.91 | 38,090.92 | 1,446,178.40 |
| PYTHON | 5000 | `http_req_duration` | ms | 388.21 | 2,638.48 | **2,547.23** | 4,172.69 | 4,439.82 | 4,605.49 | 5,005.82 |
| PYTHON | 5000 | `total_process_ns` | ns | 335,042,993.40 | 1,949,475,432.84 | **1,913,377,354.40** | 3,281,185,576.98 | 3,500,161,281.63 | 3,856,307,812.49 | 4,486,867,822.40 |

### 2.2. Isolated Core Analysis
The Python limit order book logic evaluates arriving orders, traverses price levels, and executes matches in **~7.43 to 8.14 µs**. Despite Python's interpreted nature, the core performs pure CPU-bound pointer manipulation on highly optimized C-level hash maps (dictionaries) without network I/O, avoiding GIL contention. Latency marginally decreases at 5000 RPS, reflecting localized memory access and CPU cache warming.

---

## 3. C++ Engine Benchmarking

This section evaluates the native C++ matching core connected to the Python/FastAPI architecture via Foreign Function Interface (FFI) bindings.

### 3.1. Telemetry Data
| Engine | Target RPS | Metric | Unit | Min | Avg | Med (p50) | p90 | p95 | p99 | Max |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CPP | 500 | `engine_latency_ns` | ns | 4,567.80 | 15,795.68 | **7,720.50** | 20,964.90 | 29,703.46 | 80,176.60 | 5,723,509.40 |
| CPP | 500 | `http_req_duration` | ms | 947.00 | 3,188.77 | **3,425.93** | 4,368.56 | 4,474.40 | 4,676.23 | 5,014.16 |
| CPP | 500 | `total_process_ns` | ns | 452,686,346.20 | 2,009,281,445.86 | **1,978,592,988.90** | 3,382,050,183.22 | 3,542,873,004.61 | 3,852,173,318.21 | 4,334,991,474.20 |
| CPP | 2000 | `engine_latency_ns` | ns | 4,375.80 | 19,008.54 | **7,254.20** | 21,075.74 | 28,579.00 | 86,788.15 | 10,795,128.20 |
| CPP | 2000 | `http_req_duration` | ms | 339.38 | 3,091.43 | **3,224.86** | 4,680.38 | 4,811.81 | 4,920.17 | 5,067.56 |
| CPP | 2000 | `total_process_ns` | ns | 308,406,325.00 | 2,092,150,933.58 | **1,889,179,957.20** | 3,515,403,325.88 | 3,762,232,552.67 | 4,036,126,578.07 | 4,469,718,332.20 |
| CPP | 5000 | `engine_latency_ns` | ns | 4,196.00 | 11,258.58 | **6,676.10** | 17,259.06 | 24,785.74 | 52,828.11 | 3,729,059.40 |
| CPP | 5000 | `http_req_duration` | ms | 550.58 | 2,670.40 | **2,610.10** | 4,052.17 | 4,166.19 | 4,428.29 | 5,007.96 |
| CPP | 5000 | `total_process_ns` | ns | 439,859,316.40 | 2,009,648,267.73 | **2,022,610,733.70** | 3,224,906,191.90 | 3,472,332,450.62 | 3,711,795,403.06 | 4,373,710,592.60 |

### 3.2. Isolated Core Analysis & FFI Overhead
The compiled C++ core resolves order placement deterministically in **~6.68 to 7.72 µs**. However, this latency deviates from the pure engine execution speeds captured in Phase 2. The `engine_latency_ns` recorded here is measured from within the `gateway-cpp` wrapper calling `bindings.cpp`. Therefore, this measurement inherently includes the cross-language data marshalling overhead (Python-to-C++ FFI conversion of UUIDs and scaled integers), accounting for the slight elevation and periodic tail latency jitter compared to the raw Phase 2 tests.

---

## 4. Shared Macro-System Bottlenecks (Language-Agnostic)

Comparing both tables reveals that despite the algorithmic variations between Python and C++, the surrounding web infrastructure creates insurmountable, language-agnostic bottlenecks that govern the system.

### 4.1. Amdahl's Law and Event Loop Starvation
While the core matching execution (`engine_latency_ns`) takes under **8 µs**, the overall server request lifecycle (`total_process_ns`) spans **1.1s to 2.0s** for both engines. 

This represents the mathematical inevitability of Amdahl's Law. Because the C++ engine optimizes a fraction of the lifecycle that accounts for less than **0.0004%** of the total request time, accelerating the match speed yields no macro-level benefit. To maintain order book state integrity without IPC (Inter-Process Communication), the server is restricted to a single Uvicorn worker. This single thread spends nearly 2 seconds on cryptographic JWT overhead and serialized Redis socket I/O (executing `WATCH`/`MULTI` locks for balance checks), completely starving the CPU while the matching engine sits idle.

### 4.2. Queue Saturation and the 5-Second Wall
At 500, 2000, and 5000 RPS, both architectures experience a uniform client-side `http_req_duration` collapse, clustering tightly at **~5,000 ms** for maximums and high percentiles.

This is an infrastructural artifact of Little's Law and OS socket exhaustion. The single-threaded ASGI server possesses a theoretical maximum throughput of ~40-50 RPS. Incoming loads up to 100x this capacity instantly fill the Linux TCP listen backlog. Requests wait in this queue until they hit the k6 load generator's strict client-side timeout limit (`timeout: '5s'`), resulting in forceful TCP termination prior to server processing.

---
## 5. Hypothesis Validation

**Validation:** Hypothesis H3 is **Strongly Accepted**. 

The language-level matching speedup (C++) is completely attenuated by the overarching middleware topology. The Engine Contribution Ratio is empirically proven to sit multiple orders of magnitude below the threshold where a language rewrite provides systemic value.

**Unified Verdict:**
The hybrid microservice architecture—relying on a REST API boundary (FastAPI) and external pre-trade network validation (Redis)—is fundamentally incompatible with High-Frequency Trading (HFT) latency goals. 

Optimizing the algorithmic core via FFI/C++ provides zero practical throughput gain in a decoupled system. To resolve this, future optimization targets must abandon the REST/Redis I/O boundary entirely. The prescribed evolutionary path requires fusing network ingestion (via binary protocols like FIX or SBE) and risk validation (via in-RAM colocation) into the same native compiled memory space as the matching core.