<template>
  <div class="dashboard">
    <section class="hero-card">
      <div class="hero-copy">
        <div class="hero-eyebrow">HOME OVERVIEW</div>
        <h1>内容、推送、模型调用一屏掌握</h1>
        <p class="hero-description">
          这里把视频、动态、推送、Token 消耗和模型调用放到同一个页面里，
          先看趋势，再看细节，最后看最近错误摘要。
        </p>

        <div>费用按环境配置的输入/输出单价估算</div>
        <div class="hero-badges">
          <span class="hero-badge">视频 {{ overview.videos }}</span>
          <span class="hero-badge">动态 {{ overview.dynamics }}</span>
          <span class="hero-badge">小宇宙 {{ overview.podcasts }}</span>
          <span class="hero-badge">推送 {{ overview.push_records }}</span>
          <span class="hero-badge">LLM 调用 {{ overview.llm_calls }}</span>
        </div>
      </div>

      <div class="hero-panel">
        <div class="hero-panel__label">最近 {{ trendWindowLabel }} 推送</div>
        <div class="hero-panel__value">{{ recentPushTotal }}</div>
        <div class="hero-panel__meta">按天汇总的推送记录，包含视频、动态和小宇宙内容</div>
        <div class="hero-panel__split">
          <div>
            <div class="hero-panel__mini-label">LLM Token</div>
            <div class="hero-panel__mini-value">{{ overview.llm_total_tokens }}</div>
          </div>
          <div>
            <div class="hero-panel__mini-label">总成本</div>
            <div class="hero-panel__mini-value">{{ formatYuan(totalLlmCost) }}</div>
          </div>
        </div>
      </div>
    </section>

    <div class="page-grid page-grid--five">
      <a-card v-for="item in cards" :key="item.label" class="stat-card stat-card--dashboard" :bordered="false">
        <div class="stat-label">{{ item.label }}</div>
        <div class="stat-value">{{ item.value }}</div>
      </a-card>
    </div>

    <div class="health-grid">
      <a-card v-for="item in healthCards" :key="item.module" class="page-card health-card" :bordered="false">
        <div class="health-card__title">{{ item.label }}</div>
        <div class="health-card__value">{{ formatPercent(item.success_rate) }}</div>
        <div class="health-card__meta">失败率 {{ formatPercent(item.failure_rate) }}</div>
        <div class="health-card__stats">
          <div>
            <span>成功</span>
            <strong>{{ item.success_count }}</strong>
          </div>
          <div>
            <span>失败</span>
            <strong>{{ item.failure_count }}</strong>
          </div>
          <div>
            <span>终态</span>
            <strong>{{ item.terminal_total }}</strong>
          </div>
        </div>
        <div class="health-card__footer">
          <span>总数 {{ item.total_count }}</span>
          <span>失败 {{ item.failure_count }}</span>
        </div>
      </a-card>
    </div>

    <div class="chart-grid">
      <a-card class="page-card section chart-card" :bordered="false">
        <div class="section-header">
          <div>
            <div class="section__title">最近 {{ trendWindowLabel }} 推送趋势</div>
            <div class="section__desc">视频、动态和推送量按天展示</div>
          </div>
          <div class="trend-toolbar">
            <span class="muted">窗口</span>
            <a-radio-group v-model="selectedWindow" type="button">
              <a-radio :value="7">7 天</a-radio>
              <a-radio :value="30">30 天</a-radio>
            </a-radio-group>
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

      <a-card class="page-card section chart-card" :bordered="false">
        <div class="section-header">
          <div>
            <div class="section__title">最近 {{ trendWindowLabel }} LLM 用量趋势</div>
            <div class="section__desc">调用次数与 Token 消耗的变化</div>
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

    <a-card class="page-card section" :bordered="false">
      <div class="section-header">
        <div>
          <div class="section__title">状态分布</div>
          <div class="section__desc">视频、动态、小宇宙、推送渠道与模型成功/失败分布</div>
        </div>
      </div>

      <div class="section-grid">
        <div>
          <div class="muted section-subtitle">视频</div>
          <a-table :data="summary?.video_status || []" :pagination="false" size="small">
            <template #columns>
              <a-table-column title="状态">
                <template #cell="{ record }">{{ translateStatus(record.status) }}</template>
              </a-table-column>
              <a-table-column data-index="count" title="数量" :width="100" />
            </template>
          </a-table>
        </div>
        <div>
          <div class="muted section-subtitle">动态</div>
          <a-table :data="summary?.dynamic_status || []" :pagination="false" size="small">
            <template #columns>
              <a-table-column title="状态">
                <template #cell="{ record }">{{ translateStatus(record.status) }}</template>
              </a-table-column>
              <a-table-column data-index="count" title="数量" :width="100" />
            </template>
          </a-table>
        </div>
        <div>
          <div class="muted section-subtitle">小宇宙</div>
          <a-table :data="summary?.podcast_status || []" :pagination="false" size="small">
            <template #columns>
              <a-table-column title="状态">
                <template #cell="{ record }">{{ translateStatus(record.status) }}</template>
              </a-table-column>
              <a-table-column data-index="count" title="数量" :width="100" />
            </template>
          </a-table>
        </div>
        <div>
          <div class="muted section-subtitle">推送</div>
          <a-table :data="summary?.push_channel_status || []" :pagination="false" size="small">
            <template #columns>
              <a-table-column data-index="channel" title="渠道" :width="120" />
              <a-table-column title="状态" :width="120">
                <template #cell="{ record }">{{ translateStatus(record.status) }}</template>
              </a-table-column>
              <a-table-column data-index="count" title="数量" :width="100" />
            </template>
          </a-table>
        </div>
        <div>
          <div class="muted section-subtitle">模型</div>
          <a-table :data="summary?.llm_provider_status || []" :pagination="false" size="small">
            <template #columns>
              <a-table-column data-index="provider" title="供应商" :width="120" />
              <a-table-column title="成功" :width="100">
                <template #cell="{ record }">{{ record.success ? "是" : "否" }}</template>
              </a-table-column>
              <a-table-column data-index="count" title="数量" :width="100" />
            </template>
          </a-table>
        </div>
      </div>
    </a-card>

    <a-card class="page-card section" :bordered="false">
      <div class="section-header">
        <div>
          <div class="section__title">最近错误摘要</div>
          <div class="section__desc">汇总最近的失败视频、动态、推送和 LLM 调用</div>
        </div>
      </div>

      <template v-if="recentErrors.length">
        <div class="error-list">
          <div v-for="item in recentErrors" :key="`${item.module}-${item.item_id}-${item.occurred_at}`" class="error-item">
            <div class="error-item__head">
              <div>
                <div class="error-item__title">{{ truncate(item.item_title || item.item_id, 80) }}</div>
                <div class="error-item__meta">
                  <a-tag size="small" color="arcoblue">{{ translateModule(item.module) }}</a-tag>
                  <span>{{ item.item_label }} {{ item.item_id }}</span>
                  <span v-if="item.status">状态 {{ translateStatus(item.status) }}</span>
                </div>
              </div>
              <div class="error-item__time">{{ formatDateTime(item.occurred_at) }}</div>
            </div>
            <div class="error-item__message">{{ truncate(item.error_message, 240) }}</div>
          </div>
        </div>
      </template>
      <a-empty v-else description="暂无错误摘要" />
    </a-card>

    <a-card class="page-card section" :bordered="false">
      <div class="section-header">
        <div>
          <div class="section__title">每日 Token 消耗</div>
          <div class="section__desc">看调用频率、Prompt/Completion 和估算成本</div>
        </div>
      </div>
      <a-table :data="dailyRows" :pagination="false">
        <template #columns>
          <a-table-column data-index="day" title="日期" :width="140" />
          <a-table-column data-index="calls" title="调用次数" :width="100" />
          <a-table-column data-index="prompt_tokens" title="Prompt Token" />
          <a-table-column data-index="completion_tokens" title="Completion Token" />
          <a-table-column data-index="total_tokens" title="总 Token" />
          <a-table-column title="成本" :width="120">
            <template #cell="{ record }">{{ formatYuan(calcTokenCostByRates(record.prompt_tokens, record.completion_tokens, tokenCostRates)) }}</template>
          </a-table-column>
        </template>
      </a-table>
    </a-card>

    <a-card class="page-card section" :bordered="false">
      <div class="section-header">
        <div>
          <div class="section__title">模型 Token 排行</div>
          <div class="section__desc">不同供应商 / 模型的调用结果</div>
        </div>
      </div>
      <a-table :data="modelRows" :pagination="false">
        <template #columns>
          <a-table-column data-index="provider" title="供应商" :width="160" />
          <a-table-column data-index="model" title="模型" />
          <a-table-column data-index="calls" title="调用次数" :width="100" />
          <a-table-column data-index="prompt_tokens" title="Prompt Token" />
          <a-table-column data-index="completion_tokens" title="Completion Token" />
          <a-table-column data-index="total_tokens" title="总 Token" />
          <a-table-column title="成本" :width="120">
            <template #cell="{ record }">{{ formatYuan(calcTokenCostByRates(record.prompt_tokens, record.completion_tokens, tokenCostRates)) }}</template>
          </a-table-column>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api } from "../api";
