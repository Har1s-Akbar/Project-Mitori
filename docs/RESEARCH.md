# Execution time and Request Latency Overhead comparison of Python based engine vs c++ based engine in a decoupled Microservice Architectural based Exchange Infrastructure 

**Date:** `[05/08/2026]`
**Author:** `[Haris Ahmad]`

>**Rule:** This Document will define what we will measure and how we will measure it, This Document will also include the Research Questions , Methodology and hypothesis of this research.

## Research Question
In a distributed microservice architecture Trading system with JWT authentication , login based funds hydration from database, funds verification and stream-based settlement with optimistic locking on streams and pessimistic locking on database resources with custom settlement commands on backend which read from the streams and settle the records in database , In a microservice system similar to this the questions i want to address are

- **Q1-(Throughput)**
Under concurrent multi threaded sustained load , how does the the throughput and the queue waiting time for order scales as compared to the multi threaded c++ implementation
- **Q2-(Algorithmic)**
What is the difference between the throughput , P50 and P99 latency of a single threaded algorithmicly implemented python engine using `heapq`  over a c++ implemented engine implemented using `priority_queue`
- **Q3-(Systems):**
In the full HTTP request path, what percentage of end-to-end latency is attributable to the matching engine versus I/O and middleware overhead?

## Hypothesis
**H1 — Throughput Hypothesis**
> Under High concurent multi threaded load at engine level c++ implementation will yield exceptionally higher throughput as compared to multi threaded python engine because of Python Global Interpreter Lock , that will starve the threads and will force them to be processed sequentially not concurently, forcing the python throughput to be roughly equal to a single threaded engine.
**H2 — Algorithmic Hypothesis**
> A C++ order book implementation (exposed via pybind11) will exhibit lower matching latency than the Python `heapq` implementation. The speedup will increase with book depth due to memory locality and reduced allocation overhead.

**H3 — Systems Hypothesis**
> In the full API request path, the language-level matching speedup will be attenuated by I/O and serialization overhead. The contribution of matching latency to total API latency will fall below a threshold where language rewrite is not the optimal optimization target.

## 3. System Architecture & Measurement Boundaries
Detailed System Overview is given in README.md if you want to dwell into the architectural tradeoffs and features , i will highly recommend the README.md, This is a brief overview of a request lifecycle in this distributed system.

First user logs in , django simpleJWT mints two token `access` and `refresh` token , at the time of login django queries the postgres table under core_lodger app specifically portfolio and position tables and load the `funds` and `positions` in the redis cache using `signal pattern` of django, then the user can goes to the route `/order` and puts an order either `SELL` or `BUY` now the way `/order` route is configuered it has dependency injection , it depends on `have_funds` function that checks the funds or positions seeded in the cache if the user has enough funds for thus trade , this function `have_funds` is further dependent on `is_Authenticated_user` which decrypts the JWT token and returns the `Authenticated_user` pydantic model consisting of `user_id and kyc`.
Further `have_funds` leverages the  redis watch , multi , exec and pipeline for optimistic locking and lock funds in the redis cache, `have_funds` is implemented with yield pattern this transforms the dependency into a generator , after the  order is matched it is pushed into the redis `executed_trade` with fire and persisit pattern , which django daemon `trade_registery` which is implemented through django custom commands picks the order up and check if the order has already settled in the postgres , if not the trade is settled recorded into the transaction , and positions and postfolio are updated and then if the order was executed at the lower price from the user locked price the locked funds are returned to it's portfolio.

Same is the flow for order deletion but for it tombstone deleteion is used , instead of deleting order at once it is marked as cancelled and when it is emerged on top it is gracefully skipped.
For more indepth architectural decisions and nuances i would refer you to the README.md


[Authentication] → [Django (DRF / simpleJWT)]
       |
       v
[Client Application] 
       |
       v
[FastAPI: POST /order]
       ├── 1. JWT Decode (security.py)
       ├── 2. Balance Check (Redis WATCH/MULTI/EXEC - have_funds)
       |
       ├── 3. EngineProtocol / Gateway Manager (Reads ENGINE_MODE)
       |      ├── IF 'PYTHON': Route to Python Engine (heapq)
       |      └── IF 'CPP': Route to C++ Engine (Pybind11 / Arena Allocator)
       |
       ├── 4. Order Execution (Strictly Raw Scaled Integers * 10^8)
       |
       ├── 5. Trade Serialization
       └── 6. Redis XADD (executed_trades_stream -> Raw Scaled Integers)
       
