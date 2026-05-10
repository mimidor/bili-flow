<template>
  <div class="task-center">
    <section class="task-hero">
      <div class="task-hero__copy">
        <div class="task-hero__eyebrow">任务中心 / 队列监控</div>
        <h1>统一查看处理中、失败和卡住任务</h1>
        <p class="task-hero__desc">
          这里把视频、动态和小宇宙单集的任务状态放在同一个页面里，支持手动重跑、批量重跑、重置卡住任务，以及暂停或恢复调度与队列。        </p>
      </div>

      <div class="task-hero__actions">
        <el-button type="primary" :loading="overviewLoading || tableLoading" @click="refreshAll">刷新</el-button>
        <el-button type="warning" @click="resetStuckTasks">重置卡住任务</el-button>
      </div>
    </section>

    <div v-if="isMobile" class="mobile-action-bar mobile-action-bar--task">
      <el-button type="primary" :loading="overviewLoading || tableLoading" @click="refreshAll">刷新列表</el-button>
      <el-button @click="mobileFiltersVisible = true">筛选</el-button>
      <el-button @click="resetFilters">重置</el-button>
      <el-button :disabled="!selectedRows.length" type="danger" @click="retrySelected">批量重试</el-button>
    </div>

    <div class="page-grid page-grid--five">
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">待处理</div>
        <div class="stat-value">{{ taskOverview.total_pending }}</div>
      </el-card>
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">处理中</div>
        <div class="stat-value">{{ taskOverview.total_processing }}</div>
      </el-card>
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">失败任务</div>
        <div class="stat-value">{{ taskOverview.total_failed }}</div>
      </el-card>
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">调度器</div>
        <div class="stat-value">{{ runtimeStatusText(schedulerState) }}</div>
      </el-card>
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">队列线程</div>
        <div class="stat-value">{{ runtimeStatusText(queueState) }}</div>
      </el-card>
    </div>

    <div class="runtime-grid">
      <el-card v-for="state in runtimeStates" :key="state.component" class="page-card runtime-card">
        <template #header>
          <div class="section-header">
            <div>
              <div class="section__title">{{ state.label }}</div>
              <div class="section__desc">最近心跳、最近运行时间和暂停控制</div>
            </div>
            <el-tag :type="runtimeTagType(state.status)">{{ runtimeStatusText(state) }}</el-tag>
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

        <div class="runtime-card__actions">
          <el-button v-if="!state.is_paused" type="warning" @click="toggleRuntime(state, true)">鏆傚仠</el-button>
          <el-button v-else type="primary" @click="toggleRuntime(state, false)">鎭㈠</el-button>
        </div>
      </el-card>
    </div>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">任务列表</div>
            <div class="section__desc">默认只显示待处理、处理中和失败任务；可按内容类型、状态、关键词和时间筛选</div>
          </div>
          <div class="task-toolbar__summary">
            <span class="muted">已选 {{ selectedRows.length }} 条</span>
            <el-button :disabled="!selectedRows.length" type="danger" @click="retrySelected">批量重试</el-button>
          </div>
        </div>
      </template>

      <template v-if="isMobile">
        <div class="mobile-action-strip">
          <el-button size="small" type="primary" :loading="tableLoading" @click="loadTasks">刷新列表</el-button>
          <el-button size="small" @click="mobileFiltersVisible = true">筛选条件</el-button>
          <el-button size="small" @click="resetFilters">重置筛选</el-button>
        </div>

        <div v-if="taskRows.length" class="mobile-record-list">
          <el-card v-for="row in taskRows" :key="rowKey(row)" class="mobile-record-card task-mobile-card" shadow="never">
            <template #header>
              <div class="mobile-record-card__header">
                <el-checkbox
                  :model-value="isTaskSelected(row)"
                  :disabled="tableLoading"
                  @change="toggleTaskSelection(row, $event)"
                />
                <div class="mobile-record-card__headline">
                  <div class="mobile-record-card__badges">
                    <el-tag size="small" :type="row.content_type === 'video' ? 'success' : 'warning'">
                      {{ translateContentType(row.content_type) }}
                    </el-tag>
                    <el-tag size="small" :type="statusTagType(row.status)" effect="plain">
                      {{ statusText(row.status) }}
                    </el-tag>
                    <el-tag v-if="row.push_status" size="small" :type="statusTagType(row.push_status)" effect="plain">
                      {{ statusText(row.push_status) }}
                    </el-tag>
                  </div>
                  <div class="mobile-record-card__title">
                    <el-link v-if="row.source_url" :href="row.source_url" target="_blank" type="primary" :underline="false">
                      {{ row.title }}
                    </el-link>
                    <span v-else>{{ row.title }}</span>
                  </div>
                  <div class="mobile-record-card__subtitle">{{ row.content_id }}</div>
                </div>
              </div>
            </template>

            <div class="mobile-record-card__meta-grid">
              <div>
                <span class="mobile-record-card__meta-label">作者</span>
                <strong>{{ row.uploader_name || "-" }}</strong>
              </div>
              <div>
                <span class="mobile-record-card__meta-label">重试</span>
                <strong>{{ row.attempt_count }}</strong>
              </div>
              <div>
                <span class="mobile-record-card__meta-label">发布时间</span>
                <strong>{{ formatDateTime(row.pub_time) }}</strong>
              </div>
              <div>
                <span class="mobile-record-card__meta-label">最近更新</span>
                <strong>{{ formatDateTime(row.updated_at) }}</strong>
              </div>
            </div>

            <div v-if="row.summary_excerpt" class="summary-box mobile-record-card__summary">{{ row.summary_excerpt }}</div>
            <div v-if="row.last_error" class="summary-box mobile-record-card__summary mobile-record-card__summary--error">
              {{ row.last_error }}
            </div>

            <div class="mobile-record-card__actions">
              <el-button size="small" @click="openDetail(row)">详情</el-button>
              <el-button size="small" type="warning" @click="retrySingle(row)">重试</el-button>
            </div>
          </el-card>
        </div>
        <el-empty v-else :description="tableLoading ? '正在加载任务列表' : '暂无任务'" />
      </template>

      <template v-else>
        <div class="task-toolbar">
          <el-input v-model="filters.q" clearable placeholder="按标题 / ID / 错误信息搜索" style="width: 260px" />
          <el-input v-model="filters.uploader_name" clearable placeholder="按作者搜索" style="width: 180px" />
          <el-select v-model="filters.content_type" clearable placeholder="内容类型" style="width: 140px">
            <el-option v-for="item in contentTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select v-model="filters.status" clearable placeholder="任务状态" style="width: 160px">
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-date-picker
            v-model="filters.pub_range"
            type="daterange"
            unlink-panels
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 340px"
          />
          <el-button type="primary" :loading="tableLoading" @click="loadTasks">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>

        <el-table
          :data="taskRows"
          v-loading="tableLoading"
          stripe
          :row-key="rowKey"
          @selection-change="onSelectionChange"
        >
          <el-table-column type="selection" width="50" />
          <el-table-column prop="content_type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag :type="row.content_type === 'video' ? 'success' : 'warning'">
                {{ translateContentType(row.content_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="标题 / 内容" min-width="300">
            <template #default="{ row }">
              <div class="task-title-cell">
                <el-link v-if="row.source_url" :href="row.source_url" target="_blank" type="primary" :underline="false">
                  {{ row.title }}
                </el-link>
                <span v-else>{{ row.title }}</span>
                <div class="muted">{{ row.content_id }}</div>
                <div v-if="row.summary_excerpt" class="summary-box task-summary">{{ row.summary_excerpt }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column class-name="mobile-hide-sm" prop="uploader_name" label="作者" width="160">
            <template #default="{ row }">{{ row.uploader_name || "-" }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="push_status" label="推送" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.push_status" :type="statusTagType(row.push_status)">{{ statusText(row.push_status) }}</el-tag>
              <span v-else class="muted">-</span>
            </template>
          </el-table-column>
          <el-table-column class-name="mobile-hide-sm" prop="attempt_count" label="重试" width="90" />
          <el-table-column class-name="mobile-hide-md" prop="pub_time" label="发布时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.pub_time) }}</template>
          </el-table-column>
          <el-table-column class-name="mobile-hide-md" prop="updated_at" label="最近更新" width="180">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column class-name="mobile-hide-sm" prop="last_error" label="错误信息" min-width="240">
            <template #default="{ row }">
              <span class="summary-box">{{ row.last_error || "-" }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-space>
                <el-button size="small" @click="openDetail(row)">详情</el-button>
                <el-button size="small" type="warning" @click="retrySingle(row)">重试</el-button>
              </el-space>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <div class="toolbar" style="justify-content: flex-end; margin-top: 16px">
        <el-pagination
          layout="prev, pager, next, total, sizes"
          :current-page="filters.page"
          :page-size="filters.page_size"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          @current-change="changePage"
          @size-change="changePageSize"
        />
      </div>
    </el-card>

    <el-drawer v-model="mobileFiltersVisible" title="任务筛选" size="85%">
      <el-form label-position="top" class="mobile-filter-form">
        <el-form-item label="关键词">
          <el-input v-model="filters.q" clearable placeholder="按标题 / ID / 错误信息搜索" />
        </el-form-item>
        <el-form-item label="作者">
          <el-input v-model="filters.uploader_name" clearable placeholder="按作者搜索" />
        </el-form-item>
        <el-form-item label="内容类型">
          <el-select v-model="filters.content_type" clearable placeholder="内容类型" style="width: 100%">
            <el-option v-for="item in contentTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务状态">
          <el-select v-model="filters.status" clearable placeholder="任务状态" style="width: 100%">
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.pub_range"
            type="datetimerange"
            unlink-panels
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <div class="mobile-filter-form__actions">
          <el-button type="primary" :loading="tableLoading" @click="loadTasks">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>
      </el-form>
    </el-drawer>

    <div v-if="isMobile && detailVisible && activeRow" class="mobile-detail-page task-detail-page">
      <div class="mobile-detail-page__top">
        <el-button text class="mobile-detail-page__back" @click="closeDetail">返回列表</el-button>
        <div>
          <div class="mobile-detail-page__eyebrow">任务详情</div>
          <div class="mobile-detail-page__title">{{ activeRow.title }}</div>
          <div class="mobile-detail-page__subtitle">
            {{ translateContentType(activeRow.content_type) }} · {{ statusText(activeRow.status) }}
          </div>
        </div>
        <div class="mobile-detail-page__actions">
          <el-button size="small" type="warning" @click="retrySingle(activeRow)">重试</el-button>
          <el-button size="small" @click="closeDetail">关闭</el-button>
        </div>
      </div>

      <div class="mobile-detail-card-grid">
        <el-card shadow="never" class="mobile-detail-card">
          <template #header>基本信息</template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="类型">{{ translateContentType(activeRow.content_type) }}</el-descriptions-item>
            <el-descriptions-item label="内容ID">{{ activeRow.content_id }}</el-descriptions-item>
            <el-descriptions-item label="作者">{{ activeRow.uploader_name || "-" }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ statusText(activeRow.status) }}</el-descriptions-item>
            <el-descriptions-item label="推送状态">
              {{ activeRow.push_status ? statusText(activeRow.push_status) : "-" }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card shadow="never" class="mobile-detail-card">
          <template #header>时间信息</template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="发布时间">{{ formatDateTime(activeRow.pub_time) }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDateTime(activeRow.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ formatDateTime(activeRow.updated_at) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card shadow="never" class="mobile-detail-card">
          <template #header>链接</template>
          <div class="mobile-detail-link-list">
            <div class="mobile-detail-link-item">
              <div class="mobile-detail-link-item__label">来源链接</div>
              <el-link v-if="activeRow.source_url" :href="activeRow.source_url" target="_blank" type="primary">
                打开来源
              </el-link>
              <span v-else>-</span>
            </div>
            <div class="mobile-detail-link-item">
              <div class="mobile-detail-link-item__label">文档链接</div>
              <el-link v-if="activeRow.doc_url" :href="activeRow.doc_url" target="_blank" type="primary">
                打开文档
              </el-link>
              <span v-else>-</span>
            </div>
          </div>
        </el-card>

        <el-card shadow="never" class="mobile-detail-card">
          <template #header>摘要</template>
          <pre class="summary-box mobile-detail-pre">{{ activeRow.summary_excerpt || "-" }}</pre>
        </el-card>

        <el-card shadow="never" class="mobile-detail-card">
          <template #header>错误信息</template>
          <pre class="summary-box mobile-detail-pre">{{ activeRow.last_error || "-" }}</pre>
        </el-card>
      </div>
    </div>

    <el-drawer v-else v-model="detailVisible" title="任务详情" size="50%">
      <template v-if="activeRow">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="类型">{{ translateContentType(activeRow.content_type) }}</el-descriptions-item>
          <el-descriptions-item label="标题">{{ activeRow.title }}</el-descriptions-item>
          <el-descriptions-item label="内容ID">{{ activeRow.content_id }}</el-descriptions-item>
          <el-descriptions-item label="作者">{{ activeRow.uploader_name || "-" }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusText(activeRow.status) }}</el-descriptions-item>
          <el-descriptions-item label="推送状态">
            {{ activeRow.push_status ? statusText(activeRow.push_status) : "-" }}
          </el-descriptions-item>
          <el-descriptions-item label="发布时间">{{ formatDateTime(activeRow.pub_time) }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(activeRow.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDateTime(activeRow.updated_at) }}</el-descriptions-item>
          <el-descriptions-item label="来源链接">
            <el-link v-if="activeRow.source_url" :href="activeRow.source_url" target="_blank" type="primary">
              {{ activeRow.source_url }}
            </el-link>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="文档链接">
            <el-link v-if="activeRow.doc_url" :href="activeRow.doc_url" target="_blank" type="primary">
              {{ activeRow.doc_url }}
            </el-link>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="摘要">
            <pre class="summary-box">{{ activeRow.summary_excerpt || "-" }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="错误信息">
            <pre class="summary-box">{{ activeRow.last_error || "-" }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { api } from "../api";
import { useBreakpoint } from "../composables/useBreakpoint";
import type {
  PageResult,
  TaskItem,
  TaskOverview,
  TaskRetryRequest,
  TaskRuntimeItem,
  TaskRuntimeUpdateResponse,
} from "../types";
import { buildQuery, formatDateTime, translateContentType } from "../utils";

const overviewLoading = ref(false);
const tableLoading = ref(false);
const taskOverview = ref<TaskOverview>({
  video_pending: 0,
  video_processing: 0,
  video_failed: 0,
  dynamic_pending: 0,
  dynamic_processing: 0,
  dynamic_failed: 0,
  podcast_pending: 0,
  podcast_processing: 0,
  podcast_failed: 0,
  total_pending: 0,
  total_processing: 0,
  total_failed: 0,
  runtime_states: [],
});
const taskRows = ref<TaskItem[]>([]);
const total = ref(0);
const selectedRows = ref<TaskItem[]>([]);
const detailVisible = ref(false);
const activeRow = ref<TaskItem | null>(null);
const mobileFiltersVisible = ref(false);
const { isMobile } = useBreakpoint();

const filters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  uploader_name: "",
  content_type: "",
  status: "",
  pub_range: [] as string[] | [],
});

const contentTypeOptions = [
  { label: "视频", value: "video" },
  { label: "动态", value: "dynamic" },
  { label: "小宇宙", value: "podcast" },
];

const statusOptions = [
  { label: "待处理", value: "pending" },
  { label: "处理中", value: "processing" },
  { label: "失败", value: "failed" },
];

const runtimeStates = computed(() => taskOverview.value.runtime_states || []);
const schedulerState = computed(() => runtimeStates.value.find((item) => item.component === "scheduler") || null);
const queueState = computed(() => runtimeStates.value.find((item) => item.component === "queue_worker") || null);

function rowKey(row: TaskItem): string {
  return `${row.content_type}-${row.id}`;
}

function statusText(value?: string | null): string {
  if (!value) return "-";
  const labels: Record<string, string> = {
    pending: "待处理",
    processing: "处理中",
    failed: "失败",
    failed_download: "下载失败",
    failed_asr: "识别失败",
    failed_summary: "总结失败",
    sent: "已发送",
    done: "已完成",
    filtered: "已过滤",
    running: "运行中",
    paused: "已暂停",
    error: "异常",
    success: "成功",
  };
  return labels[value] || value;
}

function statusTagType(status?: string | null): "danger" | "warning" | "info" | "success" {
  if (status === "failed" || status === "failed_download" || status === "failed_asr" || status === "failed_summary" || status === "error") return "danger";
  if (status === "processing") return "warning";
  if (status === "pending") return "info";
  if (status === "paused") return "warning";
  if (status === "running" || status === "sent" || status === "done" || status === "success") return "success";
  return "info";
}

function runtimeStatusText(state: TaskRuntimeItem | null) {
  if (!state) return "-";
  return state.is_paused ? "已暂停" : statusText(state.status);
}

function runtimeTagType(status?: string | null): "danger" | "warning" | "success" {
  if (status === "error") return "danger";
  if (status === "paused") return "warning";
  return "success";
}

async function loadOverview() {
  overviewLoading.value = true;
  try {
    taskOverview.value = await api.get<TaskOverview>("/tasks/overview");
  } finally {
    overviewLoading.value = false;
  }
}

async function loadTasks() {
  tableLoading.value = true;
  try {
    const query = {
      page: filters.page,
      page_size: filters.page_size,
      q: filters.q,
      uploader_name: filters.uploader_name,
      content_type: filters.content_type,
      status: filters.status,
      pub_after: filters.pub_range[0] || "",
      pub_before: filters.pub_range[1] || "",
    };
    const data = await api.get<PageResult<TaskItem>>(`/tasks${buildQuery(query)}`);
    taskRows.value = data.items;
    total.value = data.total;
    selectedRows.value = [];
  } finally {
    tableLoading.value = false;
  }
}

async function refreshAll() {
  await Promise.allSettled([loadOverview(), loadTasks()]);
}

function resetFilters() {
  filters.page = 1;
  filters.q = "";
  filters.uploader_name = "";
  filters.content_type = "";
  filters.status = "";
  filters.pub_range = [];
  loadTasks();
}

function changePage(page: number) {
  filters.page = page;
  loadTasks();
}

function changePageSize(size: number) {
  filters.page_size = size;
  filters.page = 1;
  loadTasks();
}

function onSelectionChange(rows: TaskItem[]) {
  selectedRows.value = rows;
}

function isTaskSelected(row: TaskItem): boolean {
  const key = rowKey(row);
  return selectedRows.value.some((item) => rowKey(item) === key);
}

function toggleTaskSelection(row: TaskItem, checked: string | number | boolean) {
  const key = rowKey(row);
  if (Boolean(checked)) {
    if (!isTaskSelected(row)) {
      selectedRows.value = [...selectedRows.value, row];
    }
    return;
  }
  selectedRows.value = selectedRows.value.filter((item) => rowKey(item) !== key);
}

function openDetail(row: TaskItem) {
  activeRow.value = row;
  detailVisible.value = true;
}

function closeDetail() {
  detailVisible.value = false;
}

async function retrySelected() {
  if (!selectedRows.value.length) {
    return;
  }
  if (!window.confirm(`确认重试选中的 ${selectedRows.value.length} 条任务吗？`)) {
    return;
  }
  const payload: TaskRetryRequest = {
    items: selectedRows.value.map((row) => ({
      content_type: row.content_type,
      id: row.id,
    })),
  };
  const result = await api.post<{ success: boolean; message: string }>("/tasks/retry", payload);
  window.alert(result.message || "任务已重新排队");
  await refreshAll();
}

async function retrySingle(row: TaskItem) {
  const payload: TaskRetryRequest = {
    items: [{ content_type: row.content_type, id: row.id }],
  };
  const result = await api.post<{ success: boolean; message: string }>("/tasks/retry", payload);
  window.alert(result.message || "任务已重新排队");
  await refreshAll();
}

async function resetStuckTasks() {
  if (!window.confirm("纭畾瑕佹妸鍗′綇鐨勫鐞嗕腑浠诲姟閲嶇疆涓哄緟澶勭悊鍚楋紵")) {
    return;
  }
  await api.post("/tasks/reset-stuck");
  window.alert("已重置卡住任务");
  await refreshAll();
}

async function toggleRuntime(state: TaskRuntimeItem, paused: boolean) {
  const payload = state.component === "scheduler" ? { scheduler_paused: paused } : { queue_paused: paused };
  const result = await api.put<TaskRuntimeUpdateResponse>("/tasks/runtime", payload);
  const latest = result.runtime_states.find((item) => item.component === state.component);
  if (latest) {
    taskOverview.value.runtime_states = taskOverview.value.runtime_states.map((item) =>
      item.component === latest.component ? latest : item,
    );
  }
  window.alert(paused ? "已暂停" : "已恢复");
  await loadOverview();
}

onMounted(refreshAll);
</script>

<style scoped>
.task-center {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

@media (max-width: 1024px) {
  .task-center :deep(.page-grid--five) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .task-center :deep(.runtime-grid) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .task-center {
    gap: 14px;
  }

  .task-center :deep(.task-hero),
  .task-center :deep(.section-header),
  .task-center :deep(.runtime-card__actions),
  .task-center :deep(.toolbar),
  .task-center :deep(.task-toolbar),
  .task-center :deep(.task-toolbar__summary) {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .task-center :deep(.task-hero__actions) {
    width: 100%;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .task-center :deep(.task-hero__actions .el-button),
  .task-center :deep(.toolbar .el-button),
  .task-center :deep(.task-toolbar .el-button) {
    width: 100%;
  }

  .task-center :deep(.task-toolbar .el-input),
  .task-center :deep(.task-toolbar .el-select),
  .task-center :deep(.task-toolbar .el-date-editor),
  .task-center :deep(.toolbar .el-input),
  .task-center :deep(.toolbar .el-select),
  .task-center :deep(.toolbar .el-date-editor) {
    width: 100% !important;
  }

  .task-center :deep(.page-grid--five),
  .task-center :deep(.runtime-grid) {
    grid-template-columns: minmax(0, 1fr);
  }

  .task-center :deep(.page-card),
  .task-center :deep(.stat-card),
  .task-center :deep(.runtime-card) {
    padding: 14px;
  }

  .task-center :deep(.el-table__cell) {
    padding: 8px 6px;
    font-size: 12px;
  }

  .task-center :deep(.el-table .cell) {
    white-space: normal;
    line-height: 1.45;
  }

  .task-center :deep(.el-pagination) {
    flex-wrap: wrap;
    gap: 8px;
  }

  .task-center :deep(.mobile-hide-sm),
  .task-center :deep(.mobile-hide-md) {
    display: none !important;
  }

  .task-center :deep(.summary-box),
  .task-center :deep(.task-summary) {
    white-space: normal;
    word-break: break-word;
  }

  .task-detail-page {
    position: fixed;
    inset: 0;
    z-index: 2500;
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    background: #f8fafc;
    overflow: hidden auto;
  }

  .mobile-detail-page__top {
    position: sticky;
    top: 0;
    z-index: 1;
    display: grid;
    gap: 8px;
    padding: 14px 16px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(148, 163, 184, 0.18);
    box-shadow: 0 16px 36px rgba(15, 23, 42, 0.08);
    backdrop-filter: blur(18px);
  }

  .mobile-detail-page__back {
    justify-self: start;
    padding: 0;
    color: #2563eb;
    font-weight: 700;
  }

  .mobile-detail-page__eyebrow {
    color: #64748b;
    font-size: 12px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .mobile-detail-page__title {
    font-size: 18px;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.3;
  }

  .mobile-detail-page__subtitle {
    color: #64748b;
    font-size: 12px;
  }

  .mobile-detail-page__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .mobile-detail-card-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-bottom: 12px;
  }

  .mobile-detail-card {
    border-radius: 18px;
  }

  .mobile-detail-link-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .mobile-detail-link-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .mobile-detail-link-item__label {
    color: #64748b;
    font-size: 12px;
  }

  .mobile-detail-pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
  }
}
</style>


