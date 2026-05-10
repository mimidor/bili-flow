<template>
  <div class="qteasy-compare">
    <div class="qteasy-compare__head">
      <div class="qteasy-compare__head-card">
        <span class="qteasy-compare__head-label">结果 A</span>
        <strong class="qteasy-compare__head-title">{{ left.job_name || left.job_id }}</strong>
        <span class="qteasy-compare__head-meta">{{ left.strategy_id || left.strategy_path || left.job_id }}</span>
      </div>
      <div class="qteasy-compare__divider">VS</div>
      <div class="qteasy-compare__head-card">
        <span class="qteasy-compare__head-label">结果 B</span>
        <strong class="qteasy-compare__head-title">{{ right.job_name || right.job_id }}</strong>
        <span class="qteasy-compare__head-meta">{{ right.strategy_id || right.strategy_path || right.job_id }}</span>
      </div>
    </div>

    <div class="qteasy-compare__meta-grid">
      <div class="qteasy-kv">
        <span class="qteasy-kv__label">A 回测区间</span>
        <strong>{{ left.invest_start || "-" }} ~ {{ left.invest_end || "-" }}</strong>
      </div>
      <div class="qteasy-kv">
        <span class="qteasy-kv__label">B 回测区间</span>
        <strong>{{ right.invest_start || "-" }} ~ {{ right.invest_end || "-" }}</strong>
      </div>
      <div class="qteasy-kv">
        <span class="qteasy-kv__label">A 基准</span>
        <strong>{{ left.benchmark || "-" }}</strong>
      </div>
      <div class="qteasy-kv">
        <span class="qteasy-kv__label">B 基准</span>
        <strong>{{ right.benchmark || "-" }}</strong>
      </div>
    </div>

    <el-card shadow="never" class="qteasy-compare__section">
      <template #header>
        <div class="qteasy-compare__section-title">指标对比</div>
      </template>
      <el-table :data="metricRows" stripe>
        <el-table-column prop="label" label="指标" min-width="180" />
        <el-table-column prop="leftDisplay" :label="leftLabel" min-width="160" />
        <el-table-column prop="rightDisplay" :label="rightLabel" min-width="160" />
        <el-table-column prop="diffDisplay" label="差值 (B-A)" min-width="140" />
      </el-table>
    </el-card>

    <div class="qteasy-backtest-charts__grid">
      <div class="qteasy-backtest-charts__panel">
        <div class="qteasy-backtest-charts__panel-title">净值与基准对比</div>
        <div ref="equityRef" class="qteasy-backtest-charts__canvas"></div>
      </div>
      <div class="qteasy-backtest-charts__panel">
        <div class="qteasy-backtest-charts__panel-title">回撤对比</div>
        <div ref="drawdownRef" class="qteasy-backtest-charts__canvas"></div>
      </div>
      <div class="qteasy-backtest-charts__panel">
        <div class="qteasy-backtest-charts__panel-title">收益分布对比</div>
        <div ref="histogramRef" class="qteasy-backtest-charts__canvas"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";

import type { QteasyChartPoint, QteasyStoredResultDetail } from "../../types";
import { formatPercent } from "../../utils";

const props = defineProps<{
  left: QteasyStoredResultDetail;
  right: QteasyStoredResultDetail;
}>();

const equityRef = ref<HTMLDivElement | null>(null);
const drawdownRef = ref<HTMLDivElement | null>(null);
const histogramRef = ref<HTMLDivElement | null>(null);

let equityChart: echarts.ECharts | null = null;
let drawdownChart: echarts.ECharts | null = null;
let histogramChart: echarts.ECharts | null = null;

const leftLabel = computed(() => props.left.job_name || props.left.job_id);
const rightLabel = computed(() => props.right.job_name || props.right.job_id);

const metricRows = computed(() => {
  const preferredKeys = [
    ["total_return", "累计收益"],
    ["annual_return", "年化收益"],
    ["max_drawdown", "最大回撤"],
    ["sharpe", "夏普比率"],
    ["sortino", "Sortino"],
    ["alpha", "Alpha"],
    ["beta", "Beta"],
    ["win_rate", "胜率"],
  ] as const;
  const leftMetrics = props.left.metrics || {};
  const rightMetrics = props.right.metrics || {};

  const keys = new Set<string>();
  preferredKeys.forEach(([key]) => {
    if (leftMetrics[key] !== undefined || rightMetrics[key] !== undefined) {
      keys.add(key);
    }
  });
  Object.keys(leftMetrics).forEach((key) => keys.add(key));
  Object.keys(rightMetrics).forEach((key) => keys.add(key));

  return Array.from(keys).map((key) => {
    const preferred = preferredKeys.find(([current]) => current === key);
    const leftValue = leftMetrics[key];
    const rightValue = rightMetrics[key];
    const diffValue =
      typeof leftValue === "number" && typeof rightValue === "number" ? rightValue - leftValue : null;
    return {
      key,
      label: preferred?.[1] || key,
      leftDisplay: formatMetricValue(leftValue),
      rightDisplay: formatMetricValue(rightValue),
      diffDisplay: diffValue === null ? "-" : formatMetricValue(diffValue),
    };
  });
});