======================== [ ASYNC BOUNDARY ] ========================

[Django Background Daemon] (Reads executed_trades_stream) | (Idempotency Guard)
       ├── 1. Integer Descaling (Divides price/qty by 10^8)
       ├── 2. Persistence -> [PostgreSQL]
       ├── 3. Acknowledgment -> [Redis XACK]
       └── 4. Cache Update -> [Redis settle_cache]

======================== [ SYNC BOUNDARY ] ========================

## 3.1 Engine Implementation 
Both engines implement price-time priority using binary heaps (O(log n) insertion and extraction). The Python engine stores full order tuples within the heapq structure, reflecting idiomatic Python patterns. The C++ engine employs an index-based heap where std::priority_queue stores 32-bit indices into a contiguous OrderMetadata vault, reflecting idiomatic C++ cache-optimization patterns. While this introduces a structural difference in memory layout, both implementations maintain identical algorithmic semantics: identical match sequences, identical partial-fill behavior, and identical tombstone cancellation. The performance differential therefore reflects both language-level execution efficiency and implementation-level memory-layout optimization.

## 4. Experimental Methodology
In this section i will go over the experimental methodology and map out
- **4.1- Independent Variables**
- **4.2- Dependent Variables**
- **4.3- Constant Variables**
- **4.4- Environment & Infrastructure**

### 4.1 Independent Variables
Each research question has it's own experiment design and each question has it's own experimental matrix

### 4.1.1 Engine Throughput & Concurency Scaling
For the benchmarking and answering question 1 , there will be no JWT, HTTP request , engine will be benchmarked strictly with concurent thread scaling for both c++ and python engine.

#### 4.1.1 Q1 — Engine Throughput 

| **Variable** | **Levels** | **Notes** |
|---|---|---|
| *Engine Implementation* | *Python (`heapq`), C++ (`std::priority_queue` + pybind11)* | *Swapped via `ENGINE_MODE`* |
| *Book Depth* | *1K, 25K, 50K resting orders* | *Pre-seeded before timer starts* |
| *Thread Count* | *1, 2, 4* | *Each thread maintains a fixed injection rate* |
| *Injection Rate (per thread)* | *10,0000 orders/sec* | *Fixed per thread; total load scales with thread count* |

**Q1 Experimental Matrix:** 2 engines × 3 depths × 3 thread counts = **18 cells**

**Total benchmark runs:** 18 cells × 5 trials = **90 runs**

---

#### 4.1.2 Q2 — Algorithmic Latency (Single-Thread)
Pure single threaded latecny execution speed of python and c++ engine , sequential executionn of orders and measurement of P99, P50 and throughput.

| **Variable** | **Levels** | **Notes** |
|---|---|---|
| *Engine Implementation* | *Python (`heapq`), C++ (`std::priority_queue` + pybind11)* | *Swapped via `ENGINE_MODE`* |
| *Book Depth* | *1K, 25K, 50K resting orders* | *Pre-seeded before timer starts* |

**Q2 Experimental Matrix:** 2 engines × 3 depths = **6 cells**

**Total benchmark runs:** 6 cells × 5 trials = **30 runs**

**What is held constant in Q2:**
- Thread count = 1 (single-threaded by design)
- Injection rate = sequential (one order at a time, no queue)
- GC state = explicitly disabled around timing loop

---

#### 4.1.3 Q3 — Full API Path Latency
End-to-end HTTP request through FastAPI, including JWT, Redis, matching, and stream push.

| **Variable** | **Levels** | **Notes** |
|---|---|---|
| *Engine Implementation* | *Python (`heapq`), C++ (`std::priority_queue` + pybind11)* | *Swapped via `ENGINE_MODE`* |
| *HTTP Request Rate* | *500, 2,000, 5,000 RPS* | Open-model load |

**Q3 Experimental Matrix:** 2 engines × 3 request rates = **6 cells**

**Total benchmark runs:** 6 cells × 5 trials = **30 runs**

---

#### 4.1.4 Cross-Engine Parity Methodology
The constraint dictating that the C++ implementation must utilize similar semantics to the Python baseline is strictly enforced. This ensures that execution time differentials represent genuine architectural characteristics (e.g., memory management, FFI overhead) rather than algorithmic divergence. To guarantee this comparison, the project employs a rigorous parity validation framework:

