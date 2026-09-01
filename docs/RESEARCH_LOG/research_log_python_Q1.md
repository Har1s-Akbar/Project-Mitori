# Throughput, Service, and Queue Residence Time of the Python Engine Analyzed: Picking up Noise and Anomalies

**Date:** `[29/08/2026]`  
**Author:** `[Haris Ahmad]`

> **Rule:** In this document we will log every run, analyzing and picking up the noise and evaluating until there is no noise or anomalies in the data and it is pristine for the benchmarking.

## Methodology and Expectation
The methodology for the benchmarking is simple. It follows 3 order book depths [1k, 25k, 50k] with three thread counts [1, 2, 4], creating a 3x3 matrix. Each trial runs for a duration of 30 seconds with an injection rate of 10k orders per second. Maintaining an order flux of 10k for 30s amounts to 300k orders, plus the initial 5k orders for warmup.

The expected result for the Python engine was that Throughput would be baselined (saturated), mimicking a saturation curve where it fails to exhibit high throughput even with the addition of threads. This is because of the Python GIL (Global Interpreter Lock), which forces each thread to wait for the sequential execution of the Python code.

- **Fix:** Since the order injection was the bottleneck during the initial benchmarking , for the python engine 600k RSP per second baseline is establishted , to demonstrate the Python GIL choking and throughput baselining.

## First Benchmarking (Ran - August 28th)
The result of the first benchmarking revealed and exposed the real and expected downgrading of the Python engine under concurrent multi-threaded load caused by GIL locking, but with a flaw (that will be discussed in the flaws section).

### Aggregated Benchmark Results (over 5 Trials)

| Depth | Threads | Throughput_RPS | Service_P50_ns | Service_P99_ns | Queue_P50_ns | Queue_P99_ns |
|:---|---:|---:|---:|---:|---:|---:|
| 1k | 1 | 10,000 | 3,635 | 51,247 | 3,962 | 134,005,118 |
| 1k | 2 | 19,996 | 2,054 | 10,692 | 361,181 | 553,864,629 |
| 1k | 4 | 39,201 | 2,054 | 11,918 | 9,297,765 | 1,334,159,709 |
| 25k | 1 | 10,000 | 2,305 | 15,388 | 2,466 | 54,367 |
| 25k | 2 | 19,996 | 2,095 | 10,006 | 179,628 | 5,908,680 |
| 25k | 4 | 39,973 | 2,059 | 10,971 | 6,782,852 | 169,560,156 |
| 50k | 1 | 10,000 | 2,295 | 13,935 | 2,455 | 48,877 |
| 50k | 2 | 19,995 | 2,150 | 11,415 | 196,340 | 6,023,599 |
| 50k | 4 | 39,965 | 2,025 | 8,894 | 6,531,856 | 151,463,114 |

### Expected Outcomes and Victories
- **Service Time Latency:** Service time staying constant throughout the 30-second market injection of 10k orders per second reveals the algorithmic legitimacy of the Python engine handling the orders at an expected low latency.
- **Queue Residence Latency:** Queue residence time scaling with the increase of threads reveals the expected outcome. With the increase of threads and the expected behavior of GIL sequential execution, queue residence time of the order scaled from `ns` to `ms` and even to `seconds` at thread count n = 4.

### Un-Expected Flaw
- **Throughput Scaling:** An unexpected outcome from the above benchmarking is that throughput is scaling linearly with the increase of threads. This is actively against our hypothesis, as we expected the throughput to baseline (saturate) around a specific point.

### Hypothesis
Hypothesis for the unexpected scaling of the throughput with the increase of threads:
- **Injection Rate:** The injection rate is too low. At 10k orders per thread, the injection rate is exactly under the GIL capacity. The GIL becomes a bottleneck only when the injection rate is higher than the GIL context switching time.

We can clearly deduce it by looking at the benchmarking script inside the `q1_worker` where we calculate the `interval_ns`:
`interval_ns = 1_000_000_000 // TARGET_RPS_PER_THREAD`

For the first benchmarking, the target RPS or injection rate is 10k, which gives an `interval_ns` of 100µs that is incorporated inside `expected_arrival`. As the telemetry suggests the average service time of the CPU is around 2-3ns, the CPU sits idle for the vast majority of the cycle. Because of the implemented time-spinning loop, the CPU just waits for `time.perf_counter_ns()` to grow larger than the expected arrival time so it can process the next order. This is why the GIL has plenty of headroom and is not being blocked, giving an illusion of linearly scaling performance when it is really just that the injection rate is unchallenging.

