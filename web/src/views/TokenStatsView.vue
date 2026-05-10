<template>
  <div class="dashboard">
    <section class="hero-card">
      <div class="hero-copy">
        <div class="hero-eyebrow">TOKEN STATS</div>
        <h1>Token统计</h1>
        <p class="hero-description">查看 LLM 调用规模、模型成本、近 7 / 30 天趋势和调用明细。</p>
        <div>费用按环境配置的输入/输出单价估算</div>
        <div class="hero-badges">
          <span class="hero-badge">调用次数</span>
          <span class="hero-badge">Token 消耗</span>
          <span class="hero-badge">模型维度</span>
          <span class="hero-badge">成本趋势</span>
        </div>
      </div>

      <div class="hero-panel">
        <div>
          <div class="hero-panel__label">总调用</div>
          <div class="hero-panel__value">{{ overview.llm_calls }}</div>
          <div class="hero-panel__meta">总 Token {{ overview.llm_total_tokens }}</div>
        </div>
        <div class="hero-panel__split">
          <div>
            <div class="hero-panel__mini-label">提示词</div>
            <div class="hero-panel__mini-value">{{ overview.llm_prompt_tokens }}</div>
          </div>
          <div>
            <div class="hero-panel__mini-label">回复</div>
            <div class="hero-panel__mini-value">{{ overview.llm_completion_tokens }}</div>
          </div>
        </div>
      </div>
    </section>

    <div class="page-grid page-grid--five">
      <el-card v-for="item in cards" :key="item.label" class="stat-card stat-card--dashboard">
        <div class="stat-label">{{ item.label }}</div>
        <div class="stat-value">{{ item.value }}</div>
      </el-card>
    </div>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">趋势总览</div>
            <div class="section__desc">支持 7 天 / 30 天窗口切换</div>
          </div>
          <div class="trend-toolbar">
            <el-radio-group v-model="selectedWindow" size="small">
              <el-radio-button :label="7">7 天</el-radio-button>
              <el-radio-button :label="30">30 天</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>

      <div class="chart-stage">
        <svg class="line-chart" viewBox="0 0 900 260" preserveAspectRatio="none">
          <g v-for="y in [20, 70, 120, 170, 220]" :key="y">
            <line x1="48" :y1="y" x2="870" :y2="y" class="chart-gridline" />
          </g>
          <path :d="buildTrendPath(activeTrend.map((row) => row.calls))" class="chart-line" stroke="#f97316" />
          <path :d="buildTrendPath(activeTrend.map((row) => row.tokens))" class="chart-line" stroke="#8b5cf6" />
          <circle v-for="point in trendMarkers.calls" :key="point.key" :cx="point.cx" :cy="point.cy" r="4" class="chart-point" fill="#f97316" />
          <circle v-for="point in trendMarkers.tokens" :key="point.key" :cx="point.cx" :cy="point.cy" r="4" class="chart-point" fill="#8b5cf6" />
          <text v-for="label in chartLabels" :key="label.key" :x="label.x" y="248" class="chart-axis-label" text-anchor="middle">
            {{ label.text }}
          </text>
        </svg>
        <div class="chart-legend">
          <span class="chart-legend-item"><i class="chart-legend-dot" style="background: #f97316"></i>调用次数</span>
          <span class="chart-legend-item"><i class="chart-legend-dot" style="background: #8b5cf6"></i>Token</span>
        </div>
      </div>
    </el-card>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">每日 Token 消耗</div>
            <div class="section__desc">按天汇总提示词、回复和总 Token</div>
          </div>
        </div>
      </template>
      <el-table :data="dailyRows" stripe>
        <el-table-column prop="day" label="日期" width="140" />
        <el-table-column class-name="mobile-hide-sm" prop="calls" label="调用次数" width="100" />
        <el-table-column class-name="mobile-hide-sm" prop="prompt_tokens" label="提示词 Token" />
        <el-table-column class-name="mobile-hide-sm" prop="completion_tokens" label="回复 Token" />
        <el-table-column prop="total_tokens" label="总 Token" />
        <el-table-column label="费用" width="120">
          <template #default="{ row }">{{ formatYuan(calcTokenCostValue(row.prompt_tokens, row.completion_tokens)) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">模型 Token 消耗</div>
            <div class="section__desc">按 provider / model 聚合</div>
          </div>
        </div>
      </template>
      <el-table :data="modelRows" stripe>
        <el-table-column prop="provider" label="供应方" width="160">
          <template #default="{ row }">{{ translateProvider(row.provider) }}</template>
        </el-table-column>
        <el-table-column prop="model" label="模型" />
        <el-table-column class-name="mobile-hide-sm" prop="calls" label="调用次数" width="100" />
        <el-table-column class-name="mobile-hide-sm" prop="prompt_tokens" label="提示词 Token" />
        <el-table-column class-name="mobile-hide-sm" prop="completion_tokens" label="回复 Token" />
        <el-table-column prop="total_tokens" label="总 Token" />
        <el-table-column label="费用" width="120">
          <template #default="{ row }">{{ formatYuan(calcTokenCostValue(row.prompt_tokens, row.completion_tokens)) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">大模型调用记录</div>
            <div class="section__desc">支持内容类型、供应方、模型和成功状态筛选</div>
          </div>
        </div>
      </template>

      <div class="toolbar">
        <el-input v-model="usageFilters.content_type" clearable placeholder="内容类型" style="width: 160px" />
        <el-input v-model="usageFilters.provider" clearable placeholder="供应方" style="width: 160px" />
        <el-input v-model="usageFilters.model" clearable placeholder="模型" style="width: 160px" />
        <el-select v-model="usageFilters.success" clearable placeholder="是否成功" style="width: 160px">
          <el-option label="是" :value="true" />
          <el-option label="否" :value="false" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="loadUsage">查询</el-button>
        <el-button @click="resetUsage">重置</el-button>
      </div>

      <el-table :data="usageRows" v-loading="loading" stripe>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="content_type" label="内容类型" width="100">
          <template #default="{ row }">{{ translateContentType(row.content_type) }}</template>
        </el-table-column>
        <el-table-column prop="content_title" label="标题" min-width="220" />
        <el-table-column class-name="mobile-hide-sm" prop="uploader_name" label="作者" width="160" />
        <el-table-column prop="provider" label="供应方" width="120">
          <template #default="{ row }">{{ translateProvider(row.provider) }}</template>
        </el-table-column>
        <el-table-column prop="model" label="模型" width="180" />
        <el-table-column class-name="mobile-hide-sm" label="联网" width="90">
          <template #default="{ row }">
            <el-tag :type="row.web_search_enabled ? 'success' : 'info'">{{ row.web_search_enabled ? "是" : "否" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column class-name="mobile-hide-sm" label="模式" width="120">
          <template #default="{ row }">
            <el-tag :type="webSearchTagType(row.web_search_mode)">{{ translateWebSearchMode(row.web_search_mode) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column class-name="mobile-hide-sm" prop="prompt_tokens" label="提示词 Token" width="110" />
        <el-table-column class-name="mobile-hide-sm" prop="completion_tokens" label="回复 Token" width="110" />
        <el-table-column prop="total_tokens" label="总 Token" width="100" />
        <el-table-column label="费用" width="120">
          <template #default="{ row }">{{ formatYuan(calcTokenCostValue(row.prompt_tokens, row.completion_tokens)) }}</template>
        </el-table-column>
        <el-table-column class-name="mobile-hide-sm" prop="duration_ms" label="耗时(ms)" width="120" />
        <el-table-column prop="success" label="成功" width="100">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? "是" : "否" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column class-name="mobile-hide-sm" prop="error_message" label="错误信息" min-width="180">
          <template #default="{ row }">
            <span class="summary-box">{{ row.error_message || "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="toolbar" style="justify-content: flex-end; margin-top: 16px">
        <el-pagination
          layout="prev, pager, next, total, sizes"
          :current-page="usageFilters.page"
          :page-size="usageFilters.page_size"
          :page-sizes="[10, 20, 50, 100]"
          :total="usageTotal"
          @current-change="changeUsagePage"
          @size-change="changeUsagePageSize"
        />
      </div>
    </el-card>

    <el-drawer v-model="detailVisible" title="大模型调用详情" size="50%">
      <template v-if="activeRow">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="标题">{{ activeRow.content_title || "-" }}</el-descriptions-item>
          <el-descriptions-item label="内容类型">{{ translateContentType(activeRow.content_type) }}</el-descriptions-item>
          <el-descriptions-item label="供应方">{{ translateProvider(activeRow.provider) }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ activeRow.model || "-" }}</el-descriptions-item>
          <el-descriptions-item label="联网">
            <el-tag :type="activeRow.web_search_enabled ? 'success' : 'info'">{{ activeRow.web_search_enabled ? "是" : "否" }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="模式">
            <el-tag :type="webSearchTagType(activeRow.web_search_mode)">{{ translateWebSearchMode(activeRow.web_search_mode) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="降级原因">{{ activeRow.web_search_fallback_reason || "-" }}</el-descriptions-item>
          <el-descriptions-item label="Token 明细">
            {{ activeRow.prompt_tokens || 0 }} / {{ activeRow.completion_tokens || 0 }} / {{ activeRow.total_tokens || 0 }}
          </el-descriptions-item>
          <el-descriptions-item label="费用">{{ formatYuan(calcTokenCostValue(activeRow.prompt_tokens, activeRow.completion_tokens)) }}</el-descriptions-item>
          <el-descriptions-item label="原始响应">
            <pre class="summary-box">{{ prettyJson(activeRow.raw_response) }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import { api } from "../api";
import type {
  EnvConfigItem,
  LLMUsageDetail,
  LlmUsageItem,
  Overview,
  PageResult,
  StatsSummary,
  TokenDailyItem,
  TokenModelItem,
} from "../types";
import {
  calcTokenCostByRates,
  formatDateTime,
  formatYuan,
  resolveTokenCostRates,
  prettyJson,
  translateContentType,
  translateProvider,
  translateWebSearchMode,
} from "../utils";

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
const statsSummary = ref<StatsSummary | null>(null);
const envConfigItems = ref<EnvConfigItem[]>([]);
const dailyRows = ref<TokenDailyItem[]>([]);
const modelRows = ref<TokenModelItem[]>([]);
const usageRows = ref<LlmUsageItem[]>([]);
const usageTotal = ref(0);
const loading = ref(false);
const detailVisible = ref(false);
const activeRow = ref<LLMUsageDetail | null>(null);
const selectedWindow = ref<7 | 30>(7);

const usageFilters = reactive({
  page: 1,
  page_size: 20,
  content_type: "",
  provider: "",
  model: "",
  success: undefined as boolean | undefined,
});

const tokenCostRates = computed(() => resolveTokenCostRates(envConfigItems.value));

const cards = computed(() => [
  { label: "调用次数", value: overview.value.llm_calls },
  { label: "总 Token", value: overview.value.llm_total_tokens },
  { label: "提示词 Token", value: overview.value.llm_prompt_tokens },
  { label: "回复 Token", value: overview.value.llm_completion_tokens },
  {
    label: "总费用",
    value: formatYuan(
      calcTokenCostByRates(overview.value.llm_prompt_tokens, overview.value.llm_completion_tokens, tokenCostRates.value),
    ),
  },
]);

function calcTokenCostValue(promptTokens?: number | null, completionTokens?: number | null) {
  return calcTokenCostByRates(promptTokens, completionTokens, tokenCostRates.value);
}

function webSearchTagType(mode?: string | null): "info" | "success" | "warning" | "danger" {
  if (!mode || mode === "disabled") return "info";
  if (mode === "responses") return "success";
  if (mode === "chat_completions") return "warning";
  if (mode === "unsupported") return "danger";
  return "info";
}

const activeTrend = computed(() => (selectedWindow.value === 30 ? statsSummary.value?.trend_30_days.llm_days || [] : statsSummary.value?.trend_7_days.llm_days || []));

function normalizePoints(values: number[]) {
  const max = Math.max(1, ...values);
  const stepX = values.length > 1 ? 822 / (values.length - 1) : 0;
  return values.map((value, index) => ({
    x: 48 + stepX * index,
    y: 220 - (value / max) * 180,
  }));
}

function buildTrendPath(values: number[]) {
  const points = normalizePoints(values);
  if (!points.length) return "";
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
}

const chartLabels = computed(() =>
  activeTrend.value.map((row, index) => ({
    key: `${row.day}-${index}`,
    x: 48 + (activeTrend.value.length > 1 ? (822 / (activeTrend.value.length - 1)) * index : 0),
    text: row.day.slice(5),
  })),
);

const trendMarkers = computed(() => {
  const calls = normalizePoints(activeTrend.value.map((row) => row.calls || 0)).map((point, index) => ({
    key: `calls-${index}`,
    cx: point.x,
    cy: point.y,
  }));
  const tokens = normalizePoints(activeTrend.value.map((row) => row.tokens || 0)).map((point, index) => ({
    key: `tokens-${index}`,
    cx: point.x,
    cy: point.y,
  }));
  return { calls, tokens };
});

async function loadStats() {
  const [ov, daily, models, summary, env] = await Promise.all([
    api.get<Overview>("/overview"),
    api.get<TokenDailyItem[]>("/stats/tokens/daily"),
    api.get<TokenModelItem[]>("/stats/tokens/models"),
    api.get<StatsSummary>("/stats/summary"),
    api.get<{ items: EnvConfigItem[] }>("/configs/env"),
  ]);
  overview.value = ov;
  dailyRows.value = daily;
  modelRows.value = models;
  statsSummary.value = summary;
  envConfigItems.value = env.items;
}

async function loadUsage() {
  loading.value = true;
  try {
    const data = await api.get<PageResult<LlmUsageItem>>(
      `/llm-usage?${new URLSearchParams(
        Object.entries(usageFilters).reduce<Record<string, string>>((acc, [key, value]) => {
          if (value !== undefined && value !== "" && value !== null) acc[key] = String(value);
          return acc;
        }, {}),
      ).toString()}`,
    );
    usageRows.value = data.items;
    usageTotal.value = data.total;
  } finally {
    loading.value = false;
  }
}

function resetUsage() {
  usageFilters.page = 1;
  usageFilters.content_type = "";
  usageFilters.provider = "";
  usageFilters.model = "";
  usageFilters.success = undefined;
  loadUsage();
}

function changeUsagePage(page: number) {
  usageFilters.page = page;
  loadUsage();
}

function changeUsagePageSize(size: number) {
  usageFilters.page_size = size;
  usageFilters.page = 1;
  loadUsage();
}

async function openDetail(row: LlmUsageItem) {
  try {
    activeRow.value = await api.get<LLMUsageDetail>(`/llm-usage/${row.id}`);
    detailVisible.value = true;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载调用详情失败");
  }
}

onMounted(async () => {
  await Promise.all([loadStats(), loadUsage()]);
});
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
}

@media (max-width: 768px) {
  .dashboard {
    gap: 14px;
  }

  .dashboard :deep(.hero-card),
  .dashboard :deep(.section-header),
  .dashboard :deep(.toolbar) {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .dashboard :deep(.hero-panel),
  .dashboard :deep(.hero-panel__split) {
    width: 100%;
  }

  .dashboard :deep(.page-grid--five) {
    grid-template-columns: minmax(0, 1fr);
  }

  .dashboard :deep(.trend-toolbar) {
    width: 100%;
    justify-content: flex-start;
  }

  .dashboard :deep(.toolbar .el-input),
  .dashboard :deep(.toolbar .el-select),
  .dashboard :deep(.toolbar .el-date-editor),
  .dashboard :deep(.toolbar .el-button) {
    width: 100% !important;
  }

  .dashboard :deep(.page-card),
  .dashboard :deep(.el-dialog__body) {
    padding: 14px;
  }

  .dashboard :deep(.chart-stage) {
    overflow-x: auto;
    padding-bottom: 8px;
  }

  .dashboard :deep(.line-chart) {
    min-width: 680px;
  }

  .dashboard :deep(.el-table__cell) {
    padding: 8px 6px;
    font-size: 12px;
  }

  .dashboard :deep(.el-table .cell) {
    white-space: normal;
    line-height: 1.45;
  }

  .dashboard :deep(.mobile-hide-sm),
  .dashboard :deep(.mobile-hide-md) {
    display: none !important;
  }

  .dashboard :deep(.el-pagination) {
    flex-wrap: wrap;
    gap: 8px;
  }
}
</style>