function formatMetricValue(value: unknown): string {
  if (typeof value === "number") {
    if (Math.abs(value) <= 1 && String(value).includes(".")) {
      return formatPercent(value, 2);
    }
    return value.toFixed(4);
  }
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function buildSeriesMap(points: QteasyChartPoint[]): Map<string, number> {
  return new Map(points.map((item) => [item.label, item.value]));
}

function mergeLabels(...seriesList: QteasyChartPoint[][]): string[] {
  const labels = new Set<string>();
  for (const series of seriesList) {
    for (const item of series) {
      labels.add(item.label);
    }
  }
  return Array.from(labels);
}

function buildAlignedValues(labels: string[], points: QteasyChartPoint[]): Array<number | null> {
  const mapping = buildSeriesMap(points);
  return labels.map((label) => mapping.get(label) ?? null);
}

function buildEquityOption(): echarts.EChartsOption {
  const leftEquity = props.left.equity_curve || [];
  const rightEquity = props.right.equity_curve || [];
  const leftBenchmark = props.left.benchmark_curve || [];
  const rightBenchmark = props.right.benchmark_curve || [];
  const labels = mergeLabels(leftEquity, rightEquity, leftBenchmark, rightBenchmark);
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 24, top: 30, bottom: 32 },
    xAxis: { type: "category", data: labels, boundaryGap: false },
    yAxis: { type: "value", scale: true },
    legend: { top: 0, right: 0 },
    series: [
      {
        name: `${leftLabel.value} 净值`,
        type: "line",
        smooth: true,
        showSymbol: false,
        data: buildAlignedValues(labels, leftEquity),
        lineStyle: { width: 2, color: "#2563eb" },
      },
      {
        name: `${rightLabel.value} 净值`,
        type: "line",
        smooth: true,
        showSymbol: false,
        data: buildAlignedValues(labels, rightEquity),
        lineStyle: { width: 2, color: "#f97316" },
      },
      {
        name: `${leftLabel.value} 基准`,
        type: "line",
        smooth: true,
        showSymbol: false,
        data: buildAlignedValues(labels, leftBenchmark),
        lineStyle: { width: 1.5, color: "#10b981", type: "dashed" },
      },
      {
        name: `${rightLabel.value} 基准`,
        type: "line",
        smooth: true,
        showSymbol: false,
        data: buildAlignedValues(labels, rightBenchmark),
        lineStyle: { width: 1.5, color: "#a855f7", type: "dashed" },
      },
    ],
  };
}

function buildDrawdownOption(): echarts.EChartsOption {
  const leftDrawdown = props.left.drawdown_curve || [];
  const rightDrawdown = props.right.drawdown_curve || [];
  const labels = mergeLabels(leftDrawdown, rightDrawdown);
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 24, top: 30, bottom: 32 },
    xAxis: { type: "category", data: labels, boundaryGap: false },
    yAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => `${(value * 100).toFixed(0)}%` },
    },
    legend: { top: 0, right: 0 },
    series: [
      {
        name: `${leftLabel.value} 回撤`,
        type: "line",
        smooth: true,
        showSymbol: false,
        data: buildAlignedValues(labels, leftDrawdown),
        lineStyle: { width: 2, color: "#ef4444" },
      },
      {
        name: `${rightLabel.value} 回撤`,
        type: "line",
        smooth: true,
        showSymbol: false,
        data: buildAlignedValues(labels, rightDrawdown),
        lineStyle: { width: 2, color: "#f59e0b" },
      },
    ],
  };
}

function buildHistogramOption(): echarts.EChartsOption {
  const leftHistogram = props.left.return_histogram || [];
  const rightHistogram = props.right.return_histogram || [];
  const labels = mergeLabels(leftHistogram, rightHistogram);
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 24, top: 30, bottom: 52 },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: { rotate: 30 },
    },
    yAxis: { type: "value" },
    legend: { top: 0, right: 0 },
    series: [
      {
        name: `${leftLabel.value} 频次`,
        type: "bar",
        data: buildAlignedValues(labels, leftHistogram),
        itemStyle: { color: "#2563eb" },
      },
      {
        name: `${rightLabel.value} 频次`,
        type: "bar",
        data: buildAlignedValues(labels, rightHistogram),
        itemStyle: { color: "#f97316" },
      },
    ],
  };
}

function ensureCharts(): void {
  if (equityRef.value && !equityChart) {
    equityChart = echarts.init(equityRef.value);
  }
  if (drawdownRef.value && !drawdownChart) {
    drawdownChart = echarts.init(drawdownRef.value);
  }
  if (histogramRef.value && !histogramChart) {
    histogramChart = echarts.init(histogramRef.value);
  }
}

function renderCharts(): void {
  ensureCharts();
  equityChart?.setOption(buildEquityOption(), true);
  drawdownChart?.setOption(buildDrawdownOption(), true);
  histogramChart?.setOption(buildHistogramOption(), true);
}

function resizeCharts(): void {
  equityChart?.resize();
  drawdownChart?.resize();
  histogramChart?.resize();
}

watch(
  () => [props.left, props.right],
  async () => {
    await nextTick();
    renderCharts();
  },
  { deep: true },
);

onMounted(async () => {
  await nextTick();
  renderCharts();
  window.addEventListener("resize", resizeCharts);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeCharts);
  equityChart?.dispose();
  drawdownChart?.dispose();
  histogramChart?.dispose();
});
</script>