*   **Interface Unification:** Both implementations strictly adhere to a shared `EngineProtocol` gateway interface, ensuring identical method signatures and command-query separation.
*   **Dual-Mode CI Validation:** A comprehensive test suite utilizes a dynamic `engine_mode` fixture within `pytest`. Every continuous integration (CI) run executes the complete operational flow against both the pure Python (`heapq`) and C++ (`ArenaAllocator`) engines simultaneously.
*   **HTTP-Level Output Verification:** A dedicated integration test asserts that, given an identical pre-seeded orderbook and an identical sequence of incoming orders, both engines produce a byte-for-byte identical sequence of executed trades at the HTTP egress layer.

This parity validation neutralizes the risk of comparing structurally inequivalent logic, isolating the benchmark to measure purely the execution latency and memory constraints of the respective environments.

### 4.2- Dependent Variables
These are the variables which are our main concern , they will yield different values based on the variance of independent variables and they will form the result of this research.
Definition of **Throughput** changes depeneding upon the benchmarking stage.
- **Question 1 (Throughput):** `For question 1, Throughput is the maximum number of orders processed by the engine per trial when all threads are concurently forcing the orders in the engine.`
- **Question 2 (Throughput)** `For question 2, Throughput is the maximum number of orders processed per execution cycle and trial.`

Similarly P50 and P99 mmean  completely different things in Research Question 1 and 2
- **Question 1 (P50 & P99):** `For Research question 1 P50 and P99 latency also includes the queue residence time , total time from order submission to order completion`
- **Question 2 (P50 & P99):** `For Research question 2 P50 and P99 only include the service time which is how fast the ordered is processed in engine`

#### 4.2.1 Q1 — Throughput 

| **Metric** | **Definition** |
|---|---|
| *Throughput* | *Total orders successfully processed by the engine divided by the 30-second recording window. Measured across all threads.* |
| *Service Time p50 / p99* | *Time spent inside `process_order()` only. Excludes queue wait.* |
| *Queue Residence Time p50 / p99* | *Total time from order submission (arrival at thread queue) to order completion.* |
| *Queue Depth* | *Orders submitted minus orders processed, sampled every second.* |
| *Saturation Point* | *The thread count at which throughput stops increasing between successive doublings.* |

#### 4.2.2 Q2 — Algorithmic Latency

| **Metric** | **Definition** |
|---|---|
| *Throughput* | *Total orders processed divided by wall-clock time using perf_counter()* |
| *Execution Time p50 / p99* | *Time from entry to `process_order()` to return of trade results.* |

#### 4.2.3 Q3 — End-to-End API Latency

| *Metric* | *Definition* |
|---|---|
| *API Response Latency p50 / p99* | *Time from TCP request accepted to HTTP response sent. Includes JWT, Redis, matching, serialization, and stream push.* |
| *Engine Contribution Ratio* | *`Q2 matching p99 / Q3 API p99` at identical engine mode. Shows what percentage of API latency is the engine itself.* |
| *Error Rate* | *Percentage of 409 (Redis WATCH conflict) or 500 responses.* |
| *Redis Consumer Group Lag* | *`XINFO GROUPS` lag after 60s of sustained load.* |


### 4.3 Constant Variables (Held Constant Across All Questions)
| *Variable* | *Fixed Value* | *Why* |
|---|---|---|
| *Payload Schema* | *Identical JSON structure for both engines | Prevents serialization bias* |
| *Order Composition Ratio* | *50% Limit Orders, 50% Market Orders* | *Realistic flow; prevents all-immediate-fill or all-no-match artifacts* |
| *Price Distribution* | *Ornstein-Uhlenbeck (μ=100, θ=0.10, σ=0.50)* | Mean-reverting; realistic spread |
| *Precision Multiplier* | *`10^8`* | *Eliminates `Decimal` overhead; identical in both engines* |
| *Seed* | *`SEED = 39`* | *Deterministic replay* |
| *Trial Duration* | *30 seconds recording + 5,000 order warm-up* | *Warm-up is discarded* |
| *Repetitions* | *5 independent trials per cell* | *Statistical power for Mann-Whitney U* |
| *State Sterilization* | *`reset_engine()` + `gc.collect()` + `FLUSHALL` between trials* | *Eliminates cross-trial contamination* |

