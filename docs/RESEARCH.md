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
| *Order Composition Ratio* | *70% Limit Orders, 30% Market Orders* | *Realistic flow; prevents all-immediate-fill or all-no-match artifacts* |
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
- **Order Composition:** *The flow maintains a strict ratio of 70% Limit Orders to 30% Market Orders.*
- **Side Distribution:** *Buy and Sell sides are uniformly distributed (50/50 probability).*

### 4.5.2 Replay
generated orders will be saved in a file and saved on disk , load generator will load it serialize it into ordered JSON and fire it at the system, that way will make sure that both engine get identical data and increasing the credibility of the answered questions at the same time.