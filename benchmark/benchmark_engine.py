import time
import gc
import orjson
import numpy as np
import os
import csv
from decimal import Decimal

from mitori_engine.core.engine import OrderBook
from mitori_engine.core.models import Order

N_TRIALS = 5

def load_json(filepath: str) -> list:
    """Reads and parses the JSON file entirely into memory using orjson."""
    with open(filepath, "rb") as f:
        return orjson.loads(f.read())


def log_raw_latencies_to_csv(filepath: str, tier_name: str, trial_num: int, latencies: np.ndarray):
    """Appends all 195,000 individual request latencies to a raw distribution CSV."""
    file_exists = os.path.isfile(filepath)
    
    with open(filepath, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Depth_Tier", "Trial", "Request_Index", "Latency_ns"])
        for i, latency in enumerate(latencies):
            writer.writerow([tier_name, trial_num, i, latency])

def log_to_csv(filepath: str, data_row: list):
    """Appends telemetry data to a CSV file, writing headers if it is a new file."""
    file_exists = os.path.isfile(filepath)
    with open(filepath, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Depth_Tier", "Trial", "P50_ns", "P99_ns", "Max_RPS"])
        writer.writerow(data_row)

def unbox_order(raw_order: dict) -> Order:
    """Safely casts JSON strings to Decimals and instantiates the Order object."""
    # Create a copy so we don't mutate the original loaded data
    parsed_order = raw_order.copy()
    
    if parsed_order.get("price") is not None:
        parsed_order["price"] = Decimal(str(parsed_order["price"]))
        
    if parsed_order.get("number_of_shares") is not None:
        parsed_order["number_of_shares"] = Decimal(str(parsed_order["number_of_shares"]))
        
    return Order(**parsed_order)

def execute_trial(engine: OrderBook, active_stream: list, trial_num: int) -> np.ndarray:
    """Executes a single benchmark trial, locking GC and returning latency array."""
    
    warmup_orders = active_stream[:5000]
    for order in warmup_orders:
        engine.process_order(order)
        
    timing_orders = active_stream[5000:]
    num_timing_orders = len(timing_orders)
    
    latencies_ns = np.zeros(num_timing_orders, dtype=np.int64)
    start_depth = len(engine.bid) + len(engine.ask)

    gc.disable()
    
    for i in range(num_timing_orders):
        order = timing_orders[i]
        
        start = time.perf_counter_ns()
        engine.process_order(order)
        end = time.perf_counter_ns()
        
        latencies_ns[i] = end - start
        
    gc.enable()

    end_depth = len(engine.bid) + len(engine.ask)
    print(f"    [Drift Check] Start Depth: {start_depth:,} | End Depth: {end_depth:,} | Drift: +{end_depth - start_depth:,}")
    
    return latencies_ns

def run_benchmark_for_tier(tier_name: str, seed_file_path: str, raw_active_stream: list, csv_filename:str):
    print(f"\n--- Starting Micro-Benchmark for {tier_name} Depth ({N_TRIALS} Trials) ---")
    
    trial_p50s = []
    trial_p99s = []
    trial_rps = []
    
    resting_orders = load_json(seed_file_path)
    num_timing_orders = len(raw_active_stream) - 5000
    
    for trial in range(1, N_TRIALS + 1):

        engine = OrderBook('APP')
        
        for order in resting_orders:
            order_object = unbox_order(order)
            engine.process_order(order_object)

        active_stream = [unbox_order(order) for order in raw_active_stream]
        
        latencies_ns = execute_trial(engine, active_stream, trial)
        
        total_time_s = np.sum(latencies_ns) / 1e9
        max_rps = num_timing_orders / total_time_s
        p50 = np.percentile(latencies_ns, 50)
        p99 = np.percentile(latencies_ns, 99)
        
        trial_p50s.append(p50)
        trial_p99s.append(p99)
        trial_rps.append(max_rps)
        
        print(f"  Trial {trial}/{N_TRIALS} -> P50: {p50:,.0f} ns | P99: {p99:,.0f} ns | RPS: {max_rps:,.0f}")
        
        log_to_csv(csv_filename, [tier_name, trial, p50, p99, max_rps])
        
        raw_csv_filename = csv_filename.replace(".csv", "_RAW.csv")
        log_raw_latencies_to_csv(raw_csv_filename, tier_name, trial, latencies_ns)

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
    raw_active_stream = load_json("benchmark/data/active_stream.json")

    # active_stream = [unbox_order(order) for order in raw_active_stream]

    timestamp = int(time.time())
    csv_filename = f"benchmark/data/python_baseline_{timestamp}.csv"
    
    tiers = [
        ("1k", "benchmark/data/seed_1k.json"),
        ("25k", "benchmark/data/seed_25k.json"),
        ("50k", "benchmark/data/seed_50k.json")
    ]
    
    for tier_name, filepath in tiers:
        run_benchmark_for_tier(tier_name, filepath, raw_active_stream, csv_filename)
        
if __name__ == "__main__":
    main()