### 4.4 Environment & Infrastructure
To ensure reproducible latency measurements , all benchmarking are done on a dedicated local compute node.
Given the constraints of virtualizing on non-linux machines certain constraints and tunnings  were applied to mitigate this contraint.

#### 4.4.1 Hardware and OS and Software
Machine on which the benchmarking will be performed is equipped with
- *13th-generation Intel Core i7-1355U processor, featuring an asymmetric architecture of 10 physical cores (2 Performance cores, 8 Efficient cores) and 12 logical threads, operating at a base clock of 1.70 GHz*
- *8 GB of physical memory and a 512 GB Samsung NVMe Solid State Drive (MZAL8512HDLU-00BL2)*

OS and Docker configurations are
*Windows 11 Enterprise build number 26200.8875 with Subsystem for docker WSL2*

Full description of all the software dependencies and their versions can be found in requirements.txt of each service , major depenedencies and their versions are listed here 
- *python==3.14.4 (64-bit)*
- *C++ Toolchain: Container-native GCC compiler (Debian/Ubuntu default, typically v11.x or v12.x) utilizing -O3 -march=native release optimization flags and pybind11. (Note: Host-level MSYS2 Windows compilers were explicitly excluded to maintain Linux ABI compatibility).*
- *fastapi==0.139.0*
- *uvicorn==0.50.2*
- *pydantic==2.13.4*
- *Django==6.0.6*
- *pybind11==3.1.0*
- *djangorestframework==3.17.1*
- *psycopg2-binary==2.9.12*
- *PyJWT==2.13.0*
-*POSTGRESQL v16*

#### 4.4.2 Virtualization and Container Isolation
Because the host operating system is Windows, the microservice architecture is virtualized through Docker desktop leveraging windows subsystem for Linux.
To prevent latency spikes caused by docker moving the threads across cores during the benchmarking, containers are pinned to specific cores.
Containerized application and the containers for specific services are pinnned to specific cores.
- **FastAPI & Engine:** *are pinned to performance cores for maximum performance and throughput*
- **Redis and Djnago:** *are pinned to efficient cores to prevent them from stealinng resources from the performance cores and affecting the order matching and API latency*
- **Load Generators** *are pinned to remaining core for isolated efficiency*
- **Memory Limits:** *Hard Memory constraints are added to docker to prevent it from exhasting the 8GB available memoryy completely which would trigger swapping and invalidating the memory latency*

#### 4.4.3 Network Constraints and optimization
Due to host machine being a Windows operating system , and limitation of docker on the windows the network directive `--network host` will not fully bypass the NAT (Network Address Translation).
Consequently the API response latency will include the network overhead.
To maximize the throughput with these constraints
- **File Descriptors:** *The open file descriptor limit within the WSL2 kernel is elevated to 65,535 `(ulimit -n 65535)` to prevent socket exhaustion during peak order arrival loads*

#### 4.4.4 Warm-up Protocol and Sampling
In this section, warm-up and sampling for the research are explained:

- **Warm-Up Phase:** *Prior to recording telemetry for any experimental cell, an untimed warm-up load of 5,000 requests is executed to pre-prime the chunk slab allocator and cache pools. Data generated during this phase is explicitly discarded.*
- **Sample Size (N) and Duration:** *Each of the experimental cells for the corresponding research question is executed across N = 5 independent test trials. To capture potential queue degradation, each trial sustains the target request rate for exactly 30 seconds.*
- **Reset & State Sterilization:** *Between individual trials, a multi-tier hard reset protocol is executed to guarantee an absolute zero-state environment across the entire stack:*
  1. ***C++ Engine Layer:** The `OrderBook::reset_engine()` routine frees all active heap pointers via the authoritative tracking vault, forces immediate capacity deallocation of priority queues and the metadata vector using the STL swap idiom, and resets the chunk slab allocator via an O(1) pointer-offset rewind (`ArenaAllocator::reset()`).*
  2. ***Python & Application Layer:** Explicit garbage collection (`gc.collect()`) is forced to eliminate cyclic references.*
  3. ***Storage & Caching Layer:** A full Redis cache flush (`FLUSHALL`).

- **GIL Release:** *Prior to Q1 benchmarking, a sanity test confirms that the C++ process_order binding releases the Python GIL. This is verified by spawning two threads that simultaneously call the C++ engine and confirming that wall-clock execution time is approximately halved compared to sequential execution*