### Improvement For Next Benchmarking
Increasing the injection rate such that the GIL becomes the bottleneck and throughput is baselined.

## Second Benchmarking (Ran - August 28th)
In the second benchmarking, the injection rate was increased from 10k to 100k, and yet the Python engine handled it. Throughput scaled linearly with the increase of threads, service time remained more or less constant, while the queue residence time exploded.

### Aggregated Benchmark Results (over 5 Trials)

| Depth | Threads | Throughput_RPS | Service_P50_ns | Service_P99_ns | Queue_P50_ns | Queue_P99_ns |
|:---|---:|---:|---:|---:|---:|---:|
| 1k | 1 | 98,552 | 2,114 | 9,707 | 2,761 | 1,010,977,082 |
| 1k | 2 | 187,374 | 2,014 | 6,044 | 106,081,172 | 2,177,393,070 |
| 1k | 4 | 241,765 | 2,016 | 4,933 | 4,021,480,431 | 12,311,473,635 |
| 25k | 1 | 100,000 | 1,978 | 5,699 | 2,178 | 99,726 |
| 25k | 2 | 199,631 | 1,990 | 6,532 | 1,526,888 | 78,499,184 |
| 25k | 4 | 376,076 | 2,042 | 7,178 | 1,011,886,977 | 1,849,708,828 |
| 50k | 1 | 100,000 | 1,984 | 5,659 | 2,198 | 1,006,181 |
| 50k | 2 | 199,901 | 1,984 | 5,295 | 1,351,972 | 10,079,086 |
| 50k | 4 | 365,225 | 2,052 | 7,722 | 1,122,291,304 | 2,510,011,068 |

### Flaw
The same flaw resurfaced. While the queue residence time exploded into seconds, the throughput continued to scale across depth for 25k and 50k. However, the 1k order book depth hit a wall with 4 threads, the throughput degraded to 241k, an unlikely result for this depth.

There is a mechanical reason for the throughput drop across the 4-thread engine at the 1k order book depth. The 1k depth has shallow liquidity. The incoming orders cross the spread more violently, rapidly depleting the book and forcing the CPU to resize the binary tree mid-benchmark. Even though the service time remains more or less constant, the queue residence time (both P50 and P99) is exploding because of this, meaning orders are spending an astronomical amount of time resting in the queue waiting for the Python thread to resolve memory operations.

Throughput is again scaling linearly, but for the 50k 4-thread engine benchmarking, we can see it is beginning to hit the bottleneck because total throughput failed to reach a clean 400k. This reveals that the Python GIL bottlenecks around 400k. This number will be used (by adding 200k more, pushing the target to 600k) in the next benchmark to show the actual bottleneck and the flatlining of the throughput.

### Aggregated Benchmark Results (Mean over 5 Trials)

| Depth | Threads | Throughput_RPS | Service_P50_ns | Service_P99_ns | Queue_P50_ns | Queue_P99_ns |
|:---|---:|---:|---:|---:|---:|---:|
| 1k | 1 | 275,340 | 1,929 | 5,186 | 8,093,632,666 | 15,650,945,032 |
| 1k | 2 | 259,846 | 1,995 | 4,509 | 10,795,836,305 | 22,525,315,260 |
| 1k | 4 | 240,352 | 2,036 | 5,323 | 12,340,249,978 | 26,282,842,290 |
| 25k | 1 | 428,470 | 1,992 | 5,177 | 3,817,630,988 | 8,451,658,531 |
| 25k | 2 | 424,612 | 2,014 | 5,193 | 9,096,202,529 | 19,134,183,518 |
| 25k | 4 | 413,412 | 2,012 | 5,238 | 11,691,903,077 | 24,516,144,094 |
| 50k | 1 | 435,706 | 1,987 | 4,801 | 3,591,935,502 | 8,079,061,584 |
| 50k | 2 | 392,749 | 2,064 | 6,561 | 10,466,624,520 | 19,930,045,432 |
| 50k | 4 | 408,022 | 2,019 | 5,271 | 11,900,736,169 | 24,562,160,202 |

### Analysis

#### 1. The True GIL Ceiling (Negative Scaling)
By pushing the closed-loop injection target to 600k RPS, we successfully cornered the architecture. Looking at the 25k depth, 1 thread achieved a maximum throughput of 428,470 RPS. When scaled to 2 threads, throughput degraded to 424,612 RPS. At 4 threads, it fell further to 413,412 RPS. 

