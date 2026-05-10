<template>
  <div class="manual-push">
    <el-card class="page-card">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">内容运营 / 手动推送</div>
            <div class="section__desc">
              输入 BV 可创建手动推送任务；定时扫描到的本地 `.flv` 任务也会复用同一任务表，在这里统一查看进度。
            </div>
          </div>
          <el-button type="primary" :loading="createLoading" @click="submitTask">创建任务</el-button>
        </div>
      </template>

      <el-form :inline="true" :model="form" class="manual-push__form" @submit.prevent>
        <el-form-item label="推送群">
          <el-select
            v-model="form.push_target_id"
            placeholder="选择飞书群"
            style="width: 260px"
            :loading="pushTargetLoading"
          >
            <el-option
              v-for="target in pushTargets"
              :key="target.id"
              :label="`${target.name}${target.is_default ? '（默认）' : ''}`"
              :value="target.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="BV">
          <el-input
            v-model.trim="form.bvid"
            placeholder="BV1xxxxxxx"
            clearable
            style="width: 260px"
            @keyup.enter="submitTask"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="createLoading" @click="submitTask">提交推送任务</el-button>
          <el-button @click="resetForm">清空</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div class="page-grid page-grid--four">
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">待处理</div>
        <div class="stat-value">{{ summary.pending }}</div>
      </el-card>
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">处理中</div>
        <div class="stat-value">{{ summary.running }}</div>
      </el-card>
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">成功</div>
        <div class="stat-value">{{ summary.success }}</div>
      </el-card>
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">失败</div>
        <div class="stat-value">{{ summary.failed }}</div>
      </el-card>
    </div>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">任务列表</div>
            <div class="section__desc">统一轮询手动 BV 推送任务和本地视频扫描任务。</div>
          </div>
          <div class="toolbar" style="gap: 12px; margin: 0">
            <el-input v-model="filters.q" clearable placeholder="搜索 BV / 标题 / 作者 / 路径 / 消息" style="width: 320px" />
            <el-select v-model="filters.status" clearable placeholder="状态" style="width: 150px">
              <el-option label="待处理" value="pending" />
              <el-option label="运行中" value="running" />
              <el-option label="成功" value="success" />
              <el-option label="失败" value="failed" />
              <el-option label="已取消" value="canceled" />
            </el-select>
            <el-button type="primary" :loading="tableLoading" @click="loadTasks">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="taskRows" v-loading="tableLoading" stripe :row-key="rowKey">
        <el-table-column label="来源" width="130">
          <template #default="{ row }">
            <el-tag :type="row.source_type === 'local_video' ? 'warning' : 'primary'">
              {{ row.source_type === "local_video" ? "本地视频扫描" : "BV 手动推送" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="bvid" label="BV / 来源ID" width="170">
          <template #default="{ row }">
            <span>{{ row.source_type === "local_video" ? "-" : row.bvid }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="push_target_name" label="推送群" width="180">
          <template #default="{ row }">
            <el-tag v-if="row.push_target_name" type="success">{{ row.push_target_name }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="260">
          <template #default="{ row }">
            <div class="task-title-cell">
              <el-link v-if="row.source_url" :href="row.source_url" target="_blank" type="primary" :underline="false">
                {{ row.title || row.bvid }}
              </el-link>
              <span v-else>{{ row.title || row.bvid }}</span>
              <div class="muted">{{ row.uploader_name || "-" }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="stage" label="阶段" width="120">
          <template #default="{ row }">
            <el-tag type="info">{{ stageText(row.stage) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="180">
          <template #default="{ row }">
            <el-progress :percentage="row.progress || 0" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column prop="message" label="当前消息" min-width="220">
          <template #default="{ row }">
            <span class="summary-box">{{ row.message || "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误" min-width="220">
          <template #default="{ row }">
            <span class="summary-box">{{ row.error_message || "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

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

    <el-drawer v-model="detailVisible" title="任务详情" size="52%">
      <template v-if="activeRow">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="任务 ID">{{ activeRow.id }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ activeRow.source_type === "local_video" ? "本地视频扫描" : "BV 手动推送" }}</el-descriptions-item>
          <el-descriptions-item label="BV / 来源ID">{{ activeRow.source_type === "local_video" ? "-" : activeRow.bvid }}</el-descriptions-item>
          <el-descriptions-item label="推送群">{{ activeRow.push_target_name || "-" }}</el-descriptions-item>
          <el-descriptions-item label="标题">{{ activeRow.title || "-" }}</el-descriptions-item>
          <el-descriptions-item label="作者">{{ activeRow.uploader_name || "-" }}</el-descriptions-item>
          <el-descriptions-item v-if="activeRow.source_type === 'local_video'" label="本地路径">
            <span class="summary-box">{{ activeRow.source_path || "-" }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusText(activeRow.status) }}</el-descriptions-item>
          <el-descriptions-item label="阶段">{{ stageText(activeRow.stage) }}</el-descriptions-item>
          <el-descriptions-item label="进度">{{ activeRow.progress }}%</el-descriptions-item>
          <el-descriptions-item label="当前消息">{{ activeRow.message || "-" }}</el-descriptions-item>
          <el-descriptions-item label="错误信息">{{ activeRow.error_message || "-" }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(activeRow.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatDateTime(activeRow.started_at) }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ formatDateTime(activeRow.finished_at) }}</el-descriptions-item>
          <el-descriptions-item label="视频链接">
            <el-link v-if="activeRow.source_url" :href="activeRow.source_url" target="_blank" type="primary">
              {{ activeRow.source_url }}
            </el-link>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="结果">
            <pre class="summary-box">{{ prettyResult(activeRow.result_json) }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import { api } from "../api";
import type {
  ManualPushTaskCreateRequest,
  ManualPushTaskCreateResponse,
  ManualPushTaskDetail,
  ManualPushTaskItem,
  PageResult,
  PushTargetItem,
} from "../types";
import { buildQuery, formatDateTime } from "../utils";

const createLoading = ref(false);
const pushTargetLoading = ref(false);
const tableLoading = ref(false);
const taskRows = ref<ManualPushTaskItem[]>([]);
const pushTargets = ref<PushTargetItem[]>([]);
const total = ref(0);
const detailVisible = ref(false);
const activeRow = ref<ManualPushTaskDetail | null>(null);
const pollingTimer = ref<number | null>(null);

const form = reactive({
  bvid: "",
  push_target_id: null as number | null,
});

const filters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  status: "",
});

const summary = computed(() => ({
  pending: taskRows.value.filter((row) => row.status === "pending").length,
  running: taskRows.value.filter((row) => row.status === "running").length,
  success: taskRows.value.filter((row) => row.status === "success").length,
  failed: taskRows.value.filter((row) => row.status === "failed").length,
}));

function rowKey(row: ManualPushTaskItem): string {
  return String(row.id);
}

function defaultPushTargetId(): number | null {
  const defaultTarget = pushTargets.value.find((item) => item.is_default && item.is_active);
  if (defaultTarget) return defaultTarget.id;
  const firstTarget = pushTargets.value.find((item) => item.is_active);
  return firstTarget?.id ?? null;
}

function statusText(status?: string | null): string {
  if (!status) return "-";
  const labels: Record<string, string> = {
    pending: "待处理",
    running: "运行中",
    success: "成功",
    failed: "失败",
    canceled: "已取消",
  };
  return labels[status] || status;
}

function statusTagType(status?: string | null): "danger" | "warning" | "info" | "success" {
  if (status === "failed") return "danger";
  if (status === "running") return "warning";
  if (status === "pending") return "info";
  if (status === "success") return "success";
  if (status === "canceled") return "warning";
  return "info";
}

function stageText(stage?: string | null): string {
  if (!stage) return "-";
  const labels: Record<string, string> = {
    created: "已创建",
    fetching: "拉取详情",
    downloading: "下载 / 预检",
    asr: "识别",
    summarizing: "总结",
    pushing: "推送",
    done: "完成",
    failed: "失败",
  };
  return labels[stage] || stage;
}

function prettyResult(value?: Record<string, unknown> | string | null): string {
  if (!value) return "-";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

async function loadTasks() {
  tableLoading.value = true;
  try {
    const query = {
      page: filters.page,
      page_size: filters.page_size,
      q: filters.q,
      status: filters.status,
    };
    const data = await api.get<PageResult<ManualPushTaskItem>>(`/manual-push/tasks${buildQuery(query)}`);
    taskRows.value = data.items;
    total.value = data.total;
    if (activeRow.value) {
      if (detailVisible.value) {
        activeRow.value = await api.get<ManualPushTaskDetail>(`/manual-push/tasks/${activeRow.value.id}`);
      } else {
        const latest = data.items.find((item) => item.id === activeRow.value?.id);
        if (latest) activeRow.value = latest as ManualPushTaskDetail;
      }
    }
  } finally {
    tableLoading.value = false;
  }
}

async function loadPushTargets() {
  pushTargetLoading.value = true;
  try {
    const data = await api.get<PageResult<PushTargetItem>>("/push-targets?page=1&page_size=200&is_active=true");
    pushTargets.value = data.items;
    if (form.push_target_id == null) {
      form.push_target_id = defaultPushTargetId();
    } else if (!pushTargets.value.some((item) => item.id === form.push_target_id)) {
      form.push_target_id = defaultPushTargetId();
    }
  } finally {
    pushTargetLoading.value = false;
  }
}

async function submitTask() {
  const bvid = form.bvid.trim();
  if (!bvid) {
    ElMessage.warning("请输入 BV");
    return;
  }

  createLoading.value = true;
  try {
    const payload: ManualPushTaskCreateRequest = {
      bvid,
      push_target_id: form.push_target_id,
    };
    const result = await api.post<ManualPushTaskCreateResponse>("/manual-push/tasks", payload);
    ElMessage.success(`任务已创建：${result.task_id}`);
    form.bvid = "";
    form.push_target_id = defaultPushTargetId();
    filters.page = 1;
    await loadTasks();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "创建任务失败");
  } finally {
    createLoading.value = false;
  }
}

function resetForm() {
  form.bvid = "";
  form.push_target_id = defaultPushTargetId();
}

function changePage(page: number) {
  filters.page = page;
  void loadTasks();
}

function changePageSize(size: number) {
  filters.page_size = size;
  filters.page = 1;
  void loadTasks();
}

async function openDetail(row: ManualPushTaskItem) {
  try {
    activeRow.value = await api.get<ManualPushTaskDetail>(`/manual-push/tasks/${row.id}`);
    detailVisible.value = true;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载任务详情失败");
  }
}

function startPolling() {
  if (pollingTimer.value !== null) return;
  pollingTimer.value = window.setInterval(() => {
    if (!tableLoading.value) void loadTasks();
  }, 3000);
}

function stopPolling() {
  if (pollingTimer.value !== null) {
    window.clearInterval(pollingTimer.value);
    pollingTimer.value = null;
  }
}

onMounted(async () => {
  await loadPushTargets();
  await loadTasks();
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});
</script>
