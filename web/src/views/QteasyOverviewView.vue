<template>
  <div class="dashboard qteasy-page">
    <section class="hero-card">
      <div class="hero-copy">
        <div class="hero-eyebrow">QTEASY / OVERVIEW</div>
        <h1>量化回测总览</h1>
        <p class="hero-description">
          这里是量化系统的工作台首页。先确认服务健康度和数据准备情况，再进入策略目录、任务工作台和结果分析。
          所有长任务统一以 job_id 驱动，页面不依赖人工读日志。
        </p>
        <div class="hero-badges">
          <span class="hero-badge">服务状态</span>
          <span class="hero-badge">任务态势</span>
          <span class="hero-badge">结果中心</span>
          <span class="hero-badge">快捷入口</span>
        </div>
      </div>

      <div class="hero-panel">
        <div>
          <div class="hero-panel__label">服务状态</div>
          <div class="hero-panel__value">{{ healthLabel }}</div>
          <div class="hero-panel__meta">{{ health.service || "Qteasy FastAPI" }}</div>
        </div>
        <div class="hero-panel__split">
          <div>
            <div class="hero-panel__mini-label">API 地址</div>
            <div class="hero-panel__mini-value">{{ apiUrlLabel }}</div>
          </div>
          <div>
            <div class="hero-panel__mini-label">支持任务</div>
            <div class="hero-panel__mini-value">{{ taskTypeCount }}</div>
          </div>
        </div>
        <div class="hero-panel__actions">
          <el-button type="primary" :loading="loading" @click="loadAll">刷新</el-button>
          <el-button @click="$router.push('/qteasy/tasks')">任务工作台</el-button>
          <el-button @click="$router.push('/qteasy/results')">结果分析</el-button>
        </div>
      </div>
    </section>

    <div class="health-grid">
      <el-card v-for="card in summaryCards" :key="card.label" class="health-card">
        <div class="health-card__title">{{ card.label }}</div>
        <div class="health-card__value">{{ card.value }}</div>
        <div class="health-card__meta">{{ card.meta }}</div>
      </el-card>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="warning" :closable="false" show-icon />

    <div class="chart-grid">
      <el-card class="page-card section">
        <template #header>
          <div class="section-header section-header--space-between">
            <div>
              <div class="section__title">工作流入口</div>
              <div class="section__desc">从数据准备、策略选择，到任务执行和结果分析的完整闭环。</div>
            </div>
            <el-space wrap>
              <el-button text @click="$router.push('/qteasy/strategies')">策略目录</el-button>
              <el-button text @click="$router.push('/qteasy/data')">数据中心</el-button>
              <el-button text @click="$router.push('/qteasy/tools')">高级工具</el-button>
            </el-space>
          </div>
        </template>

        <div class="qteasy-workflow-grid">
          <button
            v-for="item in workflowCards"
            :key="item.path"
            class="qteasy-workflow-card"
            type="button"
            @click="$router.push(item.path)"
          >
            <div class="qteasy-workflow-card__title">{{ item.title }}</div>
            <div class="qteasy-workflow-card__desc">{{ item.desc }}</div>
            <div class="qteasy-workflow-card__meta">{{ item.meta }}</div>
          </button>
        </div>
      </el-card>

      <el-card class="page-card section">
        <template #header>
          <div class="section-header section-header--space-between">
            <div>
              <div class="section__title">运行配置摘要</div>
              <div class="section__desc">从 /meta 读取当前运行时摘要，详细 settings 仅保留在调试区。</div>
            </div>
            <el-tag type="info" effect="plain">{{ configReady ? "已就绪" : "未就绪" }}</el-tag>
          </div>
        </template>

        <div class="qteasy-kv-grid">
          <div v-for="item in configSummary" :key="item.label" class="qteasy-kv">
            <span class="qteasy-kv__label">{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>

        <el-collapse v-model="debugPanels" class="qteasy-debug-collapse">
          <el-collapse-item title="查看原始 settings" name="settings">
            <pre class="summary-box qteasy-result-pre">{{ prettyJson(meta.settings || {}) }}</pre>
          </el-collapse-item>
        </el-collapse>
      </el-card>
    </div>

    <div class="chart-grid">
      <el-card class="page-card section">
        <template #header>
          <div class="section-header section-header--space-between">
            <div>
              <div class="section__title">最近任务</div>
              <div class="section__desc">优先关注运行中和最近完成的任务，快速进入任务详情。</div>
            </div>
            <el-button text @click="$router.push('/qteasy/tasks')">打开任务工作台</el-button>
          </div>
        </template>

        <el-table :data="recentJobs" v-loading="loading" stripe>
          <el-table-column prop="job_id" label="Job ID" min-width="220">
            <template #default="{ row }">
              <span class="summary-box">{{ row.job_id }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="job_name" label="任务名称" min-width="180" />
          <el-table-column prop="task_type" label="类型" width="160" />
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="jobStatusTag(row.status)">{{ translateJobStatus(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="progress" label="进度" width="100">
            <template #default="{ row }">{{ row.progress ?? 0 }}%</template>
          </el-table-column>
          <el-table-column prop="current_step" label="当前步骤" min-width="220">
            <template #default="{ row }">
              <span class="summary-box">{{ row.current_step || "-" }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button link type="primary" @click="$router.push({ path: '/qteasy/tasks', query: { job_id: row.job_id } })">
                详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="page-card section">
        <template #header>
          <div class="section-header section-header--space-between">
            <div>
              <div class="section__title">最近结果</div>
              <div class="section__desc">优先展示已落到本地结果库的数据，方便直接进入分析页。</div>
            </div>
            <el-button text @click="$router.push('/qteasy/results')">打开结果分析</el-button>
          </div>
        </template>

        <el-table :data="recentResults" v-loading="loading" stripe>
          <el-table-column prop="job_id" label="Job ID" min-width="220">
            <template #default="{ row }">
              <span class="summary-box">{{ row.job_id }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="job_name" label="任务名称" min-width="180" />
          <el-table-column prop="strategy_id" label="策略" min-width="150" />
          <el-table-column prop="parsed_ok" label="解析" width="110">
            <template #default="{ row }">
              <el-tag :type="row.parsed_ok ? 'success' : 'warning'">{{ row.parsed_ok ? "已解析" : "部分缺失" }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button link type="primary" @click="$router.push({ path: '/qteasy/results', query: { job_id: row.job_id } })">
                分析
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { qteasyApi, qteasyExtractItems, qteasyUnwrap } from "../services/qteasy";
import type { QteasyHealthResponse, QteasyJobItem, QteasyMetaResponse, QteasyStoredResultItem } from "../types";
import { formatDateTime, prettyJson } from "../utils";

type SummaryCard = {
  label: string;
  value: string;
  meta: string;
};

type WorkflowCard = {
  title: string;
  desc: string;
  meta: string;
  path: string;
};

const loading = ref(false);
const errorMessage = ref("");
const health = ref<QteasyHealthResponse>({});
const meta = ref<QteasyMetaResponse>({});
const recentJobs = ref<QteasyJobItem[]>([]);
const recentResults = ref<QteasyStoredResultItem[]>([]);
const debugPanels = ref<string[]>([]);

const taskTypes = computed(() => meta.value.task_types || []);
const taskTypeCount = computed(() => taskTypes.value.length);
const apiUrlLabel = computed(() => health.value.apiUrl || String(meta.value.settings?.host || "-"));
const healthLabel = computed(() => {
  const status = String(health.value.status || "").toLowerCase();
  if (status === "ok" || health.value.ok) return "正常";
  return status || "-";
});
const configReady = computed(() => Boolean(Object.keys(meta.value.settings || {}).length));

const summaryCards = computed<SummaryCard[]>(() => [
  { label: "服务状态", value: healthLabel.value, meta: health.value.version || health.value.service || "-" },
  { label: "任务类型", value: String(taskTypeCount.value), meta: taskTypes.value.join(" / ") || "-" },
  { label: "最近任务", value: String(recentJobs.value.length), meta: "最近拉取的 job 列表" },
  { label: "最近结果", value: String(recentResults.value.length), meta: "最近同步到本地的结果" },
]);

const workflowCards = computed<WorkflowCard[]>(() => [
  { title: "策略目录", desc: "先选内置或自定义策略，再带入任务工作台。", meta: "内置 / 自定义", path: "/qteasy/strategies" },
  { title: "任务工作台", desc: "统一创建和追踪回测、优化、数据同步任务。", meta: "新建 / 运行中 / 历史", path: "/qteasy/tasks" },
  { title: "结果分析", desc: "查看本地结果、对比策略表现、打开图表详情。", meta: "本地结果优先", path: "/qteasy/results" },
  { title: "数据中心", desc: "查看数据健康度、行情查询和股票筛选。", meta: "概览 / 查询", path: "/qteasy/data" },
  { title: "高级工具", desc: "配置、报表和 RPC 调试统一收纳。", meta: "次级入口", path: "/qteasy/tools" },
]);

const configSummary = computed(() => {
  const entries = Object.entries(meta.value.settings || {}).slice(0, 6);
  return entries.map(([key, value]) => ({
    label: key,
    value: formatValue(value),
  }));
});

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return prettyJson(value as Record<string, unknown>);
}

function translateJobStatus(value?: string | null): string {
  const mapping: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    succeeded: "成功",
    failed: "失败",
    cancelled: "已取消",
  };
  return value ? mapping[value] || value : "-";
}

function jobStatusTag(value?: string | null): "info" | "success" | "warning" | "danger" {
  if (value === "succeeded") return "success";
  if (value === "running" || value === "queued") return "warning";
  if (value === "failed" || value === "cancelled") return "danger";
  return "info";
}

async function loadAll(): Promise<void> {
  loading.value = true;
  errorMessage.value = "";
  try {
    const [healthResp, metaResp, jobsResp, resultsResp] = await Promise.allSettled([
      qteasyApi.get<QteasyHealthResponse>("/health"),
      qteasyApi.get<QteasyMetaResponse>("/meta"),
      qteasyApi.get<unknown>("/jobs", { limit: 8, offset: 0 }),
      qteasyApi.get<{ items?: QteasyStoredResultItem[] }>("/results", { page: 1, page_size: 8 }),
    ]);

    if (healthResp.status === "fulfilled") {
      health.value = qteasyUnwrap<QteasyHealthResponse>(healthResp.value, {});
    }
    if (metaResp.status === "fulfilled") {
      meta.value = qteasyUnwrap<QteasyMetaResponse>(metaResp.value, {});
    }
    if (jobsResp.status === "fulfilled") {
      recentJobs.value = qteasyExtractItems<QteasyJobItem>(jobsResp.value);
    }
    if (resultsResp.status === "fulfilled") {
      recentResults.value = Array.isArray(resultsResp.value.items) ? resultsResp.value.items : [];
    }

    if (healthResp.status === "rejected" || metaResp.status === "rejected" || jobsResp.status === "rejected" || resultsResp.status === "rejected") {
      const reason =
        healthResp.status === "rejected"
          ? healthResp.reason
          : metaResp.status === "rejected"
            ? metaResp.reason
            : jobsResp.status === "rejected"
              ? jobsResp.reason
              : resultsResp.status === "rejected"
                ? resultsResp.reason
                : null;
      if (reason) {
        errorMessage.value = reason instanceof Error ? reason.message : String(reason);
      }
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadAll();
});
</script>
