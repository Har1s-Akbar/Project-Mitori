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
|*Orderbook Depth*|*100, 1k, 10k, 25k, 50k*|*Must be preseeded*|
|*Request Rate*|*100, 500, 1k , 2k, 5k*|*use open model load*|

*Depth and rate will be measured in 2x2 matrix , [low,low low,high high,low high,high]*

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
Experimental environment and infrastructure are really important for the proper result of an experiment , faulty or broken environment can pollute the results of an experiment.

#### General Configuration
These are general configurations , before testing proper and exact environment details will be mentioned
*1- Benchmarking will be done on local machine no cloud service will be used*
*2- Benchmarking will be done in docker and for it docker will be configuered accordingly*
*-Containers wil be pinned to CPU cores to limit and avoid linux scheduler from moving threads across available cores to avoid unintentional letency overhead*
*3-Docker default bridge network routes all traffic through NAT adding measurable network laatency to every api call, it will be configuered as well*
