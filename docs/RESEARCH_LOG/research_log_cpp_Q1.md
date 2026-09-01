# Throughput, Service, and Queue Residence Time of the CPP Engine Analyzed: Picking up Noise and Anomalies

**Date:** `[01/09/2026]`  
**Author:** `[Haris Ahmad]`

>**Rule:** In this document we will log every run, analyzing and finding the flaw inside each benchmarking run and  trying to fix it properly.

## Methodology and Expectation
The methodology for the benchmarking is simple. It follows 3 order book depths [1k, 25k, 50k] with three thread counts [1, 2, 4], creating a 3x3 matrix. Each trial runs for a duration of 30 seconds with an injection rate of 600k orders per second, initial determined injection rate for python and CPP engine was 10k but since python engine Throughput baselined and GIL chocked for 600k order injection , for CPP engine 600k order injection is chosen from the get go.

The expected result for the CPP engine is that Throughput will scale with the increase in the number of threads , mimicking a linear relationship between throughput and number of threads. This is because of the Python GIL (Global Interpreter Lock) being dropped at the start of the benchmarking phase, but there is another caveat which is conserving cpp Orderbook from the thread mutation , once GIL is dropped , threads are not being executed sequentially so the chances of orderbook being targeted by the multithread state mutation during the benchmarking is certain , so `mutex` is implemented to lock the orderbook when it is being accessed by one thread so that no other thread can access it and corrupt the state.
The Tax of `mutex` is, when one thread is accessing and mutating the orderbook and another thread arrives to access the orderbook , `OS` puts that thread to sleep until that thread concludes it's work only after then `OS` wakes up the sleeping thread which takes approximately 150-200 nanoseconds, causing massive stall between the benchmarking.

In a way , GIL is released but we implemented mutex to lock the state of the orderbook.

All in all the expectations are:
- **Increased Throughput Scaling:** Linear Scaling of Throughput
| Threads | Expected Throughput RPS |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** |  600k |
| **2** |  ~1.2m |
| **4** | | ~2.4m |

- **Service time Remaining Constant:** Service Time Latencies will remain constant despite the increase in threads.
- **Queue Residence Time scaling:** Queue Residence Time will explode but will remain well under python benchmarked Queue Residence time and latencies.

## First Benchmarkings (Ran - August 31st)
First Benchmarkings ran for 30s and n=5 for each trial, even tho exhibited a constant throughput at 1 thread and scaled at the addition of 2 threads but throughput collapsed violently under the addition of 4 threads 
| Depth_Tier | Threads | Trials | Avg_Throughput_RPS | Avg_Service_P50_ns | Avg_Service_P99_ns | Avg_Queue_P50_ns | Avg_Queue_P99_ns |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1k** | 1 | 5 | 575,627 | 11,161 | 11,161 | 11,411 | 11,411 |
| **1k** | 2 | 5 | 840,431 | 732,046 | 1,150,336 | 732,269 | 1,150,593 |
| **1k** | 4 | 5 | 724,163 | 41,915 | 136,027 | 42,039 | 136,192 |
| **25k** | 1 | 5 | 600,329 | 14,029 | 14,029 | 14,175 | 14,175 |
| **25k** | 2 | 5 | 972,334 | 15,908,704 | 15,918,471 | 15,908,904 | 15,918,657 |
| **25k** | 4 | 5 | 696,698 | 49,556 | 432,454 | 49,723 | 432,607 |
| **50k** | 1 | 5 | 591,734 | 55,165 | 55,165 | 55,383 | 55,383 |
| **50k** | 2 | 5 | 870,548 | 100,756 | 112,045 | 100,871 | 112,182 |
| **50k** | 4 | 5 | 633,565 | 113,241 | 4,910,474 | 113,380 | 4,910,705 |


### Theoretical vs. Actual Throughput Analysis
**Methodology:** The baseline expected throughput is calculated by defining a single thread's target processing capacity (600,000 RPS) as 100% efficiency. Linear scaling expectations (e.g., 2 threads = 1.2M RPS) are then compared against the actual empirical throughput to calculate the exact degradation caused by OS-level lock contention.

