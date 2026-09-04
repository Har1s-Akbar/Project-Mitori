import os
import sys
import time
import subprocess
import argparse
from pathlib import Path
import pandas as pd
import requests
import redis
from seeding_script import mint_users_and_seed_cache, connect_and_sterilize_redis

sys.path.append(str(Path(__file__).resolve().parent))

ENGINE_URL = os.getenv("ENGINE_URL", "http://mitori_engine:8000")
RESULTS_DIR = Path(f"/app/benchmark/data/python_test_data/full_path_benchmarking_python_{int(time.time())}")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def sterilize_environment():
    resp = requests.post(f"{ENGINE_URL}/admin/reset", timeout=5.0)
    resp.raise_for_status()

    r = connect_and_sterilize_redis()
    mint_users_and_seed_cache(r)

def run_warmup():
    print("\n" + "="*80)
    print(">>> EXECUTING UNTIMED WARM-UP (5,000 orders) <<<")
    print("="*80)
    sterilize_environment()
    
    cmd = [
        "k6", "run",
        "-e", "TARGET_RPS=1000",
        "-e", "DURATION=5s",
        "-e", "DATA_PATH=/app/benchmark/data/Q3/warmup.json",
        "-e", "CSV_OUTPUT_PATH=/app/benchmark/data/Q3/warmup_summary.csv",
        "/app/benchmark/k6/load_test.js"
    ]
    subprocess.run(cmd, check=True)
    time.sleep(3)

def run_matrix(engine_label: str, rps_tiers: list[int], trials: int):
    results = []
    for rps in rps_tiers:
        for trial in range(1, trials + 1):
            print("\n" + "="*80)
            print(f">>> RUNNING: Engine={engine_label} | Tier={rps} RPS | Trial={trial}/{trials} <<<")
            print("="*80)
            
            sterilize_environment()
            
            csv_path = RESULTS_DIR / f"{engine_label}_{rps}rps_trial{trial}.csv"
            cmd = [
                "k6", "run",
                "-e", f"TARGET_RPS={rps}",
                "-e", "DURATION=30s",
                "-e", "DATA_PATH=/app/benchmark/data/Q3/test.json",
                "-e", f"CSV_OUTPUT_PATH={csv_path}",
                "/app/benchmark/k6/load_test.js"
            ]
            
            start_ts = time.time()
            res = subprocess.run(cmd)
            duration = time.time() - start_ts
            
            if res.returncode != 0:
                print(f"ERROR: Trial failed with exit code {res.returncode}")
                continue
                
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                df["engine"] = engine_label
                df["target_rps"] = rps
                df["trial"] = trial
                results.append(df)
            
            print("  [Cooldown] Waiting 5 seconds to drain network sockets...")
            time.sleep(5)

    if results:
        master_df = pd.concat(results, ignore_index=True)
        master_csv = RESULTS_DIR / f"master_{engine_label}_results.csv"
        master_df.to_csv(master_csv, index=False)
        
        print("\n" + "="*80)
        print(f"AGGREGATE SUMMARY MATRIX: {engine_label}")
        print("="*80)
        summary = master_df.groupby(["target_rps", "metric"])[["med", "p90", "p99"]].mean().reset_index()
        print(summary.to_string(index=False))

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