import type {
  EnvConfigItem,
  HealthMetricItem,
  RecentErrorItem,
  StatsSummary,
  TokenDailyItem,
  TokenModelItem,
  TrendWindowSummary,
  Overview,
} from "../types";
import {
  calcTokenCostByRates,
  formatDateTime,
  formatPercent,
  formatYuan,
  resolveTokenCostRates,
  translateModule,
  translateStatus,
  truncate,
} from "../utils";

type TrendRow = {
  day: string;
  videos?: number;
  dynamics?: number;
  pushes?: number;
  calls?: number;
  tokens?: number;
};

type ChartPoint = { index: number; x: number; y: number; value: number };
type ChartSeries = { key: string; label: string; color: string; latestLabel: string; points: ChartPoint[]; path: string };
type ChartTick = { value: number; y: number; label: string };
type ChartModel = { width: number; height: number; padding: { top: number; right: number; bottom: number; left: number }; labels: string[]; yTicks: ChartTick[]; series: ChartSeries[] };

const EMPTY_TREND_WINDOW: TrendWindowSummary = {
  push_days: [],
  llm_days: [],
};

const overview = ref<Overview>({
  videos: 0,
  dynamics: 0,
  podcasts: 0,
  push_records: 0,
  llm_calls: 0,
  llm_total_tokens: 0,
  llm_prompt_tokens: 0,
  llm_completion_tokens: 0,
});

