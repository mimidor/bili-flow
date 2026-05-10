<template>
  <div class="dashboard qteasy-page">
    <section class="hero-card">
      <div class="hero-copy">
        <div class="hero-eyebrow">QTEASY / RESULT ANALYSIS</div>
        <h1>结果分析</h1>
        <p class="hero-description">
          这里展示本地持久化后的回测和优化结果。默认优先看结构化指标、图表和对比，原始 payload 与 result 只保留在调试区。
        </p>
      </div>
      <div class="hero-panel">
        <div>
          <div class="hero-panel__label">当前结果</div>
          <div class="hero-panel__value">{{ currentResult?.job_name || currentResult?.job_id || "-" }}</div>
          <div class="hero-panel__meta">{{ currentResult?.strategy_id || currentResult?.strategy_path || "未选择" }}</div>
        </div>
        <div class="hero-panel__actions">
          <el-button type="primary" :loading="loading.list" @click="loadResults">刷新结果</el-button>
          <el-button :disabled="!compareLeftId || !compareRightId" @click="openCompareDrawer">打开对比</el-button>
        </div>
      </div>
    </section>

    <div class="health-grid">
      <el-card class="health-card">
        <div class="health-card__title">结果总数</div>
        <div class="health-card__value">{{ summary.total }}</div>
        <div class="health-card__meta">本地结果库</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">已解析</div>
        <div class="health-card__value">{{ summary.parsedOk }}</div>
        <div class="health-card__meta">parsed_ok = true</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">需要关注</div>
        <div class="health-card__value">{{ summary.needsAttention }}</div>
        <div class="health-card__meta">解析失败或任务失败</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">最近更新时间</div>
        <div class="health-card__value">{{ summary.latestLabel }}</div>
        <div class="health-card__meta">按更新时间倒序</div>
      </el-card>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="warning" :closable="false" show-icon />

    <div class="chart-grid">
      <el-card class="page-card section">
        <template #header>
          <div class="section-header section-header--space-between">
            <div>
              <div class="section__title">结果列表</div>
              <div class="section__desc">先选单个结果看详情，也可以把两个结果放进 A / B 做图表和指标对比。</div>
            </div>
            <el-space wrap>
              <el-button text @click="clearFilters">清空筛选</el-button>
              <el-button text @click="clearCompare">清空对比</el-button>
            </el-space>
          </div>
        </template>

        <div class="qteasy-form-grid qteasy-form-grid--wide qteasy-results-toolbar">
          <el-input v-model="filters.keyword" clearable placeholder="按任务名 / 策略 / Job ID 搜索" />
          <el-select v-model="filters.status" clearable placeholder="状态" filterable>
            <el-option v-for="item in statusOptions" :key="item" :label="translateJobStatus(item)" :value="item" />
          </el-select>
          <el-select v-model="filters.parsed" clearable placeholder="解析状态" filterable>
            <el-option label="全部" value="" />
            <el-option label="已解析" value="ok" />
            <el-option label="需要关注" value="bad" />
          </el-select>
          <el-button type="primary" :loading="loading.list" @click="loadResults">查询</el-button>
        </div>

        <el-table :data="filteredResults" v-loading="loading.list" stripe>
          <el-table-column prop="job_name" label="任务" min-width="180">
            <template #default="{ row }">
              <div class="summary-box">
                <div>{{ row.job_name || row.job_id }}</div>
                <div class="u-text-muted u-font-12">{{ row.job_id }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="策略" min-width="180">
            <template #default="{ row }">
              <div class="summary-box">
                <div>{{ row.strategy_id || row.strategy_path || "-" }}</div>
                <div class="u-text-muted u-font-12">{{ row.task_type }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)">{{ translateJobStatus(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="parsed_ok" label="解析" width="110">
            <template #default="{ row }">
              <el-tag :type="row.parsed_ok ? 'success' : 'warning'">{{ row.parsed_ok ? "已解析" : "需关注" }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="指标摘要" min-width="240">
            <template #default="{ row }">
              <span class="summary-box">{{ metricSummary(row.metrics) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <el-space>
                <el-button size="small" @click="openDetail(row.job_id)">详情</el-button>
                <el-button size="small" type="primary" plain @click="setCompareSide('left', row.job_id)">设为 A</el-button>
                <el-button size="small" type="success" plain @click="setCompareSide('right', row.job_id)">设为 B</el-button>
              </el-space>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-if="!loading.list && !filteredResults.length" description="没有符合条件的结果" class="u-mt-16" />
      </el-card>
    </div>

    <el-drawer v-model="detailVisible" size="72%" :title="detailTitle" destroy-on-close>
      <template v-if="detail">
        <div class="qteasy-results-detail">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="Job ID">{{ detail.job_id }}</el-descriptions-item>
            <el-descriptions-item label="任务名">{{ detail.job_name || "-" }}</el-descriptions-item>
            <el-descriptions-item label="任务类型">{{ detail.task_type }}</el-descriptions-item>
            <el-descriptions-item label="策略">{{ detail.strategy_id || detail.strategy_path || "-" }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusTag(detail.status)">{{ translateJobStatus(detail.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="解析">
              <el-tag :type="detail.parsed_ok ? 'success' : 'warning'">{{ detail.parsed_ok ? "已解析" : "需关注" }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="区间">{{ detail.invest_start || "-" }} ~ {{ detail.invest_end || "-" }}</el-descriptions-item>
            <el-descriptions-item label="最近同步">{{ formatDateTime(detail.last_synced_at) }}</el-descriptions-item>
          </el-descriptions>

          <div class="u-mt-16">
            <qteasy-backtest-charts :series="detailSeries" />
          </div>

          <el-collapse v-model="detailPanels" class="qteasy-debug-collapse u-mt-16">
            <el-collapse-item title="原始 payload" name="payload">
              <pre class="summary-box qteasy-result-pre">{{ prettyJson(detail.payload) }}</pre>
            </el-collapse-item>
            <el-collapse-item title="原始 result" name="result">
              <pre class="summary-box qteasy-result-pre">{{ prettyJson(detail.raw_result) }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </template>
    </el-drawer>

    <el-drawer v-model="compareVisible" size="90%" title="结果对比" destroy-on-close>
      <template v-if="compareLeft && compareRight">
        <div class="qteasy-results-compare-toolbar">
          <el-select v-model="compareLeftId" filterable placeholder="A" @change="loadCompareDetail('left')">
            <el-option v-for="item in results" :key="`left-${item.job_id}`" :label="item.job_name || item.job_id" :value="item.job_id" />
          </el-select>
          <el-select v-model="compareRightId" filterable placeholder="B" @change="loadCompareDetail('right')">
            <el-option v-for="item in results" :key="`right-${item.job_id}`" :label="item.job_name || item.job_id" :value="item.job_id" />
          </el-select>
          <el-button type="primary" @click="refreshCompare">刷新对比</el-button>
        </div>

        <qteasy-backtest-compare :left="compareLeft" :right="compareRight" />
      </template>
      <el-empty v-else description="请先选择两个结果作为 A / B" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";

import QteasyBacktestCharts from "../components/qteasy/QteasyBacktestCharts.vue";
import QteasyBacktestCompare from "../components/qteasy/QteasyBacktestCompare.vue";
import { qteasyApi, qteasyExtractItems } from "../services/qteasy";
import type {
  QteasyChartSeries,
  QteasyPerformanceMetrics,
  QteasyStoredResultDetail,
  QteasyStoredResultItem,
  QteasyStoredResultListResponse,
} from "../types";
import { formatDateTime, formatPercent, prettyJson } from "../utils";

const route = useRoute();
const loading = ref({ list: false, detail: false, compare: false });
const errorMessage = ref("");
const results = ref<QteasyStoredResultItem[]>([]);
const detail = ref<QteasyStoredResultDetail | null>(null);
const detailVisible = ref(false);
const detailPanels = ref<string[]>([]);
const compareVisible = ref(false);
const compareLeftId = ref("");
const compareRightId = ref("");
const compareLeft = ref<QteasyStoredResultDetail | null>(null);
const compareRight = ref<QteasyStoredResultDetail | null>(null);
const cache = ref<Record<string, QteasyStoredResultDetail>>({});

const filters = ref({
  keyword: "",
  status: "",
  parsed: "",
});

const statusOptions = ["queued", "running", "succeeded", "failed", "cancelled"];

const summary = computed(() => {
  const sorted = [...results.value].sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
  return {
    total: results.value.length,
    parsedOk: results.value.filter((item) => item.parsed_ok).length,
    needsAttention: results.value.filter((item) => item.parsed_ok === false || item.status === "failed").length,
    latestLabel: formatDateTime(sorted[0]?.updated_at),
  };
});

const filteredResults = computed(() => {
  const keyword = filters.value.keyword.trim().toLowerCase();
  return results.value.filter((item) => {
    if (filters.value.status && item.status !== filters.value.status) return false;
    if (filters.value.parsed === "ok" && !item.parsed_ok) return false;
    if (filters.value.parsed === "bad" && item.parsed_ok) return false;
    if (!keyword) return true;
    const haystack = [
      item.job_id,
      item.job_name,
      item.strategy_id,
      item.strategy_path,
      item.task_type,
      item.status,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(keyword);
  });
});

const currentResult = computed(() => detail.value || results.value[0] || null);
const detailTitle = computed(() => (detail.value ? `结果详情 - ${detail.value.job_name || detail.value.job_id}` : "结果详情"));
const detailSeries = computed<QteasyChartSeries>(() => toSeries(detail.value));

function statusTag(value?: string | null): "info" | "success" | "warning" | "danger" {
  if (value === "succeeded") return "success";
  if (value === "running" || value === "queued") return "warning";
  if (value === "failed" || value === "cancelled") return "danger";
  return "info";
}

function translateJobStatus(value?: string | null): string {
  const mapping: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    succeeded: "成功",
    failed: "失败",
    cancelled: "已取消",
  };
  if (!value) return "-";
  return mapping[value] || value;
}

function metricSummary(metrics?: QteasyPerformanceMetrics): string {
  if (!metrics || !Object.keys(metrics).length) return "-";
  const parts: string[] = [];
  const totalReturn = metrics.total_return;
  const annualReturn = metrics.annual_return;
  const maxDrawdown = metrics.max_drawdown;
  const sharpe = metrics.sharpe;
  if (typeof totalReturn === "number") parts.push(`总收益 ${formatPercent(totalReturn, 2)}`);
  if (typeof annualReturn === "number") parts.push(`年化 ${formatPercent(annualReturn, 2)}`);
  if (typeof maxDrawdown === "number") parts.push(`回撤 ${formatPercent(maxDrawdown, 2)}`);
  if (typeof sharpe === "number") parts.push(`夏普 ${sharpe.toFixed(2)}`);
  if (!parts.length) {
    const [firstKey] = Object.keys(metrics);
    return `${firstKey}: ${String((metrics as Record<string, unknown>)[firstKey])}`;
  }
  return parts.join(" / ");
}

function toSeries(value: QteasyStoredResultDetail | null): QteasyChartSeries {
  return {
    job_id: value?.job_id || "",
    metrics: value?.metrics || {},
    equity_curve: value?.equity_curve || [],
    benchmark_curve: value?.benchmark_curve || [],
    drawdown_curve: value?.drawdown_curve || [],
    return_histogram: value?.return_histogram || [],
    parsed_ok: value?.parsed_ok,
    parse_message: value?.parse_message,
  };
}

function normalizeDetail(item: QteasyStoredResultDetail | QteasyStoredResultItem): QteasyStoredResultDetail {
  return {
    id: "id" in item && typeof item.id === "number" ? item.id : -1,
    job_id: item.job_id,
    task_type: item.task_type,
    job_name: item.job_name || null,
    strategy_id: item.strategy_id || null,
    strategy_path: item.strategy_path || null,
    symbol_pool:
      "symbol_pool" in item && Array.isArray((item as Record<string, unknown>).symbol_pool)
        ? ((item as Record<string, unknown>).symbol_pool as string[])
        : [],
    benchmark: item.benchmark || null,
    invest_start: item.invest_start || null,
    invest_end: item.invest_end || null,
    status: item.status,
    metrics: item.metrics || {},
    parsed_ok: item.parsed_ok,
    parse_message: item.parse_message || null,
    last_synced_at: item.last_synced_at || null,
    created_at: item.created_at || null,
    updated_at: item.updated_at || null,
    payload: "payload" in item ? (item as QteasyStoredResultDetail).payload || null : null,
    raw_result: "raw_result" in item ? (item as QteasyStoredResultDetail).raw_result || null : null,
    equity_curve: "equity_curve" in item ? (item as QteasyStoredResultDetail).equity_curve || [] : [],
    benchmark_curve: "benchmark_curve" in item ? (item as QteasyStoredResultDetail).benchmark_curve || [] : [],
    drawdown_curve: "drawdown_curve" in item ? (item as QteasyStoredResultDetail).drawdown_curve || [] : [],
    return_histogram: "return_histogram" in item ? (item as QteasyStoredResultDetail).return_histogram || [] : [],
  };
}

async function loadResults(): Promise<void> {
  loading.value.list = true;
  errorMessage.value = "";
  try {
    const payload = await qteasyApi.get<QteasyStoredResultListResponse>("/results", {
      page: 1,
      page_size: 100,
    });
    results.value = payload.items || qteasyExtractItems<QteasyStoredResultItem>(payload);
    if (!compareLeftId.value && results.value.length) {
      compareLeftId.value = results.value[0].job_id;
    }
    if (!compareRightId.value && results.value.length > 1) {
      compareRightId.value = results.value[1].job_id;
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.value.list = false;
  }
}

async function loadDetailById(jobId: string): Promise<QteasyStoredResultDetail> {
  const cached = cache.value[jobId];
  if (cached) return cached;
  const detailPayload = await qteasyApi.get<QteasyStoredResultDetail>(`/results/${encodeURIComponent(jobId)}`);
  const normalized = normalizeDetail(detailPayload);
  cache.value = { ...cache.value, [jobId]: normalized };
  return normalized;
}

async function openDetail(jobId: string): Promise<void> {
  if (!jobId) return;
  loading.value.detail = true;
  errorMessage.value = "";
  try {
    detail.value = await loadDetailById(jobId);
    detailVisible.value = true;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.value.detail = false;
  }
}

async function setCompareSide(side: "left" | "right", jobId: string): Promise<void> {
  if (!jobId) return;
  if (side === "left") {
    compareLeftId.value = jobId;
    compareLeft.value = await loadDetailById(jobId);
  } else {
    compareRightId.value = jobId;
    compareRight.value = await loadDetailById(jobId);
  }
}

async function loadCompareDetail(side: "left" | "right"): Promise<void> {
  const id = side === "left" ? compareLeftId.value : compareRightId.value;
  if (!id) {
    if (side === "left") compareLeft.value = null;
    else compareRight.value = null;
    return;
  }
  try {
    const next = await loadDetailById(id);
    if (side === "left") compareLeft.value = next;
    else compareRight.value = next;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  }
}

async function openCompareDrawer(): Promise<void> {
  if (!compareLeftId.value || !compareRightId.value) {
    ElMessage.warning("请先选择两个结果作为 A / B");
    return;
  }
  compareVisible.value = true;
  await Promise.all([loadCompareDetail("left"), loadCompareDetail("right")]);
}

async function refreshCompare(): Promise<void> {
  if (!compareLeftId.value || !compareRightId.value) return;
  await Promise.all([loadCompareDetail("left"), loadCompareDetail("right")]);
}

function clearFilters(): void {
  filters.value.keyword = "";
  filters.value.status = "";
  filters.value.parsed = "";
}

function clearCompare(): void {
  compareLeftId.value = "";
  compareRightId.value = "";
  compareLeft.value = null;
  compareRight.value = null;
}

watch(
  () => route.query.job_id,
  async (jobId) => {
    if (typeof jobId === "string" && jobId) {
      await openDetail(jobId);
    }
  },
  { immediate: true },
);

onMounted(() => {
  void loadResults();
});
</script>
