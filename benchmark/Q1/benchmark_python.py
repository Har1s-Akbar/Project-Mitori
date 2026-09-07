import time
import gc
import orjson
import numpy as np
import os
import csv
import concurrent.futures
import pandas as pd
from decimal import Decimal

from mitori_engine.core_python.engine import OrderBook
from mitori_engine.core_python.models import Order

N_TRIALS = 5
PRECISION_MULTIPLIER = Decimal('100000000')
TARGET_RPS_PER_THREAD = 600000
WARMUP_COUNT = 50000
DURATION_SEC = 30
THREADS = [1, 2, 4]

RING_BUFFER_SIZE = 600000

def load_json(filepath: str) -> list:
    with open(filepath, "rb") as f:
        return orjson.loads(f.read())

def unbox_order(raw_order: dict) -> Order:
    parsed_order = raw_order.copy()
    if parsed_order.get("price") is not None:
        parsed_order["price"] = int(Decimal(str(parsed_order["price"])) * PRECISION_MULTIPLIER)
    if parsed_order.get("number_of_shares") is not None:
        parsed_order["number_of_shares"] = int(Decimal(str(parsed_order["number_of_shares"])) * PRECISION_MULTIPLIER)
    return Order(**parsed_order)

def log_q1_to_csv(filepath: str, data_row: list):
    file_exists = os.path.isfile(filepath)
    with open(filepath, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Depth", "Threads", "Trial", "Throughput_RPS", "Service_P50_ns", "Service_P99_ns", "Queue_P50_ns", "Queue_P99_ns"])
        writer.writerow(data_row)

def log_raw_q1_parquet(base_folder: str, depth: str, threads: int, trial: int, thread_id: int, service_arr: np.ndarray, queue_arr: np.ndarray):
    """Saves thread telemetry as a highly compressed binary Parquet chunk."""
    os.makedirs(base_folder, exist_ok=True)
    num_rows = len(service_arr)
    
    df = pd.DataFrame({
        "Depth": depth,
        "Threads": threads,
        "Trial": trial,
        "Thread_ID": thread_id,
        "Request_Index": np.arange(num_rows, dtype=np.int32),
        "Service_Latency_ns": service_arr,
        "Queue_Latency_ns": queue_arr
    })

    df["Depth"] = df["Depth"].astype("category")
    df["Threads"] = df["Threads"].astype(np.int8)
    df["Trial"] = df["Trial"].astype(np.int8)
    df["Thread_ID"] = df["Thread_ID"].astype(np.int8)

    filename = f"{base_folder}/tier_{depth}_th_{threads}_tr_{trial}_id_{thread_id}.parquet"
    df.to_parquet(filename, engine='pyarrow', compression='snappy', index=False)
def log_snapshots_to_csv(filepath: str, depth: str, threads: int, trial: int, snapshots: np.ndarray, count: int):
    file_exists = os.path.isfile(filepath)
    with open(filepath, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Depth", "Threads", "Trial", "Elapsed_Sec", "Bids_Count", "Asks_Count"])
            
        for i in range(count):
            writer.writerow([
                depth, 
                threads, 
                trial, 
                snapshots[i, 0], 
                snapshots[i, 1], 
                snapshots[i, 2]  
            ])

def q1_worker(engine: OrderBook, orders: list, thread_id:int) -> tuple[np.ndarray, np.ndarray, int, np.ndarray, int, int]:
    """Injects at 10k RPS and records independent service/queue latencies."""
    gc.disable()

    interval_ns = 1_000_000_000 // TARGET_RPS_PER_THREAD
    buffer_size = len(orders)
    
    for order in range(WARMUP_COUNT):
        engine.process_order(orders[order% buffer_size])

    max_expected_orders = int(TARGET_RPS_PER_THREAD*DURATION_SEC*1.1)

    service_times = np.zeros(max_expected_orders, dtype=np.int64)
    queue_times = np.zeros(max_expected_orders, dtype=np.int64)

    process = engine.process_order
    start_wall = time.perf_counter_ns()

    end_wall = start_wall + (DURATION_SEC *  1_000_000_000)
    processed_count = 0

    total_snapshots = int(DURATION_SEC/3 +2)
    snapshot_array = np.zeros((total_snapshots,3),dtype=np.int64)

    snapshot_interval = 3 * 1_000_000_000

    next_snapshot = start_wall + snapshot_interval
    snapshot_index = 0
    
    while time.perf_counter_ns() < end_wall:
        if processed_count >= max_expected_orders:
            break
        current_time = time.perf_counter_ns()
        if current_time >= next_snapshot and snapshot_index < total_snapshots:
            snapshot_array[snapshot_index, 0] = (current_time - start_wall) // 1_000_000_000
            snapshot_array[snapshot_index, 1] = len(engine.bid)
            snapshot_array[snapshot_index, 2] = len(engine.ask)
            
            snapshot_index += 1
            next_snapshot += snapshot_interval

        order_idx = (WARMUP_COUNT + processed_count) % buffer_size
        order = orders[order_idx]
        
        expected_arrival = start_wall + (processed_count * interval_ns)
        
        while time.perf_counter_ns() < expected_arrival:
            pass        
        
        arrival_time = time.perf_counter_ns()
        process(order)
        completion_time = time.perf_counter_ns()
        
        service_times[processed_count] = completion_time - arrival_time
        queue_times[processed_count] = completion_time - expected_arrival
        processed_count += 1
            
    gc.enable()
            
    return service_times[:processed_count], queue_times[:processed_count], processed_count, snapshot_array, snapshot_index, thread_id

def run_q1_matrix():
    print("Loading active stream orders...")
    raw_active_stream = load_json("benchmark/data/data_for_test/active_stream_for_q1.json")
    active_stream = [unbox_order(order) for order in raw_active_stream[:RING_BUFFER_SIZE]]
    
    timestamp = int(time.time())
    csv_filename = f"benchmark/data/python_test_data/python_q1_throughput_{timestamp}.csv"
    snapshot_csv = f"benchmark/data/python_test_data/python_q1_snapshots_{timestamp}.csv"
    parquet_folder = f"benchmark/data/python_test_data/python_q1_raw_parquet_{timestamp}"
    
    tiers = [
        ("1k", "benchmark/data/data_for_test/seed_1k.json"),
        ("25k", "benchmark/data/data_for_test/seed_25k.json"),
        ("50k", "benchmark/data/data_for_test/seed_50k.json")
    ]
    
    for tier_name, seed_path in tiers:
        print(f"\n========== PREPARING TIER: {tier_name} ==========")
        resting_orders = [unbox_order(o) for o in load_json(seed_path)]
        
        for thread_count in THREADS:
            print(f"\n--- Testing Depth: {tier_name} | Threads: {thread_count} ---")
            
            for trial in range(1, N_TRIALS + 1):
                engine = OrderBook('APP')
                for order in resting_orders:
                    engine.process_order(order)
                
                gc.collect()
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count) as executor:
                    futures = [executor.submit(q1_worker, engine, active_stream, i) for i in range(thread_count)]
                    results = [f.result() for f in concurrent.futures.as_completed(futures)]
                
                all_service = np.concatenate([r[0] for r in results])
                all_queue = np.concatenate([r[1] for r in results])
                total_processed = sum(r[2] for r in results)
                
                max_rps = total_processed / DURATION_SEC
                s_p50, s_p99 = np.percentile(all_service, 50), np.percentile(all_service, 99)
                q_p50, q_p99 = np.percentile(all_queue, 50), np.percentile(all_queue, 99)
                thread_0_snapshots = results[0][3]
                thread_0_snap_count = results[0][4]

                print(f" Trial {trial}/5 -> RPS: {max_rps:,.0f} | Q-P99: {q_p99:,.0f} ns | S-P50: {s_p50:,.0f} ns")
                log_q1_to_csv(csv_filename, [tier_name, thread_count, trial, max_rps, s_p50, s_p99, q_p50, q_p99])
                log_snapshots_to_csv(snapshot_csv, tier_name, thread_count, trial, thread_0_snapshots, thread_0_snap_count)
                
                for res in results:
                    t_service = res[0]
                    t_queue = res[1]
                    t_id = res[5]
                    log_raw_q1_parquet(parquet_folder, tier_name, thread_count, trial, t_id, t_service, t_queue)
                
                del engine
                gc.collect()

if __name__ == "__main__":
    run_q1_matrix()