### 4.4.5 Statistical Significance and Non parametric Testing
Due to the right-skewed nature of network latency, central tendencies will be compared using the non-parametric Mann-Whitney U test a = 0.05, and tail latencies p99 will be evaluated using bootstrapped 95% confidence intervals

### 4.5 Synthetic Order Generation
To guarantee deterministic execution and identical orders for each implementation, the order flow is pre generated and saved to disk prior to benchmarking


### 4.5.1 Generation
Order sequences are synthesized using a predefined pseudorandom number generator (PRNG) initialized with a static global seed (SEED = 39).
- **Price Distribution:** *Prices are generated by using a discreet-time **Ornstein-Uhlenbeck process**, gaussian random walk anchored around 100, standard deviation is tuned to maintain a realistic spread and simulate high frequency behaviour. Price may fluctuate from the base 100 but it will keep reverting back to the base price mimicking the real world asset price fluctuation*
- *Long Term Price = u = 100.00*
- *Mean reversion rate = theta =0.10*
- *Standard deviation = sigma = 0.50*
*Note- OU gaurantees that price and orders will cluster around our base price because of our defined theta , the bigger the theta the more hard it is for price to drift apart  on contrary if it is less price is allowed to move far but it eventually comes back to the base price(specifically OU model)*
- **Order Composition:** *The flow maintains a strict ratio of 50% Limit Orders to 50% Market Orders.*
- **Side Distribution:** *Buy and Sell sides are uniformly distributed (50/50 probability).*

### 4.5.2 Replay
generated orders will be saved in a file and saved on disk , load generator will load it serialize it into ordered JSON and fire it at the system, that way will make sure that both engine get identical data and increasing the credibility of the answered questions at the same time.

## 5. Benchmarking Phase
under the above conditions, pre-requisites and experimental methodology benchmarking phase of each question was ran properly, for each benchmarking it was made sure that specified configuration was and along with that several changes were made along the way in the engine as well to make them benchmarking ready.
Benchmarking phase is thoroughly and completely documented in the `RESEARCH_LOG` folder. Please reference it for complete benchmarking and telemetry analysis.

## 6. Results and Analysis
After a multi week benchmarking phase which was goining on for the better part of the August and the starting days of the Septemeber , Benchmarking officially cocnluded and now this  section deals with the resulsts and analysis of the benchmarking , as mentioned in the experimental methododlogy section 4.4.5.
All statistical comparisons use the two-sided Mann-Whitney U test (α = 0.05) with rank-biserial effect size *r*, and bootstrapped 95% confidence intervals on the P99 latency (10,000 subsamples, 1,000 resamples, percentile method). Effect sizes are interpreted as: |r| &lt; 0.3 (small), 0.3–0.5 (medium), &gt; 0.5 (large).

### 6.1 Q1 — Throughput & Concurrency Scaling

#### 6.1.1 Throughput Comparison

| Depth | Threads | Python RPS | C++ RPS | C++ Speedup |
|:-----:|:-------:|:----------:|:-------:|:-----------:|
| 1k    | 1       | 228,174    | 600,308 | 2.6×        |
| 1k    | 2       | 243,543    | 938,223 | 3.9×        |
| 1k    | 4       | 223,782    | 752,983 | 3.4×        |
| 25k   | 1       | 382,258    | 600,309 | 1.6×        |
| 25k   | 2       | 363,508    | 1,069,695 | 2.9×      |
| 25k   | 4       | 366,926    | 809,769 | 2.2×        |
| 50k   | 1       | 405,909    | 600,302 | 1.5×        |
| 50k   | 2       | 302,165    | 958,376 | 3.2×        |
| 50k   | 4       | 291,086    | 751,318 | 2.6×        |

**Key Finding — Python GIL Saturation:** Python throughput does not scale with thread count. At 1k depth, adding threads from 1→2→4 yields 228k → 244k → 224k RPS — effectively flat. The GIL forces sequential execution regardless of thread count, confirming H1.

**Key Finding — C++ Mutex Thrashing:** C++ scales linearly from 1→2 threads (600k → 938k–1,070k RPS) but collapses at 4 threads (753k–810k RPS). The mutex contention overhead at 4 threads wastes ~30% of the theoretical throughput gain. The saturation point for C++ is **2 threads** under this workload.

![Q1 Throughput Scaling](/benchmark\analysis\plots\q1_throughput_scaling.png)
*Figure 1: Q1 throughput scaling across thread counts and book depths. C++ speedup annotated.*


#### 6.1.2 Service Latency