| Depth_Tier | Threads | Expected_Throughput | Actual_Throughput | Throughput_Lost_RPS | %_Achieved | %_Lost_Degradation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1k** | 1 | 600,000 | 575,627 | 24,373 | 95.9% | 4.1% |
| **1k** | 2 | 1,200,000 | 840,431 | 359,569 | 70.0% | 30.0% |
| **1k** | 4 | 2,400,000 | 724,163 | 1,675,837 | 30.2% | **69.8%** |
| **25k** | 1 | 600,000 | 600,329 | -329 | 100.1% | 0.0% |
| **25k** | 2 | 1,200,000 | 972,334 | 227,666 | 81.0% | 19.0% |
| **25k** | 4 | 2,400,000 | 696,698 | 1,703,302 | 29.0% | **71.0%** |
| **50k** | 1 | 600,000 | 591,734 | 8,266 | 98.6% | 1.4% |
| **50k** | 2 | 1,200,000 | 870,548 | 329,452 | 72.5% | 27.5% |
| **50k** | 4 | 2,400,000 | 633,565 | 1,766,435 | 26.4% | **73.6%** |

#### Flaws
* **Latency Equivalency:** The latecny equivaleny is caused by the benchmarking measuring the service time before acquiring the mutex lock , that is why service latency is equivalent to the queue residence latency
*   **The Contention Tax:** Adding a second thread results in an immediate ~20% to 30% loss in total computational efficiency across all depth tiers.
*   **The 4-Thread Collapse:** At 4 threads (2.4M target RPS), the `std::mutex` queue becomes so severely backlogged that the system bleeds ~1.7 million requests per second. At the 50k depth tier, **73.6%** of theoretical processing power is entirely lost to Linux kernel-space context switching, and mutex collision of threads.

## C++ benchmarking and Memory Exhaustion
During the multi-threaded Q1 Benchmarking (30-second duration, 1.2M+ RPS), C++ matching engine suffered container crashes, yielding `SIGKILL 89` (Linux Out-Of-Memory Killer). On the other hand equivalent Python implementation survived similar benchmarking without exhausting memory limits. 

This section explores why a highly optimized C++ architecture fell victim to memory exhaustion, proving that the crash was not caused by a memory leak, but by a collision between **extreme computational velocity** and **dynamic contiguous memory reallocation**, **Massive Memory footprint of c++ Telemetry**, **Python Order Stream Dictionary Overhead**.


## Computational Velocity
The fundamental reason Python survived the 30-second benchmark while C++ crashed is rooted in execution speed. Python did not manage memory better; it was simply rate-limited by its own architecture.

*   **The Python Bottleneck:** Python's Global Interpreter Lock (GIL), dynamic typing overhead, and dictionary boxing restricted the system's processing speed. It physically could not inject and process enough orders within 30 seconds to reach the Docker container's RAM ceiling. It was CPU-bound long before it could become RAM-bound.
*   **The C++ Velocity:** The C++ engine, utilizing an `ArenaAllocator` and direct memory pointers, matched orders in under 600 nanoseconds. Stripped of language overhead, the threads easily injected and processed upwards of 18 million orders per thread and multiplied for each increment in thread(Tho the degradation in throughput happens but even beyond the degradation a the worst case scenario 4 threaded engine was still matching 18  million orders per trial). This extreme velocity allowed the C++ engine to rapidly fill gigabytes of memory, shifting the bottleneck directly from the CPU to the RAM.

The actual trigger for the `SIGKILL 89` was the mechanical behavior of the C++ Standard Library, specifically `std::vector`, under massive scale.

### The Contiguous Memory Requirement
Standard vectors (such as your `metadata_vault` and the underlying structures in your `ArenaAllocator`) guarantee that all elements are stored in a single, unbroken block of RAM. This is optimal for CPU cache-locality but dangerous for high-scale dynamic growth.

### Memory Allocation Factor
When a `std::vector` runs out of space, it automatically allocates a new memory block. By default, C++ compilers (like GCC and Clang) use a **2x growth multiplier**. If the vector holds 16 million elements and needs to add one more, it requests a new block capable of holding 32 million elements.

