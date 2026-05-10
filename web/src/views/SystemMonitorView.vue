<template>
  <div class="task-center system-monitor">
    <section class="task-hero">
      <div class="task-hero__copy">
        <div class="task-hero__eyebrow">SYSTEM MONITOR</div>
        <h1>系统监控</h1>
        <p class="task-hero__desc">
          聚合服务健康、调度/队列心跳、失败堆积、最近错误和重试压力，把运维态势放在同一屏里查看。
        </p>
        <div class="hero-badges">
          <span class="hero-badge">健康总览</span>
          <span class="hero-badge">任务心跳</span>
          <span class="hero-badge">失败堆积</span>
          <span class="hero-badge">最近告警</span>
        </div>
      </div>

      <div class="hero-panel">
        <div>
          <div class="hero-panel__label">任务总状态</div>
          <div class="hero-panel__value">{{ totalPending + totalProcessing + totalFailed }}</div>
          <div class="hero-panel__meta">
            总任务量：{{ totalPending }} 待处理 · {{ totalProcessing }} 处理中 · {{ totalFailed }} 失败
          </div>
        </div>
        <div class="hero-panel__split">
          <div>
            <div class="hero-panel__mini-label">调度器</div>
            <div class="hero-panel__mini-value">{{ runtimeSummary.scheduler }}</div>
          </div>
          <div>
            <div class="hero-panel__mini-label">队列</div>
            <div class="hero-panel__mini-value">{{ runtimeSummary.queue }}</div>
          </div>
        </div>

        <div class="task-hero__actions">
          <el-button type="primary" @click="load">刷新监控</el-button>
          <el-button @click="goTaskCenter">任务中心</el-button>
          <el-button @click="goLogCenter">日志中心</el-button>
        </div>
      </div>
    </section>

    <div class="health-grid">
      <a-card
        v-for="metric in healthMetrics"
        :key="metric.module"
        class="page-card health-card"
        :bordered="false"
      >
        <div class="health-card__title">{{ metric.label }}</div>
        <div class="health-card__value">{{ formatPercent(metric.success_rate) }}</div>
        <div class="health-card__meta">失败率 {{ formatPercent(metric.failure_rate) }}</div>
        <div class="health-card__stats">
          <div>
            <span>成功</span>
            <strong>{{ metric.success_count }}</strong>
          </div>
          <div>
            <span>失败</span>
            <strong>{{ metric.failure_count }}</strong>
          </div>
          <div>
            <span>终态</span>
            <strong>{{ metric.terminal_total }}</strong>
          </div>
        </div>
        <div class="health-card__footer">
          <span>总数 {{ metric.total_count }}</span>
          <span>失败 {{ metric.failure_count }}</span>
        </div>
      </a-card>
    </div>

    <div class="chart-grid">
      <a-card class="page-card chart-card" :bordered="false">
        <div class="section-header section-header--compact">
          <div>
            <div class="section__title">最近 14 天推送趋势</div>
            <div class="section__desc">视频、动态和推送量按天展示</div>
          </div>
        </div>

        <template v-if="pushChart.series.length">
          <div class="chart-stage">
            <svg :viewBox="`0 0 ${pushChart.width} ${pushChart.height}`" class="line-chart" preserveAspectRatio="none">
              <g v-for="tick in pushChart.yTicks" :key="tick.value">
                <line
                  :x1="pushChart.padding.left"
                  :x2="pushChart.width - pushChart.padding.right"
                  :y1="tick.y"
                  :y2="tick.y"
                  class="chart-gridline"
                />
                <text
                  :x="pushChart.padding.left - 8"
                  :y="tick.y"
                  class="chart-axis-label"
                  text-anchor="end"
                  dominant-baseline="middle"
                >
                  {{ tick.label }}
                </text>
              </g>

              <g v-for="series in pushChart.series" :key="series.key">
                <path :d="series.path" :stroke="series.color" class="chart-line" />
                <circle
                  v-for="point in series.points"
                  :key="`${series.key}-${point.index}`"
                  :cx="point.x"
                  :cy="point.y"
                  :fill="series.color"
                  class="chart-point"
                  r="4"
                />
              </g>
            </svg>
          </div>

          <div class="chart-legend">
            <div v-for="series in pushChart.series" :key="series.key" class="chart-legend-item">
              <span class="chart-legend-dot" :style="{ background: series.color }" />
              <span>{{ series.label }}</span>
              <strong>{{ series.latestLabel }}</strong>
            </div>
          </div>

          <div class="chart-axis">
            <span v-for="label in pushChart.labels" :key="label">{{ label }}</span>
          </div>
        </template>
        <a-empty v-else description="暂无推送趋势数据" />
      </a-card>

      <a-card class="page-card chart-card" :bordered="false">
        <div class="section-header section-header--compact">
          <div>
            <div class="section__title">最近 14 天 LLM 调用趋势</div>
            <div class="section__desc">调用次数与 token 消耗</div>
          </div>
        </div>

        <template v-if="llmChart.series.length">
          <div class="chart-stage">
            <svg :viewBox="`0 0 ${llmChart.width} ${llmChart.height}`" class="line-chart" preserveAspectRatio="none">
              <g v-for="tick in llmChart.yTicks" :key="tick.value">
                <line
                  :x1="llmChart.padding.left"
                  :x2="llmChart.width - llmChart.padding.right"
                  :y1="tick.y"
                  :y2="tick.y"
                  class="chart-gridline"
                />
                <text
                  :x="llmChart.padding.left - 8"
                  :y="tick.y"
                  class="chart-axis-label"
                  text-anchor="end"
                  dominant-baseline="middle"
                >
                  {{ tick.label }}
                </text>
              </g>

              <g v-for="series in llmChart.series" :key="series.key">
                <path :d="series.path" :stroke="series.color" class="chart-line" />
                <circle
                  v-for="point in series.points"
                  :key="`${series.key}-${point.index}`"
                  :cx="point.x"
                  :cy="point.y"
                  :fill="series.color"
                  class="chart-point"
                  r="4"
                />
              </g>
            </svg>
          </div>

          <div class="chart-legend">
            <div v-for="series in llmChart.series" :key="series.key" class="chart-legend-item">
              <span class="chart-legend-dot" :style="{ background: series.color }" />
              <span>{{ series.label }}</span>
              <strong>{{ series.latestLabel }}</strong>
            </div>
          </div>

          <div class="chart-axis">
            <span v-for="label in llmChart.labels" :key="label">{{ label }}</span>
          </div>
        </template>
        <a-empty v-else description="暂无 LLM 趋势数据" />
      </a-card>
    </div>

    <div class="chart-grid">
      <a-card class="page-card section" :bordered="false">
        <div class="section-header section-header--compact">
          <div>
            <div class="section__title">运行状态</div>
            <div class="section__desc">调度器、队列心跳、最近运行和错误摘要</div>
          </div>
        </div>

        <div class="runtime-grid runtime-grid--compact">
          <a-card v-for="state in runtimeStates" :key="state.component" class="runtime-card" :bordered="false">
            <template #title>
              <div class="section-header section-header--compact">
                <div>
                  <div class="section__title">{{ state.label }}</div>
                  <div class="section__desc">最近心跳与运行记录</div>
                </div>
                <a-tag :color="runtimeTagColor(state.status)">
                  {{ state.is_paused ? "已暂停" : translateStatus(state.status) }}
                </a-tag>
              </div>
            </template>

            <div class="runtime-card__body">
              <div class="runtime-card__row">
                <span class="muted">最近心跳</span>
                <strong>{{ formatDateTime(state.last_heartbeat_at) }}</strong>
              </div>
              <div class="runtime-card__row">
                <span class="muted">最近运行</span>
                <strong>{{ formatDateTime(state.last_run_at) }}</strong>
              </div>
              <div class="runtime-card__row">
                <span class="muted">最近消息</span>
                <span class="summary-box">{{ state.last_message || "-" }}</span>
              </div>
              <div class="runtime-card__row">
                <span class="muted">最近错误</span>
                <span class="summary-box">{{ state.last_error || "-" }}</span>
              </div>
            </div>
          </a-card>
        </div>
      </a-card>

      <a-card class="page-card section" :bordered="false">
        <div class="section-header section-header--compact">
          <div>
            <div class="section__title">最近错误</div>
            <div class="section__desc">跨模块最近的失败摘要</div>
          </div>
          <a-tag color="red">{{ recentErrors.length }}</a-tag>
        </div>

        <div v-if="recentErrors.length" class="audit-list">
          <div v-for="item in recentErrors" :key="`${item.module}-${item.item_id}-${item.occurred_at}`" class="audit-list__item">
            <div class="audit-list__meta">
              <a-tag :color="errorTagColor(item.module)" size="small">{{ item.label }}</a-tag>
              <span class="muted">{{ item.item_label }} {{ item.item_id }}</span>
              <span class="muted">{{ formatDateTime(item.occurred_at) }}</span>
            </div>
            <div class="audit-list__title">{{ item.item_title || item.error_message }}</div>
            <div class="summary-box">{{ item.error_message }}</div>
          </div>
        </div>
        <a-empty v-else description="暂无错误摘要" />
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { api } from "../api";
import type { HealthMetricItem, MonitorOverviewResponse, RecentErrorItem, TaskRuntimeItem, TrendWindowSummary } from "../types";
import { formatDateTime, formatPercent, translateStatus } from "../utils";

