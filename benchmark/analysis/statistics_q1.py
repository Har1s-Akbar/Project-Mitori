import polars as pl
import numpy as np
from scipy import stats
from pathlib import Path
import csv
import warnings

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent.parent / "data"
REPORT_DIR = Path(__file__).resolve().parent / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_SIZE_MWU = 1_000_000
SAMPLE_SIZE_BOOTSTRAP = 10_000
N_RESAMPLES = 1000

TIERS = ["1k", "25k", "50k"]
THREAD_COUNTS = [1, 2, 4]
LATENCY_METRICS = ["Service_Latency_ns", "Queue_Latency_ns"]

def find_latest_dir(base_path: Path, prefix: str) -> Path:
    dirs = [d for d in base_path.iterdir() if d.is_dir() and d.name.startswith(prefix)]
    if not dirs:
        raise FileNotFoundError(f"No directory starting with '{prefix}' found in {base_path}")
    return max(dirs, key=lambda p: p.stat().st_mtime)

def find_latest_csv(base_path: Path, prefix: str) -> Path:
    files = list(base_path.glob(f"{prefix}*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV starting with '{prefix}' found in {base_path}")
    return max(files, key=lambda p: p.stat().st_mtime)

def load_parquet_sample(parquet_dir: Path, file_pattern: str, col_name: str, n_samples: int) -> np.ndarray:
    glob_path = str(parquet_dir / file_pattern)
    lf = pl.scan_parquet(glob_path)
    df = lf.select(col_name).drop_nulls().collect()
    
    if df.height == 0:
        return np.array([], dtype=np.int64)
    if df.height > n_samples:
        df = df.sample(n=n_samples, seed=42)
    return df.to_series().to_numpy()

def get_throughput_stats(csv_path: Path, tier: str, threads: int) -> tuple:
    df = pl.read_csv(str(csv_path))
    depth_col = "Depth_Tier" if "Depth_Tier" in df.columns else "Depth"
    filtered = df.filter((pl.col(depth_col) == tier) & (pl.col("Threads") == threads))
    
    if filtered.height == 0:
        return 0.0, 0.0
        
    throughput_arr = filtered["Throughput_RPS"].to_numpy()
    return np.mean(throughput_arr), np.min(throughput_arr)

def p99_statistic(x, axis):
    return np.percentile(x, 99, axis=axis)

def analyze_latency(py_arr: np.ndarray, cpp_arr: np.ndarray) -> dict:
    if len(py_arr) == 0 or len(cpp_arr) == 0:
        return {"med_py": "N/A", "med_cpp": "N/A", "p_val": "N/A", "effect": "N/A", 
                "py_ci_l": "N/A", "py_ci_h": "N/A", "cpp_ci_l": "N/A", "cpp_ci_h": "N/A"}

    mwu_res = stats.mannwhitneyu(cpp_arr, py_arr, alternative='less')
    n1, n2 = len(cpp_arr), len(py_arr)
    r = 1 - (2 * mwu_res.statistic / (n1 * n2))
    
    p_val_str = "< 0.001" if mwu_res.pvalue == 0.0 else f"{mwu_res.pvalue:.5e}"

    py_boot = np.random.choice(py_arr, size=min(len(py_arr), SAMPLE_SIZE_BOOTSTRAP), replace=False)
    cpp_boot = np.random.choice(cpp_arr, size=min(len(cpp_arr), SAMPLE_SIZE_BOOTSTRAP), replace=False)

    py_ci = stats.bootstrap((py_boot,), p99_statistic, confidence_level=0.95, n_resamples=N_RESAMPLES, method='percentile')
    cpp_ci = stats.bootstrap((cpp_boot,), p99_statistic, confidence_level=0.95, n_resamples=N_RESAMPLES, method='percentile')

    return {
        "med_py": f"{np.median(py_arr):,.0f}",
        "med_cpp": f"{np.median(cpp_arr):,.0f}",
        "p_val": p_val_str,
        "effect": f"{r:.3f}",
        "py_ci_l": f"{py_ci.confidence_interval.low:,.0f}",
        "py_ci_h": f"{py_ci.confidence_interval.high:,.0f}",
        "cpp_ci_l": f"{cpp_ci.confidence_interval.low:,.0f}",
        "cpp_ci_h": f"{cpp_ci.confidence_interval.high:,.0f}"
    }

def run_comprehensive_q1():
    py_root = BASE_DIR / "python_test_data"
    cpp_root = BASE_DIR / "cpp_test_data"
    
    py_pq_dir = find_latest_dir(py_root, "python_q1_raw_parquet")
    cpp_pq_dir = find_latest_dir(cpp_root, "cpp_q1_raw_parquet")
    
    py_csv_path = find_latest_csv(py_root, "python_q1_throughput")
    cpp_csv_path = find_latest_csv(cpp_root, "q1_cpp_matrix")
    
    results = []
    
    for tier in TIERS:
        for threads in THREAD_COUNTS:
            print(f"\nProcessing Depth: {tier} | Threads: {threads}")
            file_pattern = f"tier_{tier}_th_{threads}_*.parquet"
            
            py_tp_mean, py_tp_worst = get_throughput_stats(py_csv_path, tier, threads)
            cpp_tp_mean, cpp_tp_worst = get_throughput_stats(cpp_csv_path, tier, threads)
            
            results.append({
                "Depth_Tier": tier, "Threads": threads, "Metric": "Throughput_RPS",
                "Python_Primary": f"{py_tp_mean:,.0f}", "CPP_Primary": f"{cpp_tp_mean:,.0f}",
                "MWU_p_value": "N/A (N=5)", "Effect_Size_r": "N/A",
                "Python_Secondary_Metric": f"Worst: {py_tp_worst:,.0f}",
                "CPP_Secondary_Metric": f"Worst: {cpp_tp_worst:,.0f}"
            })
            
            for metric in LATENCY_METRICS:
                py_data = load_parquet_sample(py_pq_dir, file_pattern, metric, SAMPLE_SIZE_MWU)
                cpp_data = load_parquet_sample(cpp_pq_dir, file_pattern, metric, SAMPLE_SIZE_MWU)
                
                stats_dict = analyze_latency(py_data, cpp_data)
                
                results.append({
                    "Depth_Tier": tier, "Threads": threads, "Metric": metric,
                    "Python_Primary": stats_dict["med_py"], "CPP_Primary": stats_dict["med_cpp"],
                    "MWU_p_value": stats_dict["p_val"], "Effect_Size_r": stats_dict["effect"],
                    "Python_Secondary_Metric": f"p99 CI: [{stats_dict['py_ci_l']}, {stats_dict['py_ci_h']}]",
                    "CPP_Secondary_Metric": f"p99 CI: [{stats_dict['cpp_ci_l']}, {stats_dict['cpp_ci_h']}]"
                })
                print(f"  -> {metric} evaluated.")

    csv_path = REPORT_DIR / "q1_statistical_summary.csv"
    if results:
        fieldnames = results[0].keys()
        with open(csv_path, mode='w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\n[Success] Comprehensive Q1 CSV generated at: {csv_path}")

if __name__ == "__main__":
    run_comprehensive_q1()