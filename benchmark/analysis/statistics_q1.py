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

TIERS = ["1k", "25k", "50k"]
THREAD_COUNTS = [1, 2, 4]

def find_latest_parquet_dir(base_path: Path, prefix: str) -> Path:
    dirs = [d for d in base_path.iterdir() if d.is_dir() and d.name.startswith(prefix)]
    if not dirs:
        raise FileNotFoundError(f"No directory starting with '{prefix}' found in {base_path}")
    return max(dirs, key=lambda p: p.stat().st_mtime)

def load_and_sample(parquet_dir: Path, file_pattern: str, col_name: str, n_samples: int) -> np.ndarray:
    glob_path = str(parquet_dir / file_pattern)
    lf = pl.scan_parquet(glob_path)
    df = lf.select(col_name).drop_nulls().collect()
    
    if df.height == 0:
        return np.array([], dtype=np.int64)
    if df.height > n_samples:
        df = df.sample(n=n_samples, seed=42)
    return df.to_series().to_numpy()

def p99_statistic(x, axis):
    return np.percentile(x, 99, axis=axis)

def compute_statistics(py_arr: np.ndarray, cpp_arr: np.ndarray, tier: str, threads: int) -> dict:
    if len(py_arr) == 0 or len(cpp_arr) == 0:
        return None

    py_med = np.median(py_arr)
    cpp_med = np.median(cpp_arr)

    mwu_res = stats.mannwhitneyu(cpp_arr, py_arr, alternative='less')
    n1, n2 = len(cpp_arr), len(py_arr)
    r = 1 - (2 * mwu_res.statistic / (n1 * n2))

    py_boot = np.random.choice(py_arr, size=min(len(py_arr), SAMPLE_SIZE_BOOTSTRAP), replace=False)
    cpp_boot = np.random.choice(cpp_arr, size=min(len(cpp_arr), SAMPLE_SIZE_BOOTSTRAP), replace=False)

    py_ci = stats.bootstrap((py_boot,), p99_statistic, confidence_level=0.95, n_resamples=N_RESAMPLES, method='percentile')
    cpp_ci = stats.bootstrap((cpp_boot,), p99_statistic, confidence_level=0.95, n_resamples=N_RESAMPLES, method='percentile')

    result_row = {
        "Depth_Tier": tier,
        "Threads": threads,
        "Python_Median_ns": f"{py_med:,.0f}",
        "CPP_Median_ns": f"{cpp_med:,.0f}",
        "MWU_p_value": f"{mwu_res.pvalue:.5e}",
        "Effect_Size_r": f"{r:.3f}",
        "Python_p99_CI_Low": f"{py_ci.confidence_interval.low:,.0f}",
        "Python_p99_CI_High": f"{py_ci.confidence_interval.high:,.0f}",
        "CPP_p99_CI_Low": f"{cpp_ci.confidence_interval.low:,.0f}",
        "CPP_p99_CI_High": f"{cpp_ci.confidence_interval.high:,.0f}"
    }

    print(f"\n[Done] Depth: {tier} | Threads: {threads} -> p-value: {mwu_res.pvalue:.5e} | Effect Size: {r:.3f}")
    return result_row

def run_full_q1_matrix():
    py_root = BASE_DIR / "python_test_data"
    cpp_root = BASE_DIR / "cpp_test_data"
    
    py_dir = find_latest_parquet_dir(py_root, "python_q1_raw_parquet")
    cpp_dir = find_latest_parquet_dir(cpp_root, "cpp_q1_raw_parquet")
    
    print(f"Analyzing Q1 Matrix across directories:\n  - Python: {py_dir.name}\n  - C++:    {cpp_dir.name}\n")
    
    results = []
    for tier in TIERS:
        for threads in THREAD_COUNTS:
            file_pattern = f"tier_{tier}_th_{threads}_*.parquet"
            py_data = load_and_sample(py_dir, file_pattern, "Service_Latency_ns", SAMPLE_SIZE_MWU)
            cpp_data = load_and_sample(cpp_dir, file_pattern, "Service_Latency_ns", SAMPLE_SIZE_MWU)
            
            row = compute_statistics(py_data, cpp_data, tier, threads)
            if row:
                results.append(row)

    csv_path = REPORT_DIR / "q1_statistical_summary.csv"
    if results:
        fieldnames = results[0].keys()
        with open(csv_path, mode='w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\n[Report Generated] Saved master summary CSV to: {csv_path}")

if __name__ == "__main__":
    run_full_q1_matrix()