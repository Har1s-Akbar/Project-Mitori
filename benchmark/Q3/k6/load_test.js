import http from 'k6/http';
import { check } from 'k6';
import { Trend } from 'k6/metrics';
import { SharedArray } from 'k6/data';
import exec from 'k6/execution';

const CONFIG = {
  TARGET_RPS: parseInt(__ENV.TARGET_RPS || '5000', 10),
  DURATION: __ENV.DURATION || '30s',
  BASE_URL: __ENV.ENGINE_URL || __ENV.BASE_URL || 'http://mitori_engine:8000',
  DATA_PATH: __ENV.DATA_PATH || '/app/benchmark/data/Q3/test.json',
  CSV_OUTPUT_PATH: __ENV.CSV_OUTPUT_PATH || '/app/benchmark/data/Q3/results/trial_output.csv',
  PRE_ALLOCATED_VUS: parseInt(__ENV.PRE_ALLOCATED_VUS || '100', 10),
  MAX_VUS: parseInt(__ENV.MAX_VUS || '1000', 10), // Raised to 1000 to prevent VU exhaustion under queueing
};

const orderStream = new SharedArray('order_stream', function () {
  const fileContent = open(CONFIG.DATA_PATH);
  return JSON.parse(fileContent);
});

const engineLatencyTrend = new Trend('engine_latency_ns');
const totalProcessTrend = new Trend('total_process_ns');

export const options = {
  scenarios: {
    constant_order_arrival: {
      executor: 'constant-arrival-rate',
      rate: CONFIG.TARGET_RPS,
      timeUnit: '1s',
      duration: CONFIG.DURATION,
      preAllocatedVUs: CONFIG.PRE_ALLOCATED_VUS,
      maxVUs: CONFIG.MAX_VUS,
    },
  },
  // Explicitly enables p(99) metric calculation across all Trends
  summaryTrendStats: ['min', 'avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
  discardResponseBodies: true,
};

export default function () {
  const index = exec.scenario.iterationInTest % orderStream.length;
  const item = orderStream[index];

  if (!item || !item.token) {
    return;
  }

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${item.token}`,
    },
    timeout: '5s',
  };

  const res = http.post(
    `${CONFIG.BASE_URL}/order`,
    JSON.stringify(item.payload),
    params
  );

  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  const rawEngineNs = res.headers['X-Engine-Latency-NS'] || res.headers['x-engine-latency-ns'];
  const rawTotalNs = res.headers['X-Total-Process-NS'] || res.headers['x-total-process-ns'];

  if (rawEngineNs) {
    engineLatencyTrend.add(parseInt(rawEngineNs, 10));
  }
  if (rawTotalNs) {
    totalProcessTrend.add(parseInt(rawTotalNs, 10));
  }
}

// Goja-compatible string padding helper (ES5 safe)
function padLeft(value, targetLength) {
  var str = String(value !== undefined && value !== null ? value : '');
  while (str.length < targetLength) {
    str = ' ' + str;
  }
  return str;
}

export function handleSummary(data) {
  const getMetricStats = (metricName) => {
    const m = data.metrics[metricName];
    if (!m || !m.values) {
      return { min: '0.00', avg: '0.00', med: '0.00', p90: '0.00', p95: '0.00', p99: '0.00', max: '0.00' };
    }
    return {
      min: (m.values.min || 0).toFixed(2),
      avg: (m.values.avg || 0).toFixed(2),
      med: (m.values.med || 0).toFixed(2),
      p90: (m.values['p(90)'] || 0).toFixed(2),
      p95: (m.values['p(95)'] || 0).toFixed(2),
      p99: (m.values['p(99)'] || 0).toFixed(2),
      max: (m.values.max || 0).toFixed(2),
    };
  };

  const httpStats = getMetricStats('http_req_duration');
  const engineStats = getMetricStats('engine_latency_ns');
  const totalStats = getMetricStats('total_process_ns');

  const csvHeaders = 'metric,unit,min,avg,med,p90,p95,p99,max\n';
  const csvRows = [
    `http_req_duration,ms,${httpStats.min},${httpStats.avg},${httpStats.med},${httpStats.p90},${httpStats.p95},${httpStats.p99},${httpStats.max}`,
    `engine_latency_ns,ns,${engineStats.min},${engineStats.avg},${engineStats.med},${engineStats.p90},${engineStats.p95},${engineStats.p99},${engineStats.max}`,
    `total_process_ns,ns,${totalStats.min},${totalStats.avg},${totalStats.med},${totalStats.p90},${totalStats.p95},${totalStats.p99},${totalStats.max}`,
  ].join('\n');

  const csvPayload = csvHeaders + csvRows + '\n';

  const textSummary = `
================================================================================
                          MITORI BENCHMARK TRIAL SUMMARY
================================================================================
Target RPS: ${CONFIG.TARGET_RPS} | Duration: ${CONFIG.DURATION} | Max VUs: ${CONFIG.MAX_VUS}
--------------------------------------------------------------------------------
Metric                  Unit         p50 (Med)           p90           p99         Max
--------------------------------------------------------------------------------
HTTP Req Duration       ms      ${padLeft(httpStats.med, 12)}  ${padLeft(httpStats.p90, 12)}  ${padLeft(httpStats.p99, 12)}  ${padLeft(httpStats.max, 10)}
Engine Latency (T_eng)  ns      ${padLeft(engineStats.med, 12)}  ${padLeft(engineStats.p90, 12)}  ${padLeft(engineStats.p99, 12)}  ${padLeft(engineStats.max, 10)}
Total Process (T_tot)   ns      ${padLeft(totalStats.med, 12)}  ${padLeft(totalStats.p90, 12)}  ${padLeft(totalStats.p99, 12)}  ${padLeft(totalStats.max, 10)}
================================================================================
`;

  const outputMap = {
    stdout: textSummary,
  };
  outputMap[CONFIG.CSV_OUTPUT_PATH] = csvPayload;

  return outputMap;
}