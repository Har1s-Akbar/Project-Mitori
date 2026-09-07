import polars as pl
import numpy as np
from scipy import stats
from pathlib import Path
import csv

BASE_DIR = Path(__file__).resolve().parent.parent / "data"
REPORT_DIR = Path(__file__).resolve().parent / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_SIZE_MWU = 1_000_000
SAMPLE_SIZE_BOOTSTRAP = 10_000
N_RESAMPLES = 1000

RPS_TIERS = [500, 2000, 5000]
METRICS = [
    ("http_req_duration", "ms"),
    ("total_process_ns", "ns"),
    ("engine_latency_ns", "ns")
]

def find_latest_q3_dir(base_path: Path, engine: str) -> Path:
    """Finds the latest Q3 Parquet directory for a specific engine."""
    prefix = f"{engine}_q3_raw_parquet"
    dirs = [d for d in base_path.iterdir() if d.is_dir() and d.name.startswith(prefix)]
    if not dirs:
        raise FileNotFoundError(f"No Q3 Parquet directory starting with '{prefix}' found in {base_path}")
    return max(dirs, key=lambda p: p.stat().st_mtime)

def load_and_sample_q3(parquet_dir: Path, rps: int, metric_name: str, n_samples: int) -> np.ndarray:
    """Lazily scans Parquet chunks, filters by metric_name, and extracts a uniform sample."""
    file_pattern = f"tier_{rps}_tr_*.parquet"
    glob_path = str(parquet_dir / file_pattern)
    
    lf = pl.scan_parquet(glob_path)
    
    df = (
        lf.filter(pl.col("metric_name") == metric_name)
          .select("metric_value")
          .drop_nulls()
          .collect()
    )
    
    if df.height == 0:
        return np.array([], dtype=np.float64)
    if df.height > n_samples:
        df = df.sample(n=n_samples, seed=42)
        
    return df.to_series().to_numpy()

def p99_statistic(x, axis):
    return np.percentile(x, 99, axis=axis)

def compute_q3_statistics(py_arr: np.ndarray, cpp_arr: np.ndarray, rps: int, metric: str, unit: str) -> dict:
    if len(py_arr) == 0 or len(cpp_arr) == 0:
        print(f"\n[Skipped] Insufficient data for RPS: {rps} | Metric: {metric}")
        return None

    py_med = np.median(py_arr)
    cpp_med = np.median(cpp_arr)

    mwu_res = stats.mannwhitneyu(cpp_arr, py_arr, alternative='less')
    n1, n2 = len(cpp_arr), len(py_arr)
    r = 1 - (2 * mwu_res.statistic / (n1 * n2))
    
    p_val_str = "< 0.001" if mwu_res.pvalue == 0.0 else f"{mwu_res.pvalue:.5e}"

    py_boot = np.random.choice(py_arr, size=min(len(py_arr), SAMPLE_SIZE_BOOTSTRAP), replace=False)
    cpp_boot = np.random.choice(cpp_arr, size=min(len(cpp_arr), SAMPLE_SIZE_BOOTSTRAP), replace=False)

    py_ci = stats.bootstrap((py_boot,), p99_statistic, confidence_level=0.95, n_resamples=N_RESAMPLES, method='percentile')
    cpp_ci = stats.bootstrap((cpp_boot,), p99_statistic, confidence_level=0.95, n_resamples=N_RESAMPLES, method='percentile')

    fmt = ".2f" if unit == "ms" else ".0f"

    result_row = {
        "Target_RPS": rps,
        "Metric": metric,
        "Unit": unit,
        "Python_Median": f"{py_med:{fmt}}",
        "CPP_Median": f"{cpp_med:{fmt}}",
        "MWU_p_value": p_val_str,
        "Effect_Size_r": f"{r:.3f}",
        "Python_p99_CI_Low": f"{py_ci.confidence_interval.low:{fmt}}",
        "Python_p99_CI_High": f"{py_ci.confidence_interval.high:{fmt}}",
        "CPP_p99_CI_Low": f"{cpp_ci.confidence_interval.low:{fmt}}",
        "CPP_p99_CI_High": f"{cpp_ci.confidence_interval.high:{fmt}}"
    }

    print(f"[Done] {rps} RPS | {metric} -> p-value: {p_val_str} | Effect Size: {r:.3f}")
    return result_row

def run_full_q3_analysis():
    py_root = BASE_DIR / "python_test_data"
    cpp_root = BASE_DIR / "cpp_test_data"
    
    try:
        py_dir = find_latest_q3_dir(py_root, "PYTHON")
        cpp_dir = find_latest_q3_dir(cpp_root, "CPP")
    except FileNotFoundError as e:
        print(f"Error locating directories: {e}")
        return
        
    print(f"Analyzing Q3 Data:\n  - Python: {py_dir.name}\n  - C++:    {cpp_dir.name}\n")
    
    results = []
    for rps in RPS_TIERS:
        for metric, unit in METRICS:
            py_data = load_and_sample_q3(py_dir, rps, metric, SAMPLE_SIZE_MWU)
            cpp_data = load_and_sample_q3(cpp_dir, rps, metric, SAMPLE_SIZE_MWU)
            
            row = compute_q3_statistics(py_data, cpp_data, rps, metric, unit)
            if row:
                results.append(row)

    csv_path = REPORT_DIR / "q3_statistical_summary.csv"
    if results:
        fieldnames = results[0].keys()
        with open(csv_path, mode='w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\n[Report Generated] Saved Q3 summary CSV to: {csv_path}")

if __name__ == "__main__":
    run_full_q3_analysis()