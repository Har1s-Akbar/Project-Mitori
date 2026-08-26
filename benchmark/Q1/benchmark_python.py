import time
import gc
import orjson
import numpy as np
import os
import csv
import concurrent.futures
from decimal import Decimal

from mitori_engine.core_python.engine import OrderBook
from mitori_engine.core_python.models import Order

N_TRIALS = 5
PRECISION_MULTIPLIER = Decimal('100000000')
TARGET_RPS_PER_THREAD = 10000
WARMUP_COUNT = 5000
DURATION_SEC = 30
THREADS = [1, 2, 4]

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

def q1_worker(engine: OrderBook, orders: list) -> tuple[np.ndarray, np.ndarray, int]:
    """Injects at 10k RPS and records independent service/queue latencies."""
    interval_ns = 1_000_000_000 // TARGET_RPS_PER_THREAD
    
    # Warmup
    for order in orders[:WARMUP_COUNT]:
        engine.process_order(order)
        
    measurement_orders = orders[WARMUP_COUNT:]
    num_orders = len(measurement_orders)
    
    service_times = np.zeros(num_orders, dtype=np.int64)
    queue_times = np.zeros(num_orders, dtype=np.int64)
    
    process = engine.process_order
    start_wall = time.perf_counter_ns()
    
    processed_count = 0
    for i in range(num_orders):
        order = measurement_orders[i]
        expected_arrival = start_wall + (i * interval_ns)
        
        while time.perf_counter_ns() < expected_arrival:
            pass
            
        arrival_time = time.perf_counter_ns()
        process(order)
        completion_time = time.perf_counter_ns()
        
        service_times[i] = completion_time - arrival_time
        queue_times[i] = completion_time - expected_arrival
        processed_count += 1
        
        if (completion_time - start_wall) > (DURATION_SEC * 1_000_000_000):
            break
            
    return service_times[:processed_count], queue_times[:processed_count], processed_count

def run_q1_matrix():
    print("Loading 350000 active stream orders...")
    raw_active_stream = load_json("benchmark/data/data_for_test/active_stream_for_q1.json")
    active_stream = [unbox_order(order) for order in raw_active_stream]
    
    csv_filename = f"benchmark/data/python_test_data/python_q1_throughput_{int(time.time())}.csv"
    
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
                    futures = [executor.submit(q1_worker, engine, active_stream) for _ in range(thread_count)]
                    results = [f.result() for f in concurrent.futures.as_completed(futures)]
                
                # Aggregate results across threads
                all_service = np.concatenate([r[0] for r in results])
                all_queue = np.concatenate([r[1] for r in results])
                total_processed = sum(r[2] for r in results)
                
                max_rps = total_processed / DURATION_SEC
                s_p50, s_p99 = np.percentile(all_service, 50), np.percentile(all_service, 99)
                q_p50, q_p99 = np.percentile(all_queue, 50), np.percentile(all_queue, 99)
                
                print(f" Trial {trial}/5 -> RPS: {max_rps:,.0f} | Q-P99: {q_p99:,.0f} ns | S-P50: {s_p50:,.0f} ns")
                log_q1_to_csv(csv_filename, [tier_name, thread_count, trial, max_rps, s_p50, s_p99, q_p50, q_p99])
                
                del engine
                gc.collect()

if __name__ == "__main__":
    run_q1_matrix()