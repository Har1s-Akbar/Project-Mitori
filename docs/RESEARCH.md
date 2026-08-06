# Execution time and Request Latency Overhead comparison of Python based engine vs c++ based engine in a decoupled Microservice Architectural based Exchange Infrastructure 

**Date:** `[09/05/2026]`
**Author:** `[Haris Ahmad]`

>**Rule:** This Document will define what we will measure and how we will measure it, This Document will also include the Research Questions , Methodology and hypothesis of this research.

## Research Question
In a distributed microservice architecture Trading system with JWT authentication , login based funds hydration from database, funds verification and stream-based settlement with optimistic locking on streams and pessimistic locking on database resources with custom settlement commands on backend which read from the streams and settle the records in database , In a microservice system similar to this the questions i want to address are

**Q1-(Throughput)**
is a python based matching engine's throughput efficient if not does a rewrite in c++ worth the extra effort?
**Q2-(Algorithmic)**
is python `heapq` based matching engine in python efficient as compared to c++?
**Q3-(Systems):**
In the full HTTP request path, what percentage of end-to-end latency is attributable to the matching engine versus I/O and middleware overhead?

## Hypothesis
**H1 Throughput Hypothesis**
> Under High concurent load upto (5000 RPS), the c++ and pybind11 implementation will fail to demonstrate a statistically significant throughput advantage over python native implementation. The overhead introduced by the FFI(foreign function interface) and unboxing of pydantic models into c++ data structures will mask the algorithmic speed of c++, resulting in I/O and serialization bottleneck

**H2 Algorithmic Hypothesis**
> A C++ order book implementation (exposed via pybind11) will exhibit lower matching latency than the Python `heapq` implementation. The speedup will increase with book depth due to memory locality and reduced allocation overhead.

### H3 — Systems Hypothesis
> In the full API request path, the language-level matching speedup will be attenuated by I/O and serialization overhead. The contribution of matching latency to total API latency will fall below a threshold where language rewrite is not the optimal optimization target.

## 3. System Architecture & Measurement Boundaries
Detailed System Overview is given in README.md if you want to dwell into the architectural tradeoffs and features , i will highly recommend the README.md, This is a brief overview of a request lifecycle in this distributed system.

First user logs in , django simpleJWT mints two token `access` and `refresh` token , at the time of login django queries the postgres table under core_lodger app specifically portfolio and position tables and load the `funds` and `positions` in the redis cache using `signal pattern` of django, then the user can goes to the route `/order` and puts an order either `SELL` or `BUY` now the way `/order` route is configuered it has dependency injection , it depends on `have_funds` function that checks the funds or positions seeded in the cache if the user has enough funds for thus trade , this function `have_funds` is further dependent on `is_Authenticated_user` which decrypts the JWT token and returns the `Authenticated_user` pydantic model consisting of `user_id and kyc`.
Further `have_funds` leverages the  redis watch , multi , exec and pipeline for optimistic locking and lock funds in the redis cache, `have_funds` is implemented with yield pattern this transforms the dependency into a generator , after the  order is matched it is pushed into the redis `executed_trade` with fire and persisit pattern , which django daemon `trade_registery` which is implemented through django custom commands picks the order up and check if the order has already settled in the postgres , if not the trade is settled recorded into the transaction , and positions and postfolio are updated and then if the order was executed at the lower price from the user locked price the locked funds are returned to it's portfolio.

Same is the flow for order deletion but for it tombstone deleteion is used , instead of deleting order at once it is marked as cancelled and when it is emerged on top it is gracefully skipped.
For more indepth architectural decisions and nuances i would refer you to the README.md


[Authentication jwt] → [Django using DRF and simpleJWT]
|
[Client] → [FastAPI /order]
├── JWT Decode (security.py)
├── have_funds (Redis WATCH/MULTI/EXEC)
├── OrderBook.add_order() + execute()
├── Trade Serialization (orjson)
└── Redis XADD (executed_trades_stream)
↓
[Django Daemon] → [PostgreSQL] → [XACK] → [settle_cache]

## 4. Experimental Methodology
In this section i will go over the experimental methodology and map out
**4.1- Independent Variables**
**4.2- Dependent Variables**
**4.3- Constant Variables**
**4.4- Environment & Infrastructure**

### 4.1- Independent Variables
These are the variables that be changing throughout the benchmarking.
|**variables**|**Levels**|**Constraints**|
|*Engine Implementation*|*Python* & *C++ with pybind11*|*C++ must use similar semantics and implementation*|
|*Orderbook Depth*|* 1k, 25k, 50k*|*Must be preseeded*|
|*Request Rate*|* 500,, 2k, 5k*|*use open model load*|