| Depth | Threads | Python P50 (ns) | Python P99 95% CI (ns) | C++ P50 (ns) | C++ P99 95% CI (ns) | Effect Size *r* | Interpretation |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| 1k | 1 | 2,112 | [7,461, 9,745] | 237 | [328, 328] | 1.000 | C++ dominates |
| 1k | 2 | 2,093 | [4,954, 5,821] | 304 | [804, 804] | 0.909 | C++ dominates |
| 1k | 4 | 2,130 | [5,400, 6,176] | 403 | [1,671, 1,671] | 0.668 | C++ advantage shrinking |
| 25k | 1 | 2,081 | [7,666, 12,445] | 265 | [410, 410] | 1.000 | C++ dominates |
| 25k | 2 | 2,120 | [7,762, 11,947] | 363 | [583, 583] | 0.942 | C++ dominates |
| 25k | 4 | 2,124 | [7,331, 9,273] | 474 | [20,715, 20,715] | 0.442 | **Medium effect** |
| 50k | 1 | 2,056 | [5,887, 8,497] | 816 | [905, 905] | 0.049 | **Negligible** |
| 50k | 2 | 2,175 | [12,893, 16,215] | 498 | [5,148, 5,148] | 0.598 | C++ advantage |
| 50k | 4 | 2,188 | [12,220, 15,608] | 433 | [17,157, 17,157] | 0.349 | **Small effect** |

**Key Finding — The GIL-as-Equalizer:** At 50k depth / 1 thread, the effect size drops to *r* = 0.049 — practically negligible. Python's dictionary-based heapq benefits from cache locality at high depth, narrowing the gap with C++'s index-based priority_queue when the working set is large.


### 6.1.3 Queue Residence Time

| Depth | Threads | Python P50 (ns) | Python P99 95% CI (ns) | C++ P50 (ns) | C++ P99 95% CI (ns) | Python Delay | Effect Size *r* |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1k | 1 | 9.46×10⁹ | [1.86×10¹⁰, 1.86×10¹⁰] | 2.07×10⁷ | [2.15×10⁷, 2.15×10⁷] | **456×** | 0.995 |
| 1k | 2 | 1.15×10¹⁰ | [2.36×10¹⁰, 2.36×10¹⁰] | 5.03×10⁷ | [3.06×10⁸, 3.06×10⁸] | **229×** | 0.988 |
| 1k | 4 | 1.06×10¹⁰ | [2.68×10¹⁰, 2.70×10¹⁰] | 1.72×10⁸ | [5.80×10⁸, 5.80×10⁸] | **61×** | 0.975 |
| 25k | 1 | 5.33×10⁹ | [1.15×10¹⁰, 1.15×10¹⁰] | 2.53×10⁷ | [3.03×10⁷, 3.03×10⁷] | **211×** | 0.996 |
| 25k | 2 | 1.02×10¹⁰ | [2.11×10¹⁰, 2.13×10¹⁰] | 7.14×10⁷ | [9.08×10⁷, 9.08×10⁷] | **143×** | 0.994 |
| 25k | 4 | 1.34×10¹⁰ | [2.51×10¹⁰, 2.53×10¹⁰] | 1.75×10⁸ | [3.94×10⁸, 3.94×10⁸] | **77×** | 0.984 |
| 50k | 1 | 5.11×10⁹ | [9.86×10⁹, 9.91×10⁹] | 2.24×10⁷ | [2.62×10⁷, 2.62×10⁷] | **228×** | 0.997 |
| 50k | 2 | 1.09×10¹⁰ | [2.29×10¹⁰, 2.33×10¹⁰] | 1.14×10⁸ | [2.15×10⁸, 2.15×10⁸] | **96×** | 0.992 |
| 50k | 4 | 1.23×10¹⁰ | [2.63×10¹⁰, 2.66×10¹⁰] | 1.78×10⁸ | [3.33×10⁸, 3.33×10⁸] | **69×** | 0.989 |

**Key Finding — The Queue Catastrophe:** Python orders spend **9–13 seconds** in queue (P50) under concurrent load, while C++ orders spend **20–178 milliseconds**. The GIL doesn't just limit throughput — it creates a backlog that grows without bound. At 4 threads, Python's queue P99 exceeds **26 seconds**, meaning orders wait 26× longer than the 30-second trial duration.