The throughput did not just baseline; it exhibited **Negative Scaling**. Adding threads actively harmed system performance. This proves the GIL has reached absolute saturation. The OS scheduler is wasting CPU cycles attempting to context-switch the lock between fighting threads, a penalty that is amplified by the Windows Hyper-V hypervisor migrating Linux virtual cores beneath Docker, leading to L1 cache invalidation.

Because the engine is physically capped around ~428k RPS but is being fed by a strict 600k RPS loop schedule, a massive backlog forms. This is why the queue residence times exploded to over 24 seconds—the orders are trapped in the queue, waiting for expected arrival timestamps that the CPU fell behind on almost immediately.

#### 2. The 1k Depth Algorithmic Collapse (Matching vs. Stacking)
The most striking anomaly is the performance disparity across depths. Even on a single thread—where GIL contention is mathematically zero—the 25k and 50k depths processed 50% to 80% faster than the 1k depth (428k RPS vs. 275k RPS).

This exposes a fundamental flaw in Python's memory management when dealing with market microstructure:
* **The 25k/50k State (Matching):** Deep liquidity allows the active stream to cross the spread and match orders continuously. This results in O(1) popping from the book. The memory footprint remains stable and highly performant.
* **The 1k State (Stacking & Array Thrashing):** A shallow book is vaporized by a 600k RPS injection rate in milliseconds. Once the liquidity dries up, the engine stops matching and begins strictly *stacking* limit orders. While the liquidity dries and the coming orders are stacked inside the heapq , instead of matching the queue residence time explodes for 1k order book depth as compared to the 25k and 50k order book depth.

### Hypothesis
Hypothesis for the throughput dropping for the 1k order book depth and scaling for the 25k and 50k order book depth is that
- **Liquidity Collapsing:** 1k order book does not have enough resting liquidity to properly handle 600k order injection and the resting liquidity is vaporized immediately , then the rest of the orders that are being injected starts stacking up in the `heapq`
- **Stacking not matching:** 1k order book depth spends more time stacking the order and managing the memory , the memory buffers and allocating contiguous memory locations , shifting and adjusting the `heapq` binary tree structure.
- **contiguous memory Allocation:** Whena orders are being pushed into the heap and are not being matched , mathematically `heappush` is O(Log N), it is backed by the Python `List` , appending to the list is O(1) most of the times, but when an increasing flux of coming orders are being stored in the list , the underlying C-array runs out of memory , for that reason python must pause the execution of the thread and allocate a massive chunk of the memory and then execute a c-level `memcpy` to move all the existing pointers to new allocated memory , cauing a memory disperancy and halt , dropping the throughput further more.

### Proper Dignosis 
For the proper dignosis of this phenomenon , a three second snapshot of the each telemetry will be implemented , which will output the size of the ask and bid at an interval of 3 seconds , this will verify the hypothesis. Expectaation for the 3 seocnd snapshot of the telemetry is 
- **1k order book depth:** 1K order book depth will exhibit a high difference in numbers of ask and bid , one of the side will grow while other will remain marginal.
- **25k &  50k order book depth:** both sides will scale and increase maintaining a linear relationship.

## Final Benchmarking (Ran - August 29th)

## 1. Aggregated Benchmark Telemetry
The following table represents the mean values aggregated across 5 trials for each Depth and Thread configuration under a 600,000 RPS closed-loop injection schedule.

| Depth | Threads | Throughput_RPS | Service_P50_ns | Service_P99_ns | Queue_P50_ns | Queue_P99_ns |
|:---|---:|---:|---:|---:|---:|---:|
| **1k** | 1 | 254,805 | 1,979 | 5,616 | 8,397,370,201 | 17,045,661,625 |
| **1k** | 2 | 223,564 | 2,082 | 6,921 | 12,369,286,870 | 24,091,384,736 |
| **1k** | 4 | 138,838 | 2,968 | 14,282 | 14,952,168,239 | 26,490,415,874 |
| **25k** | 1 | 304,195 | 2,537 | 8,740 | 7,786,787,999 | 14,675,813,681 |
| **25k** | 2 | 358,541 | 2,184 | 6,647 | 10,555,139,171 | 20,822,878,318 |
| **25k** | 4 | 362,930 | 2,088 | 7,540 | 13,270,102,971 | 25,136,476,176 |
| **50k** | 1 | 413,271 | 1,989 | 4,855 | 4,111,088,914 | 9,202,555,215 |
| **50k** | 2 | 387,832 | 2,034 | 5,944 | 9,195,578,066 | 19,873,841,449 |
| **50k** | 4 | 362,799 | 2,084 | 6,955 | 13,051,655,311 | 25,112,150,062 |

