import time
import gc
import orjson
import numpy as np
import os
import csv
from decimal import Decimal
import sys
import uuid

sys.path.append('/app/mitori_engine/core_cpp/build/') 
import mitori_engine_cpp

N_TRIALS = 5
PRECISION_MULTIPLIER = Decimal('100000000')

def load_json(filepath: str) -> list:
    """Reads and parses the JSON file entirely into memory using orjson."""
    with open(filepath, "rb") as f:
        return orjson.loads(f.read())

def log_raw_latencies_to_csv(filepath: str, tier_name: str, trial_num: int, latencies: list):
    """Writes all latencies to a CSV using a single block-write operation."""
    file_exists = os.path.isfile(filepath)
    rows_to_write = (
        [tier_name, trial_num, i, latency] 
        for i, latency in enumerate(latencies)
    )
    
    with open(filepath, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Depth_Tier", "Trial", "Request_Index", "Latency_ns"])
            
        writer.writerows(rows_to_write)

def log_to_csv(filepath: str, data_row: list):
    """Appends telemetry data to a CSV file, writing headers if it is a new file."""
    file_exists = os.path.isfile(filepath)
    with open(filepath, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Depth_Tier", "Trial", "P50_ns", "P99_ns", "Max_RPS", "start_depth", "end_depth"])
        writer.writerow(data_row)

def unbox_order_to_cpp_dict(raw_order: dict) -> dict:
    """Safely casts JSON strings, scales precision, splits UUIDs, and handles missing Order IDs."""
    parsed = raw_order.copy()
    
    if parsed.get("price") is not None:
        parsed["price"] = int(Decimal(str(parsed["price"])) * PRECISION_MULTIPLIER)
    else:
        parsed["price"] = 0
    if parsed.get("number_of_shares") is not None:
        parsed["number_of_shares"] = int(Decimal(str(parsed["number_of_shares"])) * PRECISION_MULTIPLIER)
    else:
        parsed["number_of_shares"] = 0
    if "order_id" in parsed and parsed["order_id"]:
        order_uuid_int = uuid.UUID(parsed["order_id"]).int
        order_id_high = order_uuid_int >> 64
        order_id_low = order_uuid_int & ((1 << 64) - 1)
    else:
        order_id_high = 0
        order_id_low = 0
        
    owner_uuid_int = uuid.UUID(parsed["order_owner_id"]).int
    owner_id_high = owner_uuid_int >> 64
    owner_id_low = owner_uuid_int & ((1 << 64) - 1)
    
    side_enum = mitori_engine_cpp.Side.BUY if parsed['side'] == 'buy' else mitori_engine_cpp.Side.SELL
    type_enum = mitori_engine_cpp.Type.LIMIT if parsed['type'] == 'limit' else mitori_engine_cpp.Type.MARKET
    
    return {
        "order_id_high": order_id_high,
        "order_id_low": order_id_low,
        "order_owner_id_high": owner_id_high,
        "order_owner_id_low": owner_id_low,
        "side": side_enum,
        "type": type_enum,
        "is_canceled": str(parsed.get('is_canceled', 'False')).lower() == 'true',
        "price": parsed["price"],
        "number_of_shares": parsed["number_of_shares"],
        "max_authorized_funds": None
    }

def run_benchmark_for_tier(tier_name: str, seed_file_path: str, raw_active_stream: list, csv_filename: str):
    print(f"\n--- Starting C++ Micro-Benchmark for {tier_name} Depth ({N_TRIALS} Trials) ---")
    
    trial_p50s = []
    trial_p99s = []
    trial_rps = []
    
    resting_orders = load_json(seed_file_path)
    cpp_resting_orders = [unbox_order_to_cpp_dict(o) for o in resting_orders]
    
    active_stream = [unbox_order_to_cpp_dict(o) for o in raw_active_stream]
    num_timing_orders = len(active_stream) - 5000
    
    for trial in range(1, N_TRIALS + 1):
        engine = mitori_engine_cpp.OrderBook('AAPL')
        
        for o in cpp_resting_orders:
            engine.process_order(
                o["order_id_high"], o["order_id_low"],
                o["order_owner_id_high"], o["order_owner_id_low"],
                o["side"], o["type"], o["is_canceled"],
                o["price"], o["number_of_shares"],
                o["max_authorized_funds"]
            )
            
        start_depth = engine.get_book_depth() 
        
        gc.disable()
        
        t_start = time.perf_counter()
        latencies_ns = engine.benchmark_batch(active_stream, 5000)
        t_end = time.perf_counter()
        
        gc.enable()
        
        end_depth = engine.get_book_depth() 
        
        print(f"    [Drift Check] Start Depth: {start_depth:,} | End Depth: {end_depth:,} | Drift: +{end_depth - start_depth:,}")
        
        wall_clock_time_s = t_end - t_start
        max_rps = num_timing_orders / wall_clock_time_s
        
        p50 = np.percentile(latencies_ns, 50)
        p99 = np.percentile(latencies_ns, 99)
        
        trial_p50s.append(p50)
        trial_p99s.append(p99)
        trial_rps.append(max_rps)
        
        print(f"  Trial {trial}/{N_TRIALS} -> P50: {p50:,.0f} ns | P99: {p99:,.0f} ns | RPS: {max_rps:,.0f}")
        
        log_to_csv(csv_filename, [tier_name, trial, p50, p99, max_rps, start_depth, end_depth])
        
        raw_csv_filename = csv_filename.replace(".csv", "_RAW.csv")
        log_raw_latencies_to_csv(raw_csv_filename, tier_name, trial, latencies_ns)
        
        del engine
        mitori_engine_cpp.cleanup_memory()
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

    timestamp = int(time.time())
    csv_filename = f"benchmark/data/cpp_baseline_{timestamp}.csv"
    
    tiers = [
        ("1k", "benchmark/data/seed_1k.json"),
        ("25k", "benchmark/data/seed_25k.json"),
        ("50k", "benchmark/data/seed_50k.json")
    ]
    
    for tier_name, filepath in tiers:
        run_benchmark_for_tier(tier_name, filepath, raw_active_stream, csv_filename)
        
if __name__ == "__main__":
    main()