#### 6.1.4 The Mutex-vs-GIL
At 4 threads / 25k depth, C++ service P99 CI = **[20,715, 20,715]** ns, while Python P99 CI = **[7,331, 9,273]** ns. **C++ tail latency is 2.2× worse than Python's.**

This counter-intuitive result occurs because:
1. Python's GIL forces *strict serialization* — one order at a time, no contention, predictable latency
2. C++'s mutex allows *parallel acquisition* but creates *convoy effects* — threads pile up, and the 99th percentile thread waits for 3+ others to complete

**Implication:** For latency-sensitive systems with &gt;2 concurrent matching threads, Python's GIL may produce more predictable tail latency than a naive mutex-based C++ implementation. A lock-free or sharded C++ design would be required to reclaim the advantage.

![Q1 Queue Latency](/benchmark/analysis/plots/q1_queue_latency.png)
*Figure 2: Q1 queue residence time (P50, log scale). Python orders wait 9–13 seconds; C++ orders wait 20–178 milliseconds.*

---

### 6.2 Q2 — Algorithmic Latency

| Depth | Python P50 (ns) | Python P99 95% CI (ns) | C++ P50 (ns) | C++ P99 95% CI (ns) | Speedup | Effect Size *r* | p-value |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1k | 3,299 | [19,999, 22,167] | 75 | [447, 504] | 44× | 1.000 | < 0.001 |
| 25k | 4,463 | [53,072, 66,034] | 70 | [790, 881] | 64× | 1.000 | < 0.001 |
| 50k | 3,708 | [28,185, 30,912] | 72 | [1,084, 1,203] | 51× | 0.999 | < 0.001 |

**H2 Accepted.** In isolated single-threaded execution, C++ is **44–64× faster** than Python at pure matching. The P99 CIs do not overlap at any depth. The C++ `ArenaAllocator` + index-based `std::priority_queue` consistently outperforms Python's tuple-based `heapq`.

![Q2 Isolated Latency](/benchmark/analysis/plots/q2_isolated_latency.png)
*Figure 3: Q2 isolated matching latency with bootstrapped 95% P99 CIs. C++ is 44–64× faster.*

---

### 6.3 Q3 — Full API Path & The Paradox (with 95% Bootstrapped Confidence Intervals)

| Metric | RPS | Python P50 | Python P99 95% CI | C++ P50 | C++ P99 95% CI | p-value | Effect Size *r* | C++ Advantage |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| Engine Latency | 500 | 6,761 ns | [38,748, 48,760] ns | 6,587 ns | [33,393, 38,778] ns | 8×10⁻³² | 0.052 | **~3%** |
| Engine Latency | 2000 | 6,451 ns | [38,551, 45,898] ns | 6,237 ns | [32,302, 36,629] ns | 8×10⁻⁷⁰ | 0.075 | **~3%** |
| Engine Latency | 5000 | 6,493 ns | [38,438, 45,829] ns | 6,290 ns | [31,706, 37,872] ns | 3×10⁻⁶⁷ | 0.074 | **~3%** |
| HTTP Request | 500 | 1,280 ms | [3,745, 4,634] ms | 1,349 ms | [5,000, 5,001] ms | 1.0 | -0.067 | **Python wins** |
| HTTP Request | 2000 | 1,920 ms | [3,694, 3,743] ms | 1,929 ms | [3,426, 3,466] ms | 5×10⁻⁶⁶ | 0.053 | **Negligible** |
| HTTP Request | 5000 | 2,069 ms | [3,972, 4,239] ms | 1,993 ms | [3,502, 3,598] ms | 3×10⁻¹⁵³ | 0.082 | **~4%** |
| Total Process | 500 | 902 ms | [3,161, 3,293] ms | 933 ms | [2,966, 3,054] ms | 1.0 | -0.027 | **Python wins** |
| Total Process | 2000 | 1,560 ms | [3,089, 3,163] ms | 1,622 ms | [2,984, 3,032] ms | 1×10⁻⁸⁴ | 0.060 | **~10%** |
| Total Process | 5000 | 1,738 ms | [3,403, 3,561] ms | 1,669 ms | [3,040, 3,078] ms | 2×10⁻¹³⁷ | 0.078 | **~3%** |

