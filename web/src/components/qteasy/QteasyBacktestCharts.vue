<template>
  <div class="qteasy-backtest-charts">
    <div class="qteasy-backtest-charts__metrics">
      <div v-for="item in metricCards" :key="item.key" class="qteasy-backtest-charts__metric-card">
        <span class="qteasy-backtest-charts__metric-label">{{ item.label }}</span>
        <strong class="qteasy-backtest-charts__metric-value">{{ item.value }}</strong>
      </div>
    </div>

    <el-alert
      v-if="series.parsed_ok === false && series.parse_message"
      :title="series.parse_message"
      type="warning"
      :closable="false"
      show-icon
    />

    <div class="qteasy-backtest-charts__grid">
      <div class="qteasy-backtest-charts__panel">
        <div class="qteasy-backtest-charts__panel-title">净值与基准</div>
        <div ref="equityRef" class="qteasy-backtest-charts__canvas"></div>
      </div>
      <div class="qteasy-backtest-charts__panel">
        <div class="qteasy-backtest-charts__panel-title">回撤曲线</div>
        <div ref="drawdownRef" class="qteasy-backtest-charts__canvas"></div>
      </div>
      <div class="qteasy-backtest-charts__panel">
        <div class="qteasy-backtest-charts__panel-title">收益分布</div>
        <div ref="histogramRef" class="qteasy-backtest-charts__canvas"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";

import type { QteasyChartPoint, QteasyChartSeries } from "../../types";
import { formatPercent } from "../../utils";

const props = defineProps<{
  series: QteasyChartSeries;
}>();

const equityRef = ref<HTMLDivElement | null>(null);
const drawdownRef = ref<HTMLDivElement | null>(null);
const histogramRef = ref<HTMLDivElement | null>(null);

let equityChart: echarts.ECharts | null = null;
let drawdownChart: echarts.ECharts | null = null;
let histogramChart: echarts.ECharts | null = null;

const metricCards = computed(() => {
  const metrics = props.series.metrics || {};
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

  const cards = preferredKeys
    .filter(([key]) => metrics[key] !== undefined && metrics[key] !== null)
    .slice(0, 6)
    .map(([key, label]) => ({
      key,
      label,
      value: formatMetricValue(metrics[key]),
    }));

  if (cards.length) {
    return cards;
  }

  return Object.entries(metrics)
    .slice(0, 6)
    .map(([key, value]) => ({ key, label: key, value: formatMetricValue(value) }));
});

function formatMetricValue(value: unknown): string {
  if (typeof value === "number") {
    if (Math.abs(value) <= 1 && String(value).includes(".")) {
      return formatPercent(value, 2);
    }
    return value.toFixed(4);
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function labelsOf(series: QteasyChartPoint[]): string[] {
  return series.map((item) => item.label);
}

function valuesOf(series: QteasyChartPoint[]): number[] {
  return series.map((item) => item.value);
}

function buildEquityOption(): echarts.EChartsOption {
  const equity = props.series.equity_curve || [];
  const benchmark = props.series.benchmark_curve || [];
  const labels = labelsOf(equity.length ? equity : benchmark);
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 24, top: 24, bottom: 32 },
    xAxis: { type: "category", data: labels, boundaryGap: false },
    yAxis: { type: "value", scale: true },
    legend: { top: 0, right: 0 },
    series: [
      {
        name: "策略净值",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: valuesOf(equity),
        lineStyle: { width: 2, color: "#2563eb" },
        areaStyle: { color: "rgba(37,99,235,0.08)" },
      },
      {
        name: "基准",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: valuesOf(benchmark),
        lineStyle: { width: 2, color: "#10b981" },
      },
    ],
  };
}

function buildDrawdownOption(): echarts.EChartsOption {
  const drawdown = props.series.drawdown_curve || [];
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 24, top: 24, bottom: 32 },
    xAxis: { type: "category", data: labelsOf(drawdown), boundaryGap: false },
    yAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => `${(value * 100).toFixed(0)}%` },
    },
    series: [
      {
        name: "回撤",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: valuesOf(drawdown),
        lineStyle: { width: 2, color: "#ef4444" },
        areaStyle: { color: "rgba(239,68,68,0.12)" },
      },
    ],
  };
}

function buildHistogramOption(): echarts.EChartsOption {
  const histogram = props.series.return_histogram || [];
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 24, top: 24, bottom: 52 },
    xAxis: {
      type: "category",
      data: labelsOf(histogram),
      axisLabel: { rotate: 30 },
    },
    yAxis: { type: "value" },
    series: [
      {
        name: "频次",
        type: "bar",
        data: valuesOf(histogram),
        itemStyle: { color: "#7c3aed" },
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
  () => props.series,
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