### Memory Footprint Disaster 
The Out-Of-Memory termination occurs during the exact microsecond the vector resizes:
1.  **State A:** The contiguous block of memory is full. (2 GB of RAM space in docker container is utilized).
2.  **State B :** C++ requests the new 2x block from the OS. Before the old block can be deleted, the new block must be created and the data copied over. For a fraction of a second, both blocks exist simultaneously a massive memroy overhead surpassing the limitation of the docker container exists. 
3.  **The Math:** 2 GB + 4 GB = **6 GB Total memory footprint**.
4.  **The Kill:** This massive, instantaneous 6 GB surge breaches the Docker memory limits. The Linux Kernel steps in to protect the host OS, intercepting the page fault and immediately terminating the process with `SIGKILL 89`.

### Masssive c++ Telemetry
for the `benchmark_closed_loop` a massive telemetry of c++ std::vector<uint64_t> was being returned to the python and those vectors where being intercepted by the `<pybind11/stl.h>` to compensate the python lacking `vector` data type , and calls pyList_New wrapping each 64 bit integer into a memory heavy byte size pyObject.

### Python Order Stream Dictionary Overhead
When a stream of 600k orders is being passed to c++ binding where each order is a py::dict , a massive overhead and memory is occupied by these orders and when each order is being sequentially type casted , it creates a massive spike in memory consumption and directly playing a part in the termination of the benchmarking 

### Solution
To make this engine capable of benchmarking millions of orders within a Docker container, we must completely eliminate standard Python lists and dictionaries from the binding boundary. We need to implement the Python Buffer Protocol using Pybind11's `<pybind11/numpy.h>`
`Zero Copy Numpy Architecture` which will eliminate the pre-existing orders in memory being copied from python objects to c++ complient datasets and arrays, this architecture will directly share the direct memory pointers and it will keep the memory footprint in check and minimizaing the memory consumption by bad code and Docker Memory is also increased from `2GBs` to `4GBs`

#### Phase 1: Python Columnar Serialization (`benchmark_cpp.py`)
Standard Python objects (dictionaries, strings) are excessively heavy and cannot be efficiently deserialized by C++ at high frequencies. The `stream_to_numpy_dict` function converts row-based JSON into heavily typed, contiguous 1D NumPy arrays (a columnar format).

*   **UUID Bit-Shifting (128-bit to 64-bit):** NumPy does not natively support 128-bit integers. The script parses the UUID string, converts it to an integer, and splits it into two 64-bit halves using bitwise shifts:
    ```python
    order_uuid_int = uuid.UUID(parsed["order_id"]).int
    oid_h[i] = order_uuid_int >> 64
    oid_l[i] = order_uuid_int & ((1 << 64) - 1)
    ```
*   **Floating Point Elimination:** To avoid floating-point precision loss and heavy C++ casting, prices and shares are multiplied by `PRECISION_MULTIPLIER` (10^8) and cast directly to `np.uint64`.
*   **The Result:** The payload passed to Pybind11 is not a list of objects, but a dictionary of pre-allocated C-style arrays resting directly in RAM.

#### Phase 2: C++ Pointer Extraction & Exact Reservation (`bindings.cpp`)
When `benchmark_closed_loop` receives the NumPy dict, it does not use Pybind11's default object translation, which would copy the data and inflate memory.

*   **Zero-Copy Pointer Access:** 
    ```cpp
    auto arr_price = numpy_orders["price"].cast<py::array_t<uint64_t>>().unchecked<1>();
    ```
    The `.unchecked<1>()` directive disables all bounds-checking and Python API safety rails, returning a raw, bare-metal C++ pointer directly into Python's memory space.

*   **Preventing the OOM Spike (`std::vector::reserve`):**
    To pull the NumPy data into a contiguous C++ cache struct (`RawOrderData`), the engine executes an exact memory reservation:
    ```cpp
    size_t num_orders = arr_oid_h.shape(0);
    std::vector<RawOrderData> active_stream_cache;
    active_stream_cache.reserve(num_orders);
    ```
    By reserving `num_orders` upfront, the C++ vector is allocated exactly once. This explicitly prevents the C++ 2x doubling behavior, neutralizing the root cause of the previous OOM crashes during the cache-loading phase.

*   **128-bit Reconstruction:** As the loop copies data into the `active_stream_cache`, it reconstructs the UUIDs natively using a bitwise OR:
    ```cpp
    raw.full_order_id = (static_cast<unsigned __int128>(arr_oid_h(i)) << 64) | arr_oid_l(i);
    ```