**H3 Strongly Accepted.** The 50× speedup from Q2 has been attenuated to **~3%** in the full system. At 500 RPS, C++ is actually *slower* than Python for total process latency (p = 1.0, r = -0.027).
This proves the hypothesis drmatically , the first 2 benchmarkings were done with the pre seeding of the orders in the cache casting the python based data structures into c++ complient data structures, which measured the raw speed of the both engines but when it came to a full path execution the FFI binding and Python data serialization into c++ data structures proved more time takking and consuming.

**Engine Contribution Ratio:**
At 5000 RPS:  Engine P99 (~38µs) / HTTP P99 (~4605ms) = 0.0008%
The matching engine accounts for **less than 0.001%** of total API latency. Optimizing it is mathematically futile per Amdahl's Law.

**The 5-Second Wall:** Both engines show `http_req_duration` clustering at ~5,000 ms for high percentiles. This is the k6 client timeout, not server processing time. The single-threaded ASGI server (Uvicorn) has a theoretical ceiling of ~40–50 RPS for CPU Bound requests. Loads of 500–5,000 RPS instantly saturate the TCP listen backlog. Requests wait in OS queues until timeout.

![Q3 Paradox](/benchmark\analysis\plots\q3_paradox.png)
*Figure 4: Q3 engine latency vs. HTTP latency. The ~50× engine speedup vanishes in the full system.*


---

### 6.4 Cross-Question
| Question | C++ Advantage | Mechanism | Real-World Relevance |
|:---------|:-----------:|:----------|:---------------------|
| **Q2** (Isolated) | **50×** | Memory layout, cache locality, zero-allocation | High — if engine is the bottleneck |
| **Q1** (Concurrent) | **2–4×** throughput, **60–450×** queue time | GIL vs. mutex | High — C++ prevents queue collapse upto a certain point|
| **Q3** (Full System) | **~3%** | Amdahl's Law — I/O dominates | **Negligible** — rewrite not justified |

**The Central Thesis:** Language-level optimization is only valuable when the matching engine is the bottleneck. In a decoupled microservice architecture with JWT, Redis, and HTTP serialization, the engine contributes <0.001% of latency. The optimal optimization target is **not the engine** — it is the I/O boundary (in-memory risk, binary protocols, kernel-bypass networking).

---

## 7. Conclusions

### 7.1 Hypothesis Validation

| Hypothesis | Verdict | Evidence |
|:-----------|:-------:|:---------|
| **H1** — C++ yields higher throughput under concurrent load | **Accepted** | C++ achieves 2–4× higher RPS; Python GIL prevents scaling |
| **H2** — C++ exhibits lower matching latency | **Strongly Accepted** | 44–64× speedup in isolation; all p < 0.001, r > 0.999 |
| **H3** — Speedup attenuated by I/O in full system | **Strongly Accepted** | Engine advantage drops to ~3%; HTTP latency dominated by middleware |

### 7.2 Key Contributions
1. **Empirical proof of the "Mutex Worse Than GIL" phenomenon** in order-book matching. At 4 threads, C++ mutex contention produces 2.2× worse P99 tail latency than Python's serialized execution.
2. **Quantification of Amdahl's Law** in a real trading system. The engine contribution ratio is <0.001%, making language rewrites economically irrational.
3. **A reproducible benchmarking framework** for polyglot microservices, including deterministic replay, controlled variables, and non-parametric statistical testing.

![Synthesis](/benchmark\analysis\plots\synthesis_attenuation.png)
*Figure 5: Cross-question synthesis. C++ advantage attenuates from 50× → 3× → <0.001% as system scope expands.*

### 7.3 Limitations

- **Hardware:** Consumer-grade laptop (i7-1355U, 8GB RAM) with WSL2 virtualization. Results may differ on server-grade hardware with more cores and lower virtualization overhead.
- **Sample Size:** 5 trials per cell provides adequate power for Mann-Whitney U but limits generalization to rare events.
- **Synthetic Workload:** Ornstein-Uhlenbeck price distribution is realistic but not market data. Real-world skew and burst patterns may alter queue dynamics.

### 7.4 Future Work
1. **Lock-Free C++ Engine:** Replace `std::mutex` with per-price-level sharding or lock-free data structures to reclaim the 4-thread advantage.
2. **In-Memory Risk:** Colocate balance validation with the matching engine to eliminate the Redis round-trip.
3. **Binary Protocols:** Replace HTTP/JSON with FIX or SBE over kernel-bypass networking (DPDK / RDMA).
4. **Kernel-Bypass Settlement:** Fuse the settlement daemon into the matching process to eliminate the Redis Stream boundary.
