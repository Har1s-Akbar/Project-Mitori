set -e 

echo "========== 1. COMPILING C++ ENGINE =========="
cd /app/mitori_engine/core_cpp
cmake -B build -S .
cmake --build build -j 4

echo -e "\n========== 2. EXECUTING BENCHMARK =========="
cd /app
python -X faulthandler benchmark/Q1/benchmark_cpp.py