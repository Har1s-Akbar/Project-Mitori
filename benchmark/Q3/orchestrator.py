import os
import sys
import time
import subprocess
import argparse
from pathlib import Path
import pandas as pd
import requests
from requests.exceptions import RequestException
import redis
from seeding_script import mint_users_and_seed_cache, connect_and_sterilize_redis

sys.path.append(str(Path(__file__).resolve().parent))

ENGINE_URL = os.getenv("ENGINE_URL", "http://mitori_engine:8000")
RESULTS_DIR = Path(f"/app/benchmark/data/python_test_data")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def sterilize_environment():
    print("  [Cooldown] Allowing 5 seconds for saturated queues to drain...")
    time.sleep(5.0)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"  [Admin] Sending state reset command (Attempt {attempt + 1}/{max_retries})...")
            resp = requests.post(f"{ENGINE_URL}/admin/reset", timeout=15.0)
            resp.raise_for_status()
            print("  [Admin] Engine memory state successfully sterilized.")
            break  
            
        except RequestException as e:
            print(f"  [Warning] Engine reset timeout or failure on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                print("  [Admin] Engine is likely overloaded. Waiting 10 seconds for sockets to clear...")
                time.sleep(10.0)
            else:
                print("  [Critical] Engine failed to reset after 3 attempts. Bypassing HTTP reset to save benchmark execution.")
    
    try:
        print("  [Redis] Connecting to Redis and wiping database...")
        r = connect_and_sterilize_redis()
        
        print("  [Redis] Minting users and seeding scaled balances...")
        mint_users_and_seed_cache(r)
        
        print("  [Redis] Cache seeded successfully.")
    except Exception as e:
        print(f"  [Critical] Redis seeding failed: {e}")

def run_warmup():
    print("\n" + "="*80)
    print(">>> EXECUTING UNTIMED WARM-UP (5,000 orders) <<<")
    print("="*80)
    sterilize_environment()
    
    cmd = [
        "k6", "run",
        "-e", "TARGET_RPS=1000",
        "-e", "DURATION=5s",
        "-e", f"DATA_PATH=/app/benchmark/data/data_for_test/warmup.json",
        "-e", f"CSV_OUTPUT_PATH=/app/benchmark/data/python_test_data/warmup_summary_{int(time.time())}.csv",
        "/app/benchmark/Q3/k6/load_test.js"
    ]
    subprocess.run(cmd, check=True)
    time.sleep(3)

def run_matrix(engine_label: str, rps_tiers: list[int], trials: int):
    results = []
    run_timestamp = int(time.time())
    
    for rps in rps_tiers:
        for trial in range(1, trials + 1):
            print("\n" + "="*80)
            print(f">>> RUNNING: Engine={engine_label} | Tier={rps} RPS | Trial={trial}/{trials} <<<")
            print("="*80)
            
            sterilize_environment()
            
            temp_csv = RESULTS_DIR / f"temp_{engine_label}_{rps}rps_trial{trial}_{run_timestamp}.csv"
            
            cmd = [
                "k6", "run",
                "-e", f"TARGET_RPS={rps}",
                "-e", "DURATION=30s",
                "-e", "DATA_PATH=/app/benchmark/data/data_for_test/test.json",
                "-e", f"CSV_OUTPUT_PATH={temp_csv}",
                "/app/benchmark/Q3/k6/load_test.js"
            ]
            
            start_ts = time.time()
            res = subprocess.run(cmd)
            duration = time.time() - start_ts
            
            if res.returncode != 0:
                print(f"ERROR: Tier {rps} RPS Trial {trial} failed with exit code {res.returncode}")
                if temp_csv.exists():
                    temp_csv.unlink()
                continue
                
            if temp_csv.exists():
                df = pd.read_csv(temp_csv)
                
                df["engine"] = engine_label
                df["target_rps"] = rps
                df["trial"] = trial
                
                leading_cols = ["engine", "target_rps", "trial", "metric", "unit"]
                metric_cols = [c for c in df.columns if c not in leading_cols]
                df = df[leading_cols + metric_cols]
                
                results.append(df)
                
                temp_csv.unlink()
            
            print("  [Cooldown] Waiting 5 seconds to drain network sockets...")
            time.sleep(5)

    if results:
        raw_df = pd.concat(results, ignore_index=True)
        raw_csv_path = RESULTS_DIR / f"{engine_label}_raw_trials_{run_timestamp}.csv"
        raw_df.to_csv(raw_csv_path, index=False)
        print(f"\n[Artifact 1] Raw trials ledger saved: {raw_csv_path.name}")

        num_cols = ["min", "avg", "med", "p90", "p95", "p99", "max"]
        summary_df = (
            raw_df.groupby(["engine", "target_rps", "metric", "unit"], as_index=False)[num_cols]
            .mean()
            .round(2)
        )
        
        summary_df = summary_df.sort_values(by=["target_rps", "metric"]).reset_index(drop=True)
        
        summary_csv_path = RESULTS_DIR / f"{engine_label}_summary_matrix_{run_timestamp}.csv"
        summary_df.to_csv(summary_csv_path, index=False)
        print(f"[Artifact 2] Aggregated matrix saved: {summary_csv_path.name}")
        
        print("\n" + "="*80)
        print(f"AGGREGATED SUMMARY MATRIX: {engine_label}")
        print("="*80)
        print(summary_df[["target_rps", "metric", "med", "p90", "p99", "max"]].to_string(index=False))
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mitori Automated Benchmark Harness")
    parser.add_argument("--engine", choices=["PYTHON", "CPP"], required=True, help="Active matching engine mode")
    parser.add_argument("--trials", type=int, default=5, help="Number of trials per RPS tier")
    parser.add_argument("--skip-warmup", action="store_true", help="Skip the initial warm-up run")
    args = parser.parse_args()

    if not args.skip_warmup:
        run_warmup()

    tiers = [500, 2000, 5000]
    run_matrix(engine_label=args.engine, rps_tiers=tiers, trials=args.trials)