import time
import gc
import orjson
import numpy as np

# TODO: Adjust this import to match your exact class name in mitori_engine/core/engine.py
from mitori_engine.core.engine import OrderBook

# Number of experimental trials per tier (Sec 4.4.4 Compliance)
N_TRIALS = 5

def load_json(filepath: str) -> list:
    """Reads and parses the JSON file entirely into memory using orjson."""
    with open(filepath, "rb") as f:
        return orjson.loads(f.read())

def execute_trial(engine: OrderBook, active_stream: list, trial_num: int) -> np.ndarray:
    """Executes a single benchmark trial, locking GC and returning latency array."""
    
    warmup_orders = active_stream[:5000]
    for order in warmup_orders:
        engine.process_order(order)
        
    timing_orders = active_stream[5000:]
    num_timing_orders = len(timing_orders)
    
    latencies_ns = np.zeros(num_timing_orders, dtype=np.int64)
    
    gc.disable()
    
    for i in range(num_timing_orders):
        order = timing_orders[i]
        
        start = time.perf_counter_ns()
        engine.process_order(order)
        end = time.perf_counter_ns()
        
        latencies_ns[i] = end - start
        
    gc.enable()
    
    return latencies_ns

def run_benchmark_for_tier(tier_name: str, seed_file_path: str, active_stream: list):
    print(f"\n--- Starting Micro-Benchmark for {tier_name} Depth ({N_TRIALS} Trials) ---")
    
    trial_p50s = []
    trial_p99s = []
    trial_rps = []
    
    resting_orders = load_json(seed_file_path)
    num_timing_orders = len(active_stream) - 5000
    
    for trial in range(1, N_TRIALS + 1):
        engine = OrderBook()
        
        for order in resting_orders:
            engine.process_order(order)
            
        latencies_ns = execute_trial(engine, active_stream, trial)
        
        total_time_s = np.sum(latencies_ns) / 1e9
        max_rps = num_timing_orders / total_time_s
        p50 = np.percentile(latencies_ns, 50)
        p99 = np.percentile(latencies_ns, 99)
        
        trial_p50s.append(p50)
        trial_p99s.append(p99)
        trial_rps.append(max_rps)
        
        print(f"  Trial {trial}/{N_TRIALS} -> P50: {p50:,.0f} ns | P99: {p99:,.0f} ns | RPS: {max_rps:,.0f}")
        
        del engine
        del latencies_ns
        gc.collect() 
        
    avg_p50 = np.mean(trial_p50s)
    avg_p99 = np.mean(trial_p99s)
    avg_rps = np.mean(trial_rps)
    
    print(f"\n[FINAL AGGREGATED RESULTS: {tier_name} DEPTH (N={N_TRIALS})]")
    print(f"  -> Avg Max Throughput:  {avg_rps:,.2f} RPS")
    print(f"  -> Avg Median (P50):    {avg_p50:,.0f} ns")
    print(f"  -> Avg Tail (P99):      {avg_p99:,.0f} ns\n")

def main():
    print("Loading 200,000 active stream orders into memory...")
    active_stream = load_json("benchmark/data/active_stream.json")
    
    tiers = [
        ("1k", "benchmark/data/seed_1k.json"),
        ("25k", "benchmark/data/seed_25k.json"),
        ("50k", "benchmark/data/seed_50k.json")
    ]
    
    for tier_name, filepath in tiers:
        run_benchmark_for_tier(tier_name, filepath, active_stream)
        
if __name__ == "__main__":
    main()