type TrendRow = {
  day: string;
  videos?: number;
  dynamics?: number;
  pushes?: number;
  calls?: number;
  tokens?: number;
};

type ChartPoint = {
  index: number;
  x: number;
  y: number;
  value: number;
};

type ChartSeries = {
  key: string;
  label: string;
  color: string;
  latestLabel: string;
  points: ChartPoint[];
  path: string;
};

type ChartTick = {
  value: number;
  y: number;
  label: string;
};

type ChartModel = {
  width: number;
  height: number;
  padding: { top: number; right: number; bottom: number; left: number };
  labels: string[];
  yTicks: ChartTick[];
  series: ChartSeries[];
};

const router = useRouter();
const overview = ref<MonitorOverviewResponse | null>(null);

const runtimeStates = computed<TaskRuntimeItem[]>(() => overview.value?.runtime_states || []);
const healthMetrics = computed<HealthMetricItem[]>(() => overview.value?.health_metrics || []);
const recentErrors = computed<RecentErrorItem[]>(() => overview.value?.recent_errors || []);

const totalPending = computed(() => overview.value?.task_overview.total_pending || 0);
const totalProcessing = computed(() => overview.value?.task_overview.total_processing || 0);
const totalFailed = computed(() => overview.value?.task_overview.total_failed || 0);