const dailyRows = ref<TokenDailyItem[]>([]);
const modelRows = ref<TokenModelItem[]>([]);
const summary = ref<StatsSummary | null>(null);
const envConfigItems = ref<EnvConfigItem[]>([]);
const selectedWindow = ref<7 | 30>(7);

const currentTrendWindow = computed<TrendWindowSummary>(() => {
  if (!summary.value) {
    return EMPTY_TREND_WINDOW;
  }
  return selectedWindow.value === 30 ? summary.value.trend_30_days : summary.value.trend_7_days;
});

const pushTrend = computed<TrendRow[]>(() => currentTrendWindow.value.push_days as TrendRow[]);
const llmTrend = computed<TrendRow[]>(() => currentTrendWindow.value.llm_days as TrendRow[]);
const recentErrors = computed<RecentErrorItem[]>(() => summary.value?.recent_errors || []);
const healthCards = computed<HealthMetricItem[]>(() => summary.value?.health_metrics || []);
const trendWindowLabel = computed(() => (selectedWindow.value === 30 ? "30 天" : "7 天"));
const tokenCostRates = computed(() => resolveTokenCostRates(envConfigItems.value));

const recentPushTotal = computed(() => pushTrend.value.reduce((acc, row) => acc + (row.pushes || 0), 0));
const totalLlmCost = computed(() =>
  calcTokenCostByRates(overview.value.llm_prompt_tokens, overview.value.llm_completion_tokens, tokenCostRates.value),
);

const cards = computed(() => [
  { label: "视频总数", value: overview.value.videos },
  { label: "动态总数", value: overview.value.dynamics },
  { label: "小宇宙总数", value: overview.value.podcasts },
  { label: "推送记录", value: overview.value.push_records },
  { label: "LLM 调用", value: overview.value.llm_calls },
  { label: "总 Token", value: overview.value.llm_total_tokens },
]);

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

async function load() {
  const [ov, daily, models, stats, env] = await Promise.all([
    api.get<Overview>("/overview"),
    api.get<TokenDailyItem[]>("/stats/tokens/daily"),
    api.get<TokenModelItem[]>("/stats/tokens/models"),
    api.get<StatsSummary>("/stats/summary"),
    api.get<{ items: EnvConfigItem[] }>("/configs/env"),
  ]);
  overview.value = ov;
  dailyRows.value = daily;
  modelRows.value = models;
  summary.value = stats;
  envConfigItems.value = env.items;
}

onMounted(load);
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

@media (max-width: 1024px) {
  .dashboard :deep(.page-grid--five) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard :deep(.health-grid) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .dashboard {
    gap: 14px;
  }

  .dashboard :deep(.hero-card),
  .dashboard :deep(.section-header),
  .dashboard :deep(.trend-toolbar) {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .dashboard :deep(.hero-panel),
  .dashboard :deep(.hero-panel__split) {
    width: 100%;
  }

  .dashboard :deep(.hero-panel__split) {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .dashboard :deep(.page-grid--five),
  .dashboard :deep(.health-grid),
  .dashboard :deep(.chart-grid),
  .dashboard :deep(.section-grid) {
    grid-template-columns: minmax(0, 1fr);
  }

  .dashboard :deep(.page-card) {
    padding: 14px;
  }

  .dashboard :deep(.chart-stage) {
    overflow-x: auto;
    padding-bottom: 8px;
  }

  .dashboard :deep(.line-chart) {
    min-width: 680px;
  }

  .dashboard :deep(.chart-axis) {
    flex-wrap: wrap;
    gap: 8px 12px;
  }

  .dashboard :deep(.el-table__cell) {
    padding: 8px 6px;
    font-size: 12px;
  }

  .dashboard :deep(.el-table .cell) {
    white-space: normal;
    line-height: 1.45;
  }
}
</style>
