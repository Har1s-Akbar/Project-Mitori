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

def find_q2_csv(base_path: Path, prefix: str) -> Path:
    """Finds the specific Q2 CSV file in the target directory."""
    files = list(base_path.glob(f"{prefix}*.csv"))
    if not files:
        raise FileNotFoundError(f"No Q2 CSV starting with '{prefix}' found in {base_path}")
    # Return the most recently modified file if multiple exist
    return max(files, key=lambda p: p.stat().st_mtime)

def load_and_sample_q2(csv_path: Path, tier: str, col_name: str, n_samples: int) -> np.ndarray:
    """Lazily scans the Q2 CSV, filters by Depth_Tier, and extracts a memory-safe sample."""
    lf = pl.scan_csv(str(csv_path))
    
    df = (
        lf.filter(pl.col("Depth_Tier") == tier)
          .select(col_name)
          .drop_nulls()
          .collect()
    )
    
    if df.height == 0:
        return np.array([], dtype=np.int64)
    if df.height > n_samples:
        df = df.sample(n=n_samples, seed=42)
        
    return df.to_series().to_numpy()

def p99_statistic(x, axis):
    return np.percentile(x, 99, axis=axis)

def compute_q2_statistics(py_arr: np.ndarray, cpp_arr: np.ndarray, tier: str) -> dict:
    if len(py_arr) == 0 or len(cpp_arr) == 0:
        print(f"\n[Skipped] Insufficient data for Depth_Tier: {tier}")
        return None

    py_med = np.median(py_arr)
    cpp_med = np.median(cpp_arr)

    # Mann-Whitney U Test
    mwu_res = stats.mannwhitneyu(cpp_arr, py_arr, alternative='less')
    n1, n2 = len(cpp_arr), len(py_arr)
    r = 1 - (2 * mwu_res.statistic / (n1 * n2))
    
    p_val_str = "< 0.001" if mwu_res.pvalue == 0.0 else f"{mwu_res.pvalue:.5e}"

    py_boot = np.random.choice(py_arr, size=min(len(py_arr), SAMPLE_SIZE_BOOTSTRAP), replace=False)
    cpp_boot = np.random.choice(cpp_arr, size=min(len(cpp_arr), SAMPLE_SIZE_BOOTSTRAP), replace=False)

    py_ci = stats.bootstrap((py_boot,), p99_statistic, confidence_level=0.95, n_resamples=N_RESAMPLES, method='percentile')
    cpp_ci = stats.bootstrap((cpp_boot,), p99_statistic, confidence_level=0.95, n_resamples=N_RESAMPLES, method='percentile')

    result_row = {
        "Depth_Tier": tier,
        "Python_Median_ns": f"{py_med:,.0f}",
        "CPP_Median_ns": f"{cpp_med:,.0f}",
        "MWU_p_value": p_val_str,
        "Effect_Size_r": f"{r:.3f}",
        "Python_p99_CI_Low": f"{py_ci.confidence_interval.low:,.0f}",
        "Python_p99_CI_High": f"{py_ci.confidence_interval.high:,.0f}",
        "CPP_p99_CI_Low": f"{cpp_ci.confidence_interval.low:,.0f}",
        "CPP_p99_CI_High": f"{cpp_ci.confidence_interval.high:,.0f}"
    }

    print(f"\n[Done] Depth: {tier} -> p-value: {p_val_str} | Effect Size: {r:.3f}")
    return result_row

def run_full_q2_analysis():
    py_root = BASE_DIR / "python_test_data"
    cpp_root = BASE_DIR / "cpp_test_data"
    
    try:
        py_csv = find_q2_csv(py_root, "q2_")
        cpp_csv = find_q2_csv(cpp_root, "q2_")
    except FileNotFoundError as e:
        print(f"Error locating files: {e}")
        print("Please ensure your Q2 CSV files are in the data folders and start with 'q2_'")
        return
        
    print(f"Analyzing Q2 Data:\n  - Python: {py_csv.name}\n  - C++:    {cpp_csv.name}\n")
    
    results = []
    for tier in TIERS:
        py_data = load_and_sample_q2(py_csv, tier, "Latency_ns", SAMPLE_SIZE_MWU)
        cpp_data = load_and_sample_q2(cpp_csv, tier, "Latency_ns", SAMPLE_SIZE_MWU)
        
        row = compute_q2_statistics(py_data, cpp_data, tier)
        if row:
            results.append(row)

    csv_path = REPORT_DIR / "q2_statistical_summary.csv"
    if results:
        fieldnames = results[0].keys()
        with open(csv_path, mode='w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\n[Report Generated] Saved Q2 summary CSV to: {csv_path}")

if __name__ == "__main__":
    run_full_q2_analysis()