*Depth and rate will be measured in 3x3 matrix , it gives us 9-cell experimental matrix and multiplied with our third independent variable engine it will be 18-cell experimental matrix*

### 4.2- Dependent Variables
These are the variables which are our main concern , they will yield different values based on the variance of independent variables and they will form the result of this research

|**variables**|**Defination**|
|*Throughput*|*RPS at a specific latency threshold*|
|*Execution Time*|*Time taken by an order to be exxecuted algorithmically*|
|*API response latency*|*Total time required by a request including JWT and dependency resolution*|

### 4.3- Constant Vraiables
These are the variables that should remain constant throughout the experimentation

|**variables**|**why**|
|*Payload Schema*|*JSON size must remain constant*|
|*Order composition Ratio*|*Limit order / Market Order ratio shall remain constant for each phase*|
|*GC Collection State*|*Explicitly disabled for Phase 1 pure-engine tests; enabled for Phase 2 API tests*|

### 4.4 Environment & Infrastructure
To ensure reproducible latency measurements , all benchmarking are done on a dedicated local compute node.
Given the constraints of virtualizing on non-linux machines certain constraints and tunnings  were applied to mitigate this contraint.

#### 4.4.1 Hardware and OS and Software
Machine on which the benchmarking will be performed is equipped with
- *13th-generation Intel Core i7-1355U processor, featuring an asymmetric architecture of 10 physical cores (2 Performance cores, 8 Efficient cores) and 12 logical threads, operating at a base clock of 1.70 GHz*
- *8 GB of physical memory and a 512 GB Samsung NVMe Solid State Drive (MZAL8512HDLU-00BL2)*

OS and Docker configurations are
*Host OS & SubSystem Windows 11 Enterprise build number 26200.8875*

Full description of all the software dependencies and their versions can be found in requirements.txt of each service , major depenedencies and their versions are listed here 
- *python==3.14.4 (64-bit)*
- *C++ Toolchain: Container-native GCC compiler (Debian/Ubuntu default, typically v11.x or v12.x) utilizing -O3 -march=native release optimization flags and pybind11. (Note: Host-level MSYS2 Windows compilers were explicitly excluded to maintain Linux ABI compatibility).*
- *fastapi==0.139.0*
- *uvicorn==0.50.2*
- *pydantic==2.13.4*
- *Django==6.0.6*
- *djangorestframework==3.17.1*
- *psycopg2-binary==2.9.12*
- *PyJWT==2.13.0*
-*POSTGRESQL v16*

#### 4.4.2 Virtualization and Container Isolation
Because the host operating system is Windows, the microservice architecture is virtualized through Doccker dekstop leveraging windows subsystem for Linux.
To prevent latency spikes caused by docker moving the threads across cores during the benchmarking the containers are pinned to specific cores.
Containerized application and the containers for specific services are pinnned to specific cores.
**FastAPI & Engine:** *are pinned to performance cores for maximum performance and throughput*
**Redis and Djnago:** *are pinned to efficient cores to prevent them from stealinng resources from the performance cores and affecting the order matching and API latency*
**Load Generators** *are pinned to remaining core for isolated efficienncy*
**Memory Limits:** *Hard Memory constraints are added to docker to prevent it from exhasting the 8GB available memoryy completely which would trigger swapping and invalidating the memory latency*

#### 4.4.3 Network Constraints and optimization
Due to host machine being a Windows operating system , and limitation of docker on the windows the network directive `--network host` will not fully bypass the NAT (Network Address Translation).
Consequently the API response latency will include the network overhead.
To maximize the throughput with these constraints
- **File Descriptors:***The open file descriptor limit within the WSL2 kernel is elevated to 65,535 `(ulimit -n 65535)` to prevent socket exhaustion during peak Request Per Second (RPS) loads*

#### 4.4.4 Warm-up Protocol and Sampling
**Warm-Up Phase:** *Prior to recording telemetry for any experimental cell, an untimed warm-up load of 5,000 requests is executed. Data generated during this phase is explicitly discarded*
**Sample Size (N) and Duration:** *Each of the 18 experimental cells is executed across N = 5 independent test trials. To capture potential queue degradation , each trial sustains the target request rate for exactly 30 seconds.*
**Reset:** *Between individual trials, the memory state is cleared via Python explicit garbage collection (gc.collect()), Redis cache flush (FLUSHALL), and database transaction rollback to guarantee clean state of the memory, database and redis*

### Statistical Significance and Non parametric Testing
Due to the right-skewed nature of network latency, central tendencies will be compared using the non-parametric Mann-Whitney U test a = 0.05, and tail latencies p99 will be evaluated using bootstrapped 95% confidence intervals