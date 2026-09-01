import time
import gc
import orjson
import numpy as np
import os
import csv
from decimal import Decimal
import uuid
import concurrent.futures
import sys

sys.path.append('/app/mitori_engine/core_cpp/build/') 
import mitori_engine_cpp

N_TRIALS = 6
PRECISION_MULTIPLIER = Decimal('100000000')
TOTAL_TARGET_RPS = 600_000
DURATION_SEC = 28
THREAD_COUNTS = [1,2, 4]

def load_json(filepath: str) -> list:
    with open(filepath, "rb") as f:
        return orjson.loads(f.read())

def log_to_csv(filepath: str, data_row: list):
    file_exists = os.path.isfile(filepath)
    with open(filepath, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "Depth_Tier", "Threads", "Trial", "Throughput_RPS", 
                "Service_P50_ns", "Service_P99_ns", 
                "Queue_P50_ns", "Queue_P99_ns", 
                "Start_Depth", "End_Depth"
            ])
        writer.writerow(data_row)

def unbox_order_to_cpp_dict(raw_order: dict) -> dict:
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
        
    owner_uuid_int = uuid.UUID(parsed.get("order_owner_id", "00000000-0000-0000-0000-000000000000")).int
    owner_id_high = owner_uuid_int >> 64
    owner_id_low = owner_uuid_int & ((1 << 64) - 1)
    
    side_enum = mitori_engine_cpp.Side.BUY if parsed.get('side', 'buy').lower() == 'buy' else mitori_engine_cpp.Side.SELL
    type_enum = mitori_engine_cpp.Type.LIMIT if parsed.get('type', 'limit').lower() == 'limit' else mitori_engine_cpp.Type.MARKET
    
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

def stream_to_numpy_dict(raw_orders: list) -> dict:
    num_orders = len(raw_orders)
    
    oid_h = np.zeros(num_orders, dtype=np.uint64)
    oid_l = np.zeros(num_orders, dtype=np.uint64)
    own_h = np.zeros(num_orders, dtype=np.uint64)
    own_l = np.zeros(num_orders, dtype=np.uint64)
    side = np.zeros(num_orders, dtype=np.uint8)
    type_arr = np.zeros(num_orders, dtype=np.uint8)
    is_canc = np.zeros(num_orders, dtype=np.bool_)
    price = np.zeros(num_orders, dtype=np.uint64)
    shares = np.zeros(num_orders, dtype=np.uint64)
    max_f = np.full(num_orders, 18446744073709551615, dtype=np.uint64)
    
    for i, parsed in enumerate(raw_orders):
        if parsed.get("price") is not None:
            price[i] = int(Decimal(str(parsed["price"])) * PRECISION_MULTIPLIER)
        if parsed.get("number_of_shares") is not None:
            shares[i] = int(Decimal(str(parsed["number_of_shares"])) * PRECISION_MULTIPLIER)
            
        if "order_id" in parsed and parsed["order_id"]:
            order_uuid_int = uuid.UUID(parsed["order_id"]).int
            oid_h[i] = order_uuid_int >> 64
            oid_l[i] = order_uuid_int & ((1 << 64) - 1)
            
        owner_uuid_int = uuid.UUID(parsed.get("order_owner_id", "00000000-0000-0000-0000-000000000000")).int
        own_h[i] = owner_uuid_int >> 64
        own_l[i] = owner_uuid_int & ((1 << 64) - 1)
        
        side[i] = int(mitori_engine_cpp.Side.BUY if parsed.get('side', 'buy').lower() == 'buy' else mitori_engine_cpp.Side.SELL)
        type_arr[i] = int(mitori_engine_cpp.Type.LIMIT if parsed.get('type', 'limit').lower() == 'limit' else mitori_engine_cpp.Type.MARKET)
        is_canc[i] = str(parsed.get('is_canceled', 'False')).lower() == 'true'
        
    return {
        "order_id_high": oid_h,
        "order_id_low": oid_l,
        "order_owner_id_high": own_h,
        "order_owner_id_low": own_l,
        "side": side,
        "type": type_arr,
        "is_canceled": is_canc,
        "price": price,
        "number_of_shares": shares,
        "max_authorized_funds": max_f
    }