## 2. Aggregated Order Book Snapshots (Thread = 1)
To observe the internal state of the order book arrays, we aggregated the snapshot data across the 5 trials for the 1-Thread runs at the beginning (3s), middle (15s), and end (27s) of the benchmark.

| Depth | Elapsed | Mean Bids Count | Mean Asks Count | Book State |
|:---|---:|---:|---:|:---|
| **1k** | 3s | 27,242 | 197,383 | Imbalanced |
| **1k** | 15s | 6,614 | 946,846 | **Bid Collapse** |
| **1k** | 27s | 27,746 | 1,689,933 | **Unilateral Bloat** |
| **25k** | 3s | 243,308 | 245,391 | Balanced |
| **25k** | 15s | 1,146,131 | 1,149,848 | Balanced |
| **25k** | 27s | 2,072,550 | 2,081,274 | **Bilateral Bloat** |
| **50k** | 3s | 347,926 | 348,785 | Balanced |
| **50k** | 15s | 1,646,366 | 1,651,623 | Balanced |
| **50k** | 27s | 2,845,611 | 2,855,327 | **Bilateral Bloat** |

---

## 3. Findings and Analysis

### The Distinction Between "Depth" and "Liquidity"
This data provides a strict mechanical definition separating the initial state of the book (*Depth*) from its ability to survive an active stream (*Liquidity*).
*   **Depth** is simply the seed size of the arrays before the benchmark begins (1,000 vs. 25,000 vs. 50,000 orders).
*   **Liquidity** is the engine's ability to maintain a functional bid-ask spread under extreme load. 

The snapshot data verifies the hypothesis: **The 1k order book lacks the liquidity required to survive a 600k RPS active stream.** 
Because there are too few resting orders, the active stream vaporizes the Bid side almost immediately (dropping to 0 or near 0 consistently). Once the bids are depleted, the spread breaks. Incoming active sell orders have nothing to match against, forcing the engine into a state of *Unilateral Bloat*, where the Ask array absorbs a massive, unmatched stack of nearly 1.7 million limit orders.

Conversely, the 25k and 50k books possess enough initial mass to maintain bilateral liquidity. Both the Bid and Ask arrays grow symmetrically (reaching ~2.8 million orders at 50k depth). Because neither side ever hits zero, the spread remains intact, allowing the engine to continuously match and cross orders rather than strictly stacking them on one side.

### Throughput Degradation & Queue Residence
The collapse of liquidity directly impacts the Python Global Interpreter Lock (GIL) and total system throughput:

1.  **50k Depth (High Liquidity):** Showcases the highest absolute performance, processing **413,271 RPS** on a single thread. Because the throughput is so high, the Queue Residence P99 is kept relatively low at **9.20 seconds**. The engine only scales negatively under 4 threads (dropping to 362,799 RPS) due to standard GIL context-switching overhead.
2.  **1k Depth (Liquidity Collapse):** Showcases severe performance degradation. On a single thread, it can only process **254,805 RPS**. Furthermore, it scales catastrophically poorly under 4 threads, dropping to an abysmal **138,838 RPS**. Because the engine is processing so slowly compared to the 600k injection rate, the Queue P99 residence time skyrockets to **26.49 seconds**. 

**Conclusion:** The data proves unequivocally that the Python engine's throughput is tied directly to order book liquidity. 
- When the 1k book loses its spread, the engine stops executing trades and falls into a one-sided stacking loop. This state aggravates the Python GIL and memory allocator, causing massive lock contention, tanking throughput by over 45%, and causing queue latencies to explode.
- On the other hand **25k & 50k** order book depth's bid and ask is increasing with each second, but since both the sides are more or less equivalent , the orders are being matched instead of being stacked, this explains the
- Efficient queue residence time of 50k and 25k order book depth.
- Higher Throughput of the 50k and 25k order book depth as compared to 1k.

Confirming the Hypothesis of *liquidity Collapsing and stacking not matching* and refuting the contiguous memory allocation , even tho contiguous memory allocation phenomenon is true but by observing the 3-second snapshot telemetry , it is evident that further down the benchmarking 25k and 50k order book depths are experiencing more order flux in both asks and bids array.