const runtimeSummary = computed(() => {
  const scheduler = runtimeStates.value.find((item) => item.component === "scheduler");
  const queue = runtimeStates.value.find((item) => item.component === "queue_worker");
  return {
    scheduler: scheduler ? (scheduler.is_paused ? "已暂停" : translateStatus(scheduler.status)) : "-",
    queue: queue ? (queue.is_paused ? "已暂停" : translateStatus(queue.status)) : "-",
  };
});

const pushTrend = computed<TrendRow[]>(() => (overview.value?.recent_push_days || []) as TrendRow[]);
const llmTrend = computed<TrendRow[]>(() => (overview.value?.recent_llm_days || []) as TrendRow[]);

function formatDayLabel(day: string): string {
  if (!day) return "-";
  const parts = day.split("-");
  if (parts.length !== 3) return day;
  return `${parts[1]}/${parts[2]}`;
}

function formatChartValue(value: number): string {
  if (!Number.isFinite(value)) return "0";
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  if (value >= 10) return `${Math.round(value)}`;
  if (value >= 1) return value.toFixed(1);
  return value.toFixed(2);
}

function buildChart(
  rows: TrendRow[],
  defs: Array<{ key: string; label: string; color: string; getValue: (row: TrendRow) => number }>
): ChartModel {
  const width = 860;
  const height = 280;
  const padding = { top: 20, right: 24, bottom: 28, left: 52 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const labels = rows.map((row) => formatDayLabel(row.day));
  const allValues = defs.flatMap((def) => rows.map((row) => Math.max(0, def.getValue(row) || 0)));
  const maxValue = Math.max(1, ...allValues);
  const yTicks = [1, 0.75, 0.5, 0.25, 0].map((ratio) => {
    const value = maxValue * ratio;
    return {
      value,
      y: padding.top + innerHeight - innerHeight * ratio,
      label: formatChartValue(value),
    };
  });

  const denominator = Math.max(rows.length - 1, 1);
  const series = defs.map((def) => {
    const points = rows.map((row, index) => {
      const value = Math.max(0, def.getValue(row) || 0);
      const x = rows.length === 1 ? padding.left + innerWidth / 2 : padding.left + (index / denominator) * innerWidth;
      const y = padding.top + innerHeight - (value / maxValue) * innerHeight;
      return { index, x, y, value };
    });

    const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
    const latestValue = points.length ? points[points.length - 1].value : 0;

    return {
      key: def.key,
      label: def.label,
      color: def.color,
      latestLabel: formatChartValue(latestValue),
      points,
      path,
    };
  });

  return {
    width,
    height,
    padding,
    labels,
    yTicks,
    series,
  };
}

const pushChart = computed(() =>
  buildChart(pushTrend.value, [
    { key: "videos", label: "视频", color: "#2563eb", getValue: (row) => row.videos || 0 },
    { key: "dynamics", label: "动态", color: "#0ea5e9", getValue: (row) => row.dynamics || 0 },
    { key: "pushes", label: "推送", color: "#8b5cf6", getValue: (row) => row.pushes || 0 },
  ])
);

const llmChart = computed(() =>
  buildChart(llmTrend.value, [
    { key: "calls", label: "调用次数", color: "#f97316", getValue: (row) => row.calls || 0 },
    { key: "tokens", label: "千 Token", color: "#14b8a6", getValue: (row) => (row.tokens || 0) / 1000 },
  ])
);

function runtimeTagColor(status?: string | null): string {
  if (status === "error") return "red";
  if (status === "paused") return "orange";
  if (status === "running") return "green";
  return "arcoblue";
}

function errorTagColor(module?: string | null): string {
  if (module === "video") return "green";
  if (module === "dynamic") return "gold";
  if (module === "podcast") return "gold";
  if (module === "push") return "red";
  return "arcoblue";
}

function goTaskCenter() {
  router.push("/tasks");
}

function goLogCenter() {
  router.push("/logs");
}

async function load() {
  overview.value = await api.get<MonitorOverviewResponse>("/monitor/overview");
}

onMounted(load);
</script>