def run_q1_matrix(tier_name: str, seed_file_path: str, raw_active_stream: list, csv_filename: str):
    print(f"--- Starting C++ Q1 Benchmark for {tier_name} Depth ---")
    
    resting_orders = load_json(seed_file_path)
    cpp_resting_orders = [unbox_order_to_cpp_dict(o) for o in resting_orders]
    numpy_active_stream = stream_to_numpy_dict(raw_active_stream)
    
    for thread_count in THREAD_COUNTS:
        print(f"\n>>> Running {tier_name} Depth | {thread_count} Threads <<<")
        target_rps_per_thread = TOTAL_TARGET_RPS
        
        trial_throughput = []
        trial_srv_p50 = []
        trial_srv_p99 = []
        trial_que_p50 = []
        trial_que_p99 = []
        
        for trial in range(1, N_TRIALS + 1):
            engine = mitori_engine_cpp.OrderBook('APP')
            
            for o in cpp_resting_orders:
                engine.process_order(
                    o["order_id_high"], o["order_id_low"],
                    o["order_owner_id_high"], o["order_owner_id_low"],
                    o["side"], o["type"], o["is_canceled"],
                    o["price"], o["number_of_shares"],
                    o["max_authorized_funds"]
                )
                
            start_depth = sum(engine.get_book_depth()) if isinstance(engine.get_book_depth(), tuple) else engine.get_book_depth()
            
            gc.disable()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count) as executor:
                futures = []
                for _ in range(thread_count):
                    futures.append(executor.submit(
                        engine.benchmark_closed_loop, 
                        numpy_active_stream, 
                        target_rps_per_thread, 
                        DURATION_SEC, 
                        50000 
                    ))
                
                concurrent.futures.wait(futures)
                
            gc.enable()
            
            all_service_times = []
            all_queue_times = []
            total_processed = 0
            
            for future in futures:
                srv_np, que_np, processed = future.result()
                all_service_times.append(srv_np[:processed])
                all_queue_times.append(que_np[:processed])
                total_processed += processed
                
            end_depth = sum(engine.get_book_depth()) if isinstance(engine.get_book_depth(), tuple) else engine.get_book_depth()
            
            actual_rps = total_processed / DURATION_SEC
            
            if len(all_service_times) > 0:
                flat_srv = np.concatenate(all_service_times)
                flat_que = np.concatenate(all_queue_times)
                
                srv_p50 = np.percentile(flat_srv, 50)
                srv_p99 = np.percentile(flat_srv, 99)
                que_p50 = np.percentile(flat_que, 50)
                que_p99 = np.percentile(flat_que, 99)
                
                del flat_srv, flat_que
            else:
                srv_p50 = srv_p99 = que_p50 = que_p99 = 0
                
            trial_throughput.append(actual_rps)
            trial_srv_p50.append(srv_p50)
            trial_srv_p99.append(srv_p99)
            trial_que_p50.append(que_p50)
            trial_que_p99.append(que_p99)
            
            print(f"  Trial {trial}/{N_TRIALS} -> RPS: {actual_rps:,.0f} | Srv_P99: {srv_p99:,.0f} ns | Que_P99: {que_p99:,.0f} ns | Drift: +{end_depth - start_depth:,}")
            
            log_to_csv(csv_filename, [
                tier_name, thread_count, trial, actual_rps, 
                srv_p50, srv_p99, que_p50, que_p99, 
                start_depth, end_depth
            ])
            
            del engine
            mitori_engine_cpp.cleanup_memory()
            gc.collect()

def main():
    print("Loading active stream into memory...")
    raw_active_stream = load_json("benchmark/data/data_for_test/active_stream_for_q1.json")

    timestamp = int(time.time())
    csv_filename = f"benchmark/data/cpp_test_data/q1_cpp_matrix_{timestamp}.csv"
    
    tiers = [
        ("1k", "benchmark/data/data_for_test/seed_1k.json"),
        ("25k", "benchmark/data/data_for_test/seed_25k.json"),
        ("50k", "benchmark/data/data_for_test/seed_50k.json")
    ]
    
    for tier_name, filepath in tiers:
        run_q1_matrix(tier_name, filepath, raw_active_stream, csv_filename)
        
if __name__ == "__main__":
    main()