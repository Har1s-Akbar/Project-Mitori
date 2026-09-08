import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

PLOT_DIR = Path(__file__).resolve().parent / "plots"
PLOT_DIR.mkdir(exist_ok=True)

q1_depths = ["1k", "25k", "50k"]
q1_threads = [1, 2, 4]

py_tp = {
    "1k":  [228174, 243543, 223782],
    "25k": [382258, 363508, 366926],
    "50k": [405909, 302165, 291086],
}
cpp_tp = {
    "1k":  [600308, 938223, 752983],
    "25k": [600309, 1069695, 809769],
    "50k": [600302, 958376, 751318],
}

py_svc = {
    "1k":  [2112, 2093, 2130],
    "25k": [2081, 2120, 2124],
    "50k": [2056, 2175, 2188],
}
cpp_svc = {
    "1k":  [237, 304, 403],
    "25k": [265, 363, 474],
    "50k": [816, 498, 433],
}

py_queue = {
    "1k":  [9464, 11492, 10556],
    "25k": [5326, 10240, 13375],
    "50k": [5113, 10911, 12300],
}
cpp_queue = {
    "1k":  [20.7, 50.3, 172.1],
    "25k": [25.3, 71.4, 174.7],
    "50k": [22.4, 113.8, 178.1],
}

q2_depths = ["1k", "25k", "50k"]
q2_py_p50 = [3299, 4463, 3708]
q2_py_p99 = [21083, 59653, 29549]  
q2_cpp_p50 = [75, 70, 72]
q2_cpp_p99 = [476, 836, 1144]

q3_rps = [500, 2000, 5000]
q3_py_engine = [6761, 6451, 6493]
q3_cpp_engine = [6587, 6237, 6290]
q3_py_http = [1280, 1920, 2069]
q3_cpp_http = [1349, 1929, 1993]

fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), sharey=True)
x = np.arange(3)
width = 0.35

for idx, depth in enumerate(q1_depths):
    ax = axes[idx]
    bars1 = ax.bar(x - width/2, py_tp[depth], width, label='Python', color='#e74c3c', alpha=0.85)
    bars2 = ax.bar(x + width/2, cpp_tp[depth], width, label='C++', color='#3498db', alpha=0.85)
    
    ax.set_xticks(x)
    ax.set_xticklabels(['1T', '2T', '4T'])
    ax.set_xlabel('Thread Count')
    if idx == 0:
        ax.set_ylabel('Throughput (RPS)')
    ax.set_title(f'Depth: {depth}')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    for i, (py, cpp) in enumerate(zip(py_tp[depth], cpp_tp[depth])):
        speedup = cpp / py
        ax.annotate(f'{speedup:.1f}×', 
                   xy=(x[i] + width/2, cpp), 
                   xytext=(0, 5), textcoords='offset points',
                   ha='center', fontsize=8, color='#2c3e50')

fig.suptitle('Q1: Throughput Scaling — Python vs. C++', fontsize=13, fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig(PLOT_DIR / 'q1_throughput_scaling.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"[Saved] {PLOT_DIR / 'q1_throughput_scaling.png'}")

fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), sharey=True)

for idx, depth in enumerate(q1_depths):
    ax = axes[idx]
    ax.plot(q1_threads, py_svc[depth], 'o-', color='#e74c3c', linewidth=2, markersize=8, label='Python')
    ax.plot(q1_threads, cpp_svc[depth], 's-', color='#3498db', linewidth=2, markersize=8, label='C++')
    
    ax.set_xlabel('Thread Count')
    if idx == 0:
        ax.set_ylabel('Service Latency P50 (ns)')
    ax.set_title(f'Depth: {depth}')
    ax.set_yscale('log')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xticks(q1_threads)

fig.suptitle('Q1: Service Latency P50 (Log Scale)', fontsize=13, fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig(PLOT_DIR / 'q1_service_latency.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"[Saved] {PLOT_DIR / 'q1_service_latency.png'}")

fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), sharey=True)

for idx, depth in enumerate(q1_depths):
    ax = axes[idx]
    ax.plot(q1_threads, py_queue[depth], 'o-', color='#e74c3c', linewidth=2.5, markersize=10, label='Python')
    ax.plot(q1_threads, cpp_queue[depth], 's-', color='#3498db', linewidth=2.5, markersize=10, label='C++')
    
    ax.set_xlabel('Thread Count')
    if idx == 0:
        ax.set_ylabel('Queue Latency P50 (ms)')
    ax.set_title(f'Depth: {depth}')
    ax.set_yscale('log')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xticks(q1_threads)
    
    ax.annotate('Python: 9–13s queue', xy=(2, py_queue[depth][2]), 
                xytext=(2.3, py_queue[depth][2]*1.5),
                fontsize=8, color='#e74c3c', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#e74c3c'))

fig.suptitle('Q1: Queue Residence Time P50 (Log Scale)', fontsize=13, fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig(PLOT_DIR / 'q1_queue_latency.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"[Saved] {PLOT_DIR / 'q1_queue_latency.png'}")

fig, ax = plt.subplots(figsize=(10, 5.5))
x = np.arange(len(q2_depths))
width = 0.35

bars_py = ax.bar(x - width/2, q2_py_p50, width, label='Python P50', color='#e74c3c', alpha=0.85, zorder=3)
bars_cpp = ax.bar(x + width/2, q2_cpp_p50, width, label='C++ P50', color='#3498db', alpha=0.85, zorder=3)

ax.scatter(x - width/2, q2_py_p99, marker='D', s=80, color='#c0392b', 
           label='Python P99', zorder=5, edgecolors='white', linewidths=1)
ax.scatter(x + width/2, q2_cpp_p99, marker='D', s=80, color='#2980b9', 
           label='C++ P99', zorder=5, edgecolors='white', linewidths=1)

for i in range(len(q2_depths)):
    ax.plot([x[i] - width/2, x[i] - width/2], [q2_py_p50[i], q2_py_p99[i]], 
            'k--', alpha=0.3, linewidth=1, zorder=2)
    ax.plot([x[i] + width/2, x[i] + width/2], [q2_cpp_p50[i], q2_cpp_p99[i]], 
            'k--', alpha=0.3, linewidth=1, zorder=2)

ax.set_ylabel('Latency (ns)')
ax.set_xlabel('Book Depth')
ax.set_title('Q2: Isolated Matching Latency — P50 (bars) vs P99 (diamonds)', fontsize=13, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(q2_depths)
ax.set_yscale('log')
ax.legend(loc='upper left', ncol=2)
ax.grid(axis='y', alpha=0.3, zorder=1)

for i, (py, cpp) in enumerate(zip(q2_py_p50, q2_cpp_p50)):
    speedup = py / cpp
    ax.annotate(f'{speedup:.0f}×', 
               xy=(i, max(py, cpp)), 
               xytext=(0, 12), textcoords='offset points',
               ha='center', fontsize=11, fontweight='bold', color='#2c3e50')

plt.tight_layout()
fig.savefig(PLOT_DIR / 'q2_isolated_latency.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"[Saved] {PLOT_DIR / 'q2_isolated_latency.png'}")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

x = np.arange(len(q3_rps))
width = 0.35

ax1.bar(x - width/2, q3_py_engine, width, label='Python', color='#e74c3c', alpha=0.85)
ax1.bar(x + width/2, q3_cpp_engine, width, label='C++', color='#3498db', alpha=0.85)
ax1.set_ylabel('Engine Latency (ns)')
ax1.set_xlabel('Target RPS')
ax1.set_title('Q3: Engine Latency (Isolated)', fontsize=12, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(q3_rps)
ax1.legend()
ax1.grid(axis='y', alpha=0.3)

ax2.bar(x - width/2, q3_py_http, width, label='Python', color='#e74c3c', alpha=0.85)
ax2.bar(x + width/2, q3_cpp_http, width, label='C++', color='#3498db', alpha=0.85)
ax2.set_ylabel('HTTP Latency (ms)')
ax2.set_xlabel('Target RPS')
ax2.set_title('Q3: HTTP Request Latency (Full Path)', fontsize=12, fontweight='bold')
ax2.set_xticks(x)
ax2.set_xticklabels(q3_rps)
ax2.legend()
ax2.grid(axis='y', alpha=0.3)

ax2.annotate('Amdahl\'s Law:\nEngine < 0.001%\nof total latency', 
            xy=(2, max(q3_py_http[2], q3_cpp_http[2])), 
            xytext=(1.3, 3500),
            fontsize=10, fontweight='bold', color='#2c3e50',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#f39c12', alpha=0.2),
            arrowprops=dict(arrowstyle='->', color='#2c3e50'))

fig.suptitle('Q3: The Paradox — Engine Speedup Vanishes in Full System', 
             fontsize=13, fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig(PLOT_DIR / 'q3_paradox.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"[Saved] {PLOT_DIR / 'q3_paradox.png'}")

fig, ax = plt.subplots(figsize=(10, 5))

questions = ['Q2\n(Isolated)', 'Q1\n(Concurrent)', 'Q3\n(Full System)']
ratios = [50, 3, 0.0008]
colors = ['#27ae60', '#f39c12', '#e74c3c']

bars = ax.bar(questions, ratios, color=colors, alpha=0.85, edgecolor='black', linewidth=1.2)
ax.set_ylabel('C++ Advantage (Ratio)')
ax.set_title('Cross-Question Synthesis: C++ Advantage Attenuation', fontsize=13, fontweight='bold')
ax.set_yscale('log')
ax.grid(axis='y', alpha=0.3)

for bar, ratio in zip(bars, ratios):
    height = bar.get_height()
    label = f'{ratio:.0f}×' if ratio >= 1 else f'{ratio*100:.4f}%'
    ax.annotate(label, xy=(bar.get_x() + bar.get_width()/2, height),
                xytext=(0, 8), textcoords='offset points',
                ha='center', fontsize=12, fontweight='bold')

ax.text(0.5, 0.02, 
        'Q2: 50× speedup in isolation\nQ1: 3× speedup under load\nQ3: <0.001% in full system (Amdahl\'s Law)',
        transform=ax.transAxes, fontsize=10, verticalalignment='bottom',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='wheat', alpha=0.5))

plt.tight_layout()
fig.savefig(PLOT_DIR / 'synthesis_attenuation.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"[Saved] {PLOT_DIR / 'synthesis_attenuation.png'}")

print(f"\n{'='*50}")
print(f"All plots saved to: {PLOT_DIR}")
print(f"{'='*50}")