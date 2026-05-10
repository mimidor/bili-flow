<template>
  <div class="dashboard qteasy-page">
    <section class="hero-card">
      <div class="hero-copy">
        <div class="hero-eyebrow">QTEASY / TASK WORKBENCH</div>
        <h1>任务工作台</h1>
        <p class="hero-description">
          把回测、优化和数据同步统一收进一个工作台。先创建任务，再只轮询运行中的对象，完成后转入结果分析。
        </p>
      </div>
      <div class="hero-panel">
        <div>
          <div class="hero-panel__label">当前模式</div>
          <div class="hero-panel__value">{{ taskModeLabel }}</div>
          <div class="hero-panel__meta">{{ submitPath }}</div>
        </div>
        <div class="hero-panel__actions">
          <el-button type="primary" :loading="loading.jobs || loading.create" @click="() => loadJobs()">刷新任务</el-button>
          <el-button v-if="taskMode !== 'refill'" :loading="loading.create" @click="submitJob">{{ submitButtonLabel }}</el-button>
          <el-button v-if="taskMode === 'backtest'" @click="router.push('/qteasy/results')">结果分析</el-button>
        </div>
      </div>
    </section>

    <div class="health-grid">
      <el-card class="health-card">
        <div class="health-card__title">排队中</div>
        <div class="health-card__value">{{ statusCounts.queued }}</div>
        <div class="health-card__meta">queued</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">运行中</div>
        <div class="health-card__value">{{ statusCounts.running }}</div>
        <div class="health-card__meta">running</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">已成功</div>
        <div class="health-card__value">{{ statusCounts.succeeded }}</div>
        <div class="health-card__meta">succeeded</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">失败 / 取消</div>
        <div class="health-card__value">{{ statusCounts.failed }}</div>
        <div class="health-card__meta">failed + cancelled</div>
      </el-card>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="warning" :closable="false" show-icon />

    <el-card class="page-card section">
      <template #header>
        <div class="section-header section-header--space-between">
          <div>
            <div class="section__title">工作流</div>
            <div class="section__desc">新建任务、查看运行中、回看历史任务。任务详情只展示结构化摘要，原始响应收进调试区。</div>
          </div>
          <el-space wrap>
            <el-select v-model="taskMode" style="width: 180px" @change="handleTaskModeChange">
              <el-option label="回测任务" value="backtest" />
              <el-option label="优化任务" value="optimization" />
              <el-option label="数据同步" value="refill" />
            </el-select>
            <el-tag type="info" effect="plain">{{ activeTabLabel }}</el-tag>
          </el-space>
        </div>
      </template>

      <el-tabs v-model="activeTab" class="qteasy-tabs">
        <el-tab-pane label="新建任务" name="create">
          <div class="chart-grid">
            <el-card class="page-card section">
              <template #header>
                <div class="section-header">
                  <div>
                    <div class="section__title">任务参数</div>
                    <div class="section__desc">{{ createDescription }}</div>
                  </div>
                </div>
              </template>

              <template v-if="taskMode === 'refill'">
                <div class="qteasy-form-stack">
                  <div class="qteasy-form-grid qteasy-form-grid--wide">
                    <el-input v-model="refillForm.job_name" placeholder="job_name" clearable />
                    <el-input v-model.number="refillForm.priority" type="number" placeholder="priority" clearable />
                    <el-input v-model="refillForm.channel" placeholder="channel" clearable />
                    <el-input v-model="refillForm.tables" placeholder="tables，逗号分隔" clearable />
                  </div>
                  <div class="qteasy-form-grid qteasy-form-grid--wide">
                    <el-input v-model="refillForm.start_date" placeholder="start_date" clearable />
                    <el-input v-model="refillForm.end_date" placeholder="end_date" clearable />
                  </div>
                  <el-space wrap>
                    <el-button type="primary" :loading="loading.create" @click="submitJob">创建数据同步任务</el-button>
                    <el-button @click="fillExample">填充示例</el-button>
                    <el-button @click="resetForm">清空</el-button>
                  </el-space>
                </div>
              </template>

              <template v-else>
                <div class="qteasy-form-stack">
                  <div class="qteasy-form-grid qteasy-form-grid--wide">
                    <el-input v-model="form.job_name" placeholder="job_name" clearable />
                    <el-input v-model.number="form.priority" type="number" placeholder="priority" clearable />
                    <el-select v-model="form.strategy_kind" placeholder="策略来源">
                      <el-option label="内置策略 built_in" value="built_in" />
                      <el-option label="自定义策略 import" value="import" />
                    </el-select>
                  </div>

                  <div class="qteasy-form-grid qteasy-form-grid--wide">
                    <el-select
                      v-if="form.strategy_kind === 'built_in'"
                      v-model="form.strategy_id"
                      filterable
                      clearable
                      placeholder="选择内置策略"
                    >
                      <el-option
                        v-for="strategy in builtinStrategies"
                        :key="strategy.strategy_id"
                        :label="strategy.strategy_id"
                        :value="strategy.strategy_id"
                      />
                    </el-select>
                    <el-select
                      v-else
                      v-model="selectedCustomStrategyName"
                      filterable
                      clearable
                      placeholder="选择自定义策略"
                      @change="handleCustomStrategySelect"
                    >
                      <el-option
                        v-for="strategy in customStrategies"
                        :key="strategy.name"
                        :label="strategy.name"
                        :value="strategy.name"
                      />
                    </el-select>
                    <el-input
                      v-model="form.strategy_path"
                      :disabled="form.strategy_kind === 'built_in'"
                      placeholder="module:ClassName"
                      clearable
                    />
                    <el-input
                      v-model="form.strategy_kwargs"
                      :disabled="form.strategy_kind === 'built_in'"
                      placeholder="strategy kwargs (JSON)"
                      clearable
                    />
                  </div>

                  <el-alert
                    v-if="form.strategy_kind === 'built_in'"
                    type="info"
                    :closable="false"
                    show-icon
                    title="内置策略使用 strategy_id 提交；策略详情和文档在策略目录里查看。"
                  />
                  <el-alert
                    v-else
                    type="warning"
                    :closable="false"
                    show-icon
                    title="自定义策略以 import 模式提交，可从目录选择，也可以手动填写 module:ClassName。"
                  />

                  <div class="qteasy-form-grid qteasy-form-grid--wide">
                    <el-input v-model="form.run_kwargs" type="textarea" :rows="10" placeholder="run_kwargs JSON" />
                  </div>

                  <el-space wrap>
                    <el-button type="primary" :loading="loading.create" @click="submitJob">{{ submitButtonLabel }}</el-button>
                    <el-button @click="fillExample">填充示例</el-button>
                    <el-button @click="resetForm">清空</el-button>
                  </el-space>
                </div>
              </template>

              <el-alert
                v-if="createResult?.job_id"
                :title="`已创建任务 ${createResult.job_id}`"
                type="success"
                show-icon
                :closable="false"
                class="u-mt-16"
              />
            </el-card>

            <el-card v-if="taskMode === 'backtest'" class="page-card section">
              <template #header>
                <div class="section-header section-header--space-between">
                  <div>
                    <div class="section__title">最近入库结果</div>
                    <div class="section__desc">完成后的回测可同步到本地结果库，方便后续图表分析和对比。</div>
                  </div>
                  <el-button text @click="router.push('/qteasy/results')">查看全部</el-button>
                </div>
              </template>

              <el-table :data="storedResults" v-loading="loading.results" stripe>
                <el-table-column prop="job_name" label="任务名" min-width="180" />
                <el-table-column prop="strategy_id" label="策略 ID" min-width="120" />
                <el-table-column prop="status" label="状态" width="120">
                  <template #default="{ row }">
                    <el-tag :type="jobStatusTag(row.status)">{{ translateJobStatus(row.status) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="parsed_ok" label="解析" width="120">
                  <template #default="{ row }">
                    <el-tag :type="row.parsed_ok ? 'success' : 'warning'">{{ row.parsed_ok ? "已解析" : "部分缺失" }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="updated_at" label="更新时间" width="180">
                  <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
                </el-table-column>
                <el-table-column label="操作" width="120">
                  <template #default="{ row }">
                    <el-button size="small" @click="openStoredResult(row.job_id)">查看图表</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </div>
        </el-tab-pane>

        <el-tab-pane label="运行中" name="running">
          <el-card class="page-card section">
            <template #header>
              <div class="section-header section-header--space-between">
                <div>
                  <div class="section__title">运行中任务</div>
                  <div class="section__desc">只轮询 queued / running 任务，完成后自动停止高频刷新。</div>
                </div>
                <el-space wrap>
                  <el-tag type="warning" effect="plain">{{ activeJobs.length }} 个活动任务</el-tag>
                  <el-button type="primary" :loading="loading.jobs" @click="() => loadJobs()">刷新</el-button>
                </el-space>
              </div>
            </template>

            <el-table :data="activeJobs" v-loading="loading.jobs" stripe>
              <el-table-column prop="job_id" label="Job ID" min-width="220">
                <template #default="{ row }"><span class="summary-box">{{ row.job_id }}</span></template>
              </el-table-column>
              <el-table-column prop="job_name" label="任务名" min-width="180" />
              <el-table-column prop="status" label="状态" width="120">
                <template #default="{ row }">
                  <el-tag :type="jobStatusTag(row.status)">{{ translateJobStatus(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="priority" label="优先级" width="100" />
              <el-table-column prop="progress" label="进度" width="100">
                <template #default="{ row }">{{ row.progress ?? 0 }}%</template>
              </el-table-column>
              <el-table-column prop="current_step" label="当前步骤" min-width="220">
                <template #default="{ row }"><span class="summary-box">{{ row.current_step || "-" }}</span></template>
              </el-table-column>
              <el-table-column prop="created_at" label="创建时间" width="180">
                <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="180" fixed="right">
                <template #default="{ row }">
                  <el-space>
                    <el-button size="small" @click="openJob(row.job_id)">详情</el-button>
                    <el-button size="small" type="warning" :disabled="!canCancel(row.status)" @click="cancelJob(row.job_id)">取消</el-button>
                  </el-space>
                </template>
              </el-table-column>
            </el-table>

            <el-empty v-if="!loading.jobs && !activeJobs.length" description="当前没有运行中的任务" class="u-mt-16" />
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="历史任务" name="history">
          <el-card class="page-card section">
            <template #header>
              <div class="section-header">
                <div>
                  <div class="section__title">历史任务</div>
                  <div class="section__desc">按状态和任务名筛选。已完成任务不再高频轮询，避免详情页卡住。</div>
                </div>
              </div>
            </template>

            <div class="toolbar qteasy-toolbar">
              <el-select v-model="listFilters.status" clearable placeholder="状态" style="width: 160px">
                <el-option v-for="item in statusOptions" :key="item" :label="translateJobStatus(item)" :value="item" />
              </el-select>
              <el-input v-model="listFilters.job_name" clearable placeholder="任务名称" style="width: 200px" />
              <el-button type="primary" :loading="loading.jobs" @click="() => loadJobs()">查询</el-button>
              <el-button @click="resetListFilters">重置</el-button>
            </div>

            <el-table :data="historicalJobs" v-loading="loading.jobs" stripe>
              <el-table-column prop="job_id" label="Job ID" min-width="220">
                <template #default="{ row }"><span class="summary-box">{{ row.job_id }}</span></template>
              </el-table-column>
              <el-table-column prop="job_name" label="名称" min-width="180" />
              <el-table-column prop="status" label="状态" width="120">
                <template #default="{ row }">
                  <el-tag :type="jobStatusTag(row.status)">{{ translateJobStatus(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="progress" label="进度" width="100">
                <template #default="{ row }">{{ row.progress ?? 0 }}%</template>
              </el-table-column>
              <el-table-column prop="current_step" label="最后步骤" min-width="220">
                <template #default="{ row }"><span class="summary-box">{{ row.current_step || "-" }}</span></template>
              </el-table-column>
              <el-table-column v-if="taskMode === 'backtest'" label="结果状态" width="140">
                <template #default="{ row }">
                  <el-tag :type="jobResultTag(row.job_id)">{{ jobResultLabel(row.job_id) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="finished_at" label="完成时间" width="180">
                <template #default="{ row }">{{ formatDateTime(row.finished_at || row.updated_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="240" fixed="right">
                <template #default="{ row }">
                  <el-space>
                    <el-button size="small" @click="openJob(row.job_id)">详情</el-button>
                    <el-button
                      v-if="taskMode === 'backtest' && isFinished(row.status)"
                      size="small"
                      type="success"
                      @click="syncStoredResult(row.job_id)"
                    >
                      同步结果
                    </el-button>
                  </el-space>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-drawer v-model="detailVisible" size="72%" :title="detailTitle">
      <template v-if="currentJob">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="job_id">{{ currentJob.job_id }}</el-descriptions-item>
          <el-descriptions-item label="任务名">{{ currentJob.job_name || "-" }}</el-descriptions-item>
          <el-descriptions-item label="task_type">{{ currentJob.task_type }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="jobStatusTag(currentJob.status)">{{ translateJobStatus(currentJob.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="进度">{{ currentJob.progress ?? 0 }}%</el-descriptions-item>
          <el-descriptions-item label="当前步骤">{{ currentJob.current_step || "-" }}</el-descriptions-item>
          <el-descriptions-item label="错误信息">
            <span class="summary-box">{{ currentJob.error || "-" }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(currentJob.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatDateTime(currentJob.started_at) }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ formatDateTime(currentJob.finished_at) }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="taskMode === 'backtest' && storedDetail" class="u-mt-16">
          <qteasy-backtest-charts :series="chartSeries" />
        </div>

        <el-empty
          v-else-if="taskMode === 'backtest' && isFinished(currentJob.status)"
          class="u-mt-16"
          description="本地还没有同步结果，可在历史任务里点击“同步结果”，再进入结果分析。"
        />

        <el-collapse v-model="detailPanels" class="qteasy-debug-collapse u-mt-16">
          <el-collapse-item title="原始 payload" name="payload">
            <pre class="summary-box qteasy-result-pre">{{ prettyJson(currentJob.payload) }}</pre>
          </el-collapse-item>
          <el-collapse-item title="原始 result" name="result">
            <pre class="summary-box qteasy-result-pre">{{ prettyJson(currentJob.result) }}</pre>
          </el-collapse-item>
        </el-collapse>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import QteasyBacktestCharts from "../components/qteasy/QteasyBacktestCharts.vue";
import { qteasyApi, qteasyExtractItems, qteasyUnwrap } from "../services/qteasy";
import type {
  QteasyChartSeries,
  QteasyCustomStrategyItem,
  QteasyJobItem,
  QteasyStoredResultDetail,
  QteasyStoredResultItem,
  QteasyStrategyItem,
} from "../types";
import { formatDateTime, prettyJson } from "../utils";

type TaskMode = "backtest" | "optimization" | "refill";
type WorkbenchTab = "create" | "running" | "history";

const route = useRoute();
const router = useRouter();

const activeTab = ref<WorkbenchTab>("create");
const taskMode = ref<TaskMode>("backtest");
const loading = reactive({
  create: false,
  jobs: false,
  jobDetail: false,
  results: false,
  sync: false,
});
const errorMessage = ref("");
const jobs = ref<QteasyJobItem[]>([]);
const storedResults = ref<QteasyStoredResultItem[]>([]);
const builtinStrategies = ref<QteasyStrategyItem[]>([]);
const customStrategies = ref<QteasyCustomStrategyItem[]>([]);
const currentJob = ref<QteasyJobItem | null>(null);
const storedDetail = ref<QteasyStoredResultDetail | null>(null);
const detailVisible = ref(false);
const detailPanels = ref<string[]>([]);
const createResult = ref<{ job_id?: string; [key: string]: unknown }>({});
const refreshTimer = ref<number | null>(null);
const resultStatusMap = ref<Record<string, { exists: boolean; parsed_ok: boolean }>>({});

const statusOptions = ["queued", "running", "succeeded", "failed", "cancelled"];
const listFilters = reactive<{ status: string; job_name: string }>({
  status: "",
  job_name: "",
});
const form = reactive({
  job_name: "",
  priority: 50,
  strategy_kind: "built_in",
  strategy_id: "",
  strategy_path: "",
  strategy_kwargs: "",
  run_kwargs: '{\n  "asset_type": "E",\n  "visual": false\n}',
});
const refillForm = reactive({
  job_name: "",
  priority: 50,
  channel: "",
  tables: "",
  start_date: "",
  end_date: "",
});
const selectedCustomStrategyName = ref("");

const taskModeLabel = computed(() => {
  const labels: Record<TaskMode, string> = {
    backtest: "回测任务",
    optimization: "优化任务",
    refill: "数据同步",
  };
  return labels[taskMode.value];
});

const activeTabLabel = computed(() => {
  const labels: Record<WorkbenchTab, string> = {
    create: "新建任务",
    running: "运行中",
    history: "历史任务",
  };
  return labels[activeTab.value];
});

const submitPath = computed(() => {
  if (taskMode.value === "optimization") return "/optimizations";
  if (taskMode.value === "refill") return "/data/refill";
  return "/backtests";
});

const submitButtonLabel = computed(() => {
  if (taskMode.value === "optimization") return "创建优化任务";
  if (taskMode.value === "refill") return "创建数据同步任务";
  return "创建回测任务";
});

const createDescription = computed(() => {
  if (taskMode.value === "optimization") {
    return "优化任务和回测任务共用同一套策略选择器，参数仍通过 run_kwargs 传入。";
  }
  if (taskMode.value === "refill") {
    return "数据同步按表名、渠道和日期范围提交，适合作为行情或基础数据灌库入口。";
  }
  return "先选策略来源，再选择具体策略。自定义策略保留手动 module:ClassName 作为高级兜底。";
});

const statusCounts = computed(() => {
  const counter = { queued: 0, running: 0, succeeded: 0, failed: 0 };
  for (const item of jobs.value) {
    if (item.status === "cancelled") {
      counter.failed += 1;
    } else if (item.status in counter) {
      counter[item.status as keyof typeof counter] += 1;
    }
  }
  return counter;
});

const activeJobs = computed(() => jobs.value.filter((item) => item.status === "queued" || item.status === "running"));
const historicalJobs = computed(() => jobs.value.filter((item) => item.status !== "queued" && item.status !== "running"));

const detailTitle = computed(() =>
  currentJob.value ? `任务详情 - ${currentJob.value.job_name || currentJob.value.job_id}` : "任务详情",
);

const chartSeries = computed<QteasyChartSeries>(() => ({
  job_id: storedDetail.value?.job_id || "",
  metrics: storedDetail.value?.metrics || {},
  equity_curve: storedDetail.value?.equity_curve || [],
  benchmark_curve: storedDetail.value?.benchmark_curve || [],
  drawdown_curve: storedDetail.value?.drawdown_curve || [],
  return_histogram: storedDetail.value?.return_histogram || [],
  parsed_ok: storedDetail.value?.parsed_ok,
  parse_message: storedDetail.value?.parse_message,
}));

function normalizeTaskMode(value: unknown): TaskMode {
  if (value === "optimization") return "optimization";
  if (value === "refill") return "refill";
  return "backtest";
}

function normalizeCustomStrategy(payload: unknown, fallbackName = ""): QteasyCustomStrategyItem {
  const source = payload && typeof payload === "object" && !Array.isArray(payload) ? (payload as Record<string, unknown>) : {};
  return {
    name: String(source.name || fallbackName || ""),
    import_path: typeof source.import_path === "string" ? source.import_path : typeof source.path === "string" ? source.path : null,
    class_name: typeof source.class_name === "string" ? source.class_name : null,
    module: typeof source.module === "string" ? source.module : null,
    summary: typeof source.summary === "string" ? source.summary : typeof source.doc === "string" ? source.doc : null,
    doc: typeof source.doc === "string" ? source.doc : null,
    repr: typeof source.repr === "string" ? source.repr : null,
    ...source,
  };
}

function jobStatusTag(value?: string | null): "info" | "success" | "warning" | "danger" {
  if (value === "succeeded") return "success";
  if (value === "running" || value === "queued") return "warning";
  if (value === "failed" || value === "cancelled") return "danger";
  return "info";
}

function canCancel(status?: string | null): boolean {
  return status === "queued" || status === "running";
}

function isFinished(status?: string | null): boolean {
  return status === "succeeded" || status === "failed" || status === "cancelled";
}

function translateJobStatus(value?: string | null): string {
  if (!value) return "-";
  const mapping: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    succeeded: "成功",
    failed: "失败",
    cancelled: "已取消",
  };
  return mapping[value] || value;
}

function jobResultLabel(jobId: string): string {
  const item = resultStatusMap.value[jobId];
  if (!item) return "未入库";
  return item.parsed_ok ? "已解析" : "已入库";
}

function jobResultTag(jobId: string): "info" | "success" | "warning" {
  const item = resultStatusMap.value[jobId];
  if (!item) return "info";
  return item.parsed_ok ? "success" : "warning";
}

function parseJsonInput(text: string, fallback: Record<string, unknown> = {}): Record<string, unknown> {
  const raw = text.trim();
  if (!raw) return fallback;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // ignore
  }
  return fallback;
}

function buildJobFilters(): Record<string, string | number | boolean | null | undefined> {
  const taskType =
    taskMode.value === "optimization"
      ? "optimization.run"
      : taskMode.value === "refill"
        ? "data.refill"
        : "qteasy.run";
  return {
    limit: 20,
    offset: 0,
    task_type: taskType,
    status: listFilters.status || undefined,
  };
}

function filterJobsByName(items: QteasyJobItem[]): QteasyJobItem[] {
  const keyword = listFilters.job_name.trim().toLowerCase();
  if (!keyword) {
    return items;
  }
  return items.filter((item) => String(item.job_name || "").toLowerCase().includes(keyword));
}

function buildStrategiesPayload(): Record<string, unknown> {
  if (form.strategy_kind === "import") {
    return {
      kind: "import",
      path: form.strategy_path.trim(),
      kwargs: parseJsonInput(form.strategy_kwargs, {}),
    };
  }
  return {
    kind: "built_in",
    strategy_id: form.strategy_id.trim(),
  };
}

function buildSubmitPayload(): Record<string, unknown> {
  if (taskMode.value === "refill") {
    return {
      job_name: refillForm.job_name.trim() || undefined,
      priority: Number.isFinite(Number(refillForm.priority)) ? Number(refillForm.priority) : undefined,
      channel: refillForm.channel.trim() || undefined,
      tables: refillForm.tables
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      start_date: refillForm.start_date.trim() || undefined,
      end_date: refillForm.end_date.trim() || undefined,
    };
  }
  return {
    job_name: form.job_name.trim() || undefined,
    priority: Number.isFinite(Number(form.priority)) ? Number(form.priority) : undefined,
    mode: taskMode.value === "optimization" ? 2 : 1,
    strategies: buildStrategiesPayload(),
    run_kwargs: parseJsonInput(form.run_kwargs, {}),
  };
}

function resetForm(): void {
  form.job_name = "";
  form.priority = 50;
  form.strategy_kind = "built_in";
  form.strategy_id = "";
  form.strategy_path = "";
  form.strategy_kwargs = "";
  form.run_kwargs = '{\n  "asset_type": "E",\n  "visual": false\n}';
  refillForm.job_name = "";
  refillForm.priority = 50;
  refillForm.channel = "";
  refillForm.tables = "";
  refillForm.start_date = "";
  refillForm.end_date = "";
  selectedCustomStrategyName.value = "";
}

function fillExample(): void {
  if (taskMode.value === "optimization") {
    form.job_name = "策略优化示例";
    form.strategy_kind = "import";
    form.strategy_path = "qteasy.kdj_threshold:JThresholdStg";
    form.strategy_kwargs = '{\n  "buy_level": -10,\n  "sell_level": 50\n}';
    form.run_kwargs =
      '{\n  "asset_type": "E",\n  "asset_pool": ["000001.SZ"],\n  "invest_start": "20200101",\n  "invest_end": "20241231",\n  "trade_log": true,\n  "visual": false\n}';
    return;
  }
  if (taskMode.value === "refill") {
    refillForm.job_name = "日更同步";
    refillForm.priority = 50;
    refillForm.channel = "baostock";
    refillForm.tables = "trade_calendar,stock_daily";
    refillForm.start_date = "20240101";
    refillForm.end_date = "20240430";
    return;
  }
  form.job_name = "J 阈值回测";
  form.strategy_kind = "import";
  form.strategy_path = "qteasy.kdj_threshold:JThresholdStg";
  form.strategy_kwargs = '{\n  "buy_level": -10,\n  "sell_level": 50\n}';
  form.run_kwargs =
    '{\n  "asset_type": "E",\n  "asset_pool": ["000001.SZ"],\n  "invest_start": "20200101",\n  "invest_end": "20241231",\n  "trade_log": true,\n  "visual": false\n}';
}

function handleTaskModeChange(): void {
  void router.replace({ path: "/qteasy/tasks", query: { ...route.query, kind: taskMode.value } });
  activeTab.value = "create";
  resetListFilters();
  void loadJobs();
  if (taskMode.value === "backtest") {
    void loadStoredResults();
  }
}

function handleCustomStrategySelect(name: string | null | undefined): void {
  const strategy = customStrategies.value.find((item) => item.name === name);
  selectedCustomStrategyName.value = strategy?.name || "";
  form.strategy_path = strategy?.import_path || "";
  if (!strategy) {
    form.strategy_kwargs = "";
  }
}

function applyRouteStrategyPrefill(): void {
  const source = String(route.query.strategy_source || "").trim();
  if (source === "custom") {
    form.strategy_kind = "import";
    const name = String(route.query.strategy_name || "").trim();
    const path = String(route.query.strategy_path || "").trim();
    selectedCustomStrategyName.value = name;
    form.strategy_path = path;
    if (!path && name) {
      handleCustomStrategySelect(name);
    }
    return;
  }
  if (source === "built_in") {
    form.strategy_kind = "built_in";
    form.strategy_id = String(route.query.strategy_id || "").trim();
    form.strategy_path = "";
    form.strategy_kwargs = "";
    selectedCustomStrategyName.value = "";
  }
}

async function loadBuiltinStrategies(): Promise<void> {
  try {
    const payload = await qteasyApi.get<unknown>("/strategies/builtins");
    builtinStrategies.value = qteasyUnwrap<QteasyStrategyItem[]>(payload, []);
    if (form.strategy_kind === "built_in" && !form.strategy_id) {
      form.strategy_id = builtinStrategies.value[0]?.strategy_id || "";
    }
  } catch {
    builtinStrategies.value = [];
  }
}

async function loadCustomStrategies(): Promise<void> {
  try {
    const payload = await qteasyApi.get<unknown>("/strategies/custom");
    const items = qteasyUnwrap<unknown[]>(payload, []);
    customStrategies.value = Array.isArray(items)
      ? items.map((item) => normalizeCustomStrategy(item)).filter((item) => item.name)
      : [];
    if (selectedCustomStrategyName.value && !form.strategy_path) {
      handleCustomStrategySelect(selectedCustomStrategyName.value);
    }
  } catch {
    customStrategies.value = [];
  }
}

async function loadJobs(options: { refreshResultStatus?: boolean } = {}): Promise<void> {
  loading.jobs = true;
  errorMessage.value = "";
  try {
    const payload = await qteasyApi.get<unknown>("/jobs", buildJobFilters());
    jobs.value = filterJobsByName(qteasyExtractItems<QteasyJobItem>(payload));
    if (taskMode.value === "backtest" && options.refreshResultStatus !== false) {
      await loadResultStatusForJobs(historicalJobs.value.map((item) => item.job_id).filter(Boolean));
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.jobs = false;
  }
}

async function loadResultStatusForJobs(jobIds: string[]): Promise<void> {
  if (!jobIds.length) {
    resultStatusMap.value = {};
    return;
  }
  try {
    const payload = await qteasyApi.get<{ items?: QteasyStoredResultItem[] }>("/results", {
      page: 1,
      page_size: 100,
      job_ids: jobIds.join(","),
    });
    const nextMap: Record<string, { exists: boolean; parsed_ok: boolean }> = {};
    for (const item of payload.items || []) {
      nextMap[item.job_id] = { exists: true, parsed_ok: Boolean(item.parsed_ok) };
    }
    resultStatusMap.value = nextMap;
  } catch {
    resultStatusMap.value = {};
  }
}

async function loadStoredResults(): Promise<void> {
  if (taskMode.value !== "backtest") return;
  loading.results = true;
  try {
    const payload = await qteasyApi.get<{ items?: QteasyStoredResultItem[] }>("/results", {
      page: 1,
      page_size: 8,
    });
    storedResults.value = payload.items || [];
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.results = false;
  }
}

async function createJob(payload: Record<string, unknown>): Promise<string | null> {
  const response = await qteasyApi.post<unknown>(submitPath.value, payload);
  const result = qteasyUnwrap<Record<string, unknown> | null>(response, {});
  createResult.value = result && typeof result === "object" && !Array.isArray(result) ? result : {};
  const normalized = createResult.value as Record<string, unknown>;
  const jobId = normalized.job_id ?? normalized.id;
  return typeof jobId === "string" && jobId.trim() ? jobId.trim() : jobId != null ? String(jobId) : null;
}

async function submitJob(): Promise<void> {
  loading.create = true;
  errorMessage.value = "";
  try {
    const payload = buildSubmitPayload();
    await createJob(payload);
    activeTab.value = "running";
    await loadJobs();
    if (taskMode.value === "backtest") {
      await loadStoredResults();
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.create = false;
  }
}

async function loadJobSnapshot(jobId: string): Promise<QteasyJobItem> {
  return qteasyUnwrap<QteasyJobItem>(await qteasyApi.get<unknown>(`/jobs/${encodeURIComponent(jobId)}`), {
    job_id: jobId,
    task_type: taskMode.value === "optimization" ? "optimization.run" : taskMode.value === "refill" ? "data.refill" : "qteasy.run",
    status: "unknown",
  });
}

async function openJob(jobId: string): Promise<void> {
  detailVisible.value = true;
  await loadJobDetail(jobId);
}

async function loadJobDetail(jobId: string): Promise<void> {
  loading.jobDetail = true;
  errorMessage.value = "";
  try {
    currentJob.value = await loadJobSnapshot(jobId);
    if (taskMode.value === "backtest" && isFinished(currentJob.value.status)) {
      try {
        storedDetail.value = await qteasyApi.get<QteasyStoredResultDetail>(`/results/${encodeURIComponent(jobId)}`);
      } catch {
        storedDetail.value = null;
      }
    } else {
      storedDetail.value = null;
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.jobDetail = false;
  }
}

async function syncStoredResult(jobId: string): Promise<void> {
  loading.sync = true;
  errorMessage.value = "";
  try {
    await qteasyApi.post(`/results/${encodeURIComponent(jobId)}/sync`, {});
    await loadStoredResults();
    await loadResultStatusForJobs(historicalJobs.value.map((item) => item.job_id).filter(Boolean));
    if (detailVisible.value && currentJob.value?.job_id === jobId) {
      await loadJobDetail(jobId);
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.sync = false;
  }
}

async function openStoredResult(jobId: string): Promise<void> {
  await router.push({ path: "/qteasy/results", query: { job_id: jobId } });
}

async function cancelJob(jobId: string): Promise<void> {
  try {
    await qteasyApi.post(`/jobs/${encodeURIComponent(jobId)}/cancel`, {});
    await loadJobs();
    if (currentJob.value?.job_id === jobId) {
      await loadJobDetail(jobId);
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  }
}

function resetListFilters(): void {
  listFilters.status = "";
  listFilters.job_name = "";
}

function schedulePolling(): void {
  if (refreshTimer.value) {
    window.clearInterval(refreshTimer.value);
  }
  refreshTimer.value = window.setInterval(() => {
    if (!activeJobs.value.length && !(detailVisible.value && currentJob.value && canCancel(currentJob.value.status))) {
      return;
    }
    void loadJobs({ refreshResultStatus: false });
    if (detailVisible.value && currentJob.value?.job_id && canCancel(currentJob.value.status)) {
      void loadJobDetail(currentJob.value.job_id);
    }
  }, 5000);
}

watch(
  () => route.query.kind,
  () => {
    taskMode.value = normalizeTaskMode(route.query.kind);
  },
  { immediate: true },
);

watch(
  () => route.query,
  () => {
    applyRouteStrategyPrefill();
  },
);

watch(
  () => detailVisible.value,
  (visible) => {
    if (!visible || !currentJob.value?.job_id) return;
    void loadJobDetail(currentJob.value.job_id);
  },
);

watch(
  () => form.strategy_kind,
  (kind) => {
    if (kind === "built_in") {
      form.strategy_path = "";
      form.strategy_kwargs = "";
      selectedCustomStrategyName.value = "";
      if (!form.strategy_id && builtinStrategies.value.length) {
        form.strategy_id = builtinStrategies.value[0]?.strategy_id || "";
      }
      return;
    }
    form.strategy_id = "";
  },
);

watch(
  () => taskMode.value,
  () => {
    resetForm();
  },
);

onMounted(() => {
  void loadBuiltinStrategies();
  void loadCustomStrategies();
  applyRouteStrategyPrefill();
  void loadJobs();
  void loadStoredResults();
  schedulePolling();
});

onUnmounted(() => {
  if (refreshTimer.value) {
    window.clearInterval(refreshTimer.value);
  }
});
</script>
