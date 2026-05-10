<template>
  <div class="task-center log-page">
    <section class="task-hero">
      <div class="task-hero__copy">
        <div class="task-hero__eyebrow">LOG CENTER</div>
        <h1>日志中心</h1>
        <p class="task-hero__desc">直接读取按日保存的原始日志文件，支持级别、模块、来源文件和时间窗口筛选。</p>
      </div>
      <div class="hero-panel">
        <div>
          <div class="hero-panel__label">告警数</div>
          <div class="hero-panel__value">{{ recentAlerts.length }}</div>
          <div class="hero-panel__meta">优先展示 WARNING / ERROR / CRITICAL</div>
        </div>
        <div class="hero-panel__split">
          <el-button @click="$router.push('/tasks')">任务中心</el-button>
          <el-button @click="$router.push('/monitor')">系统监控</el-button>
        </div>
      </div>
    </section>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">日志检索</div>
            <div class="section__desc">按日文件读取，支持窗口、级别、模块和来源文件过滤</div>
          </div>
          <div class="trend-toolbar">
            <span class="muted">默认窗口</span>
            <el-radio-group v-model="filters.window_days" size="small" @change="loadLogs">
              <el-radio-button :label="7">7 天</el-radio-button>
              <el-radio-button :label="30">30 天</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>

      <div class="toolbar">
        <el-input v-model="filters.q" clearable placeholder="关键字搜索" style="width: 240px" />
        <el-input v-model="filters.module" clearable placeholder="模块 / logger name" style="width: 180px" />
        <el-select v-model="filters.source_file" clearable placeholder="来源文件" style="width: 200px">
          <el-option v-for="item in sourceFileOptions" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select v-model="filters.level" clearable placeholder="级别" style="width: 140px">
          <el-option v-for="item in levelOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-date-picker
          v-model="timeRange"
          type="datetimerange"
          unlink-panels
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          value-format="YYYY-MM-DD HH:mm:ss"
          style="width: 360px"
        />
        <el-button type="primary" :loading="loading" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <div class="chart-grid">
        <el-card class="page-card section">
          <template #header>
            <div class="section-header">
              <div>
                <div class="section__title">最近告警</div>
                <div class="section__desc">WARNING / ERROR / CRITICAL 摘要</div>
              </div>
              <el-tag type="warning" effect="light">{{ recentAlerts.length }}</el-tag>
            </div>
          </template>
          <div class="audit-list">
            <button
              v-for="item in recentAlerts"
              :key="item.id"
              type="button"
              class="audit-list__item"
              @click="openDetail(item)"
            >
              <div class="audit-list__meta">
                <el-tag :type="levelTagType(item.level)" size="small">{{ translateLogLevel(item.level) }}</el-tag>
                <span class="muted">{{ translateLoggerName(item.module) }}</span>
                <span class="muted">{{ item.source_file }}</span>
              </div>
              <div class="audit-list__title">{{ item.excerpt || item.message }}</div>
            </button>
          </div>
        </el-card>

        <el-card class="page-card section">
          <template #header>
            <div class="section-header">
              <div>
                <div class="section__title">来源文件</div>
                <div class="section__desc">从扫描到的文件中切换查看</div>
              </div>
            </div>
          </template>
          <el-tag v-for="item in scannedFiles" :key="item" class="source-file-tag" @click="filters.source_file = item">
            {{ item }}
          </el-tag>
          <el-empty v-if="!scannedFiles.length" description="暂无可用日志文件" />
        </el-card>
      </div>

      <el-table :data="rows" v-loading="loading" stripe class="log-table">
        <el-table-column prop="timestamp" label="时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.timestamp) }}</template>
        </el-table-column>
        <el-table-column prop="level" label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="levelTagType(row.level)">{{ translateLogLevel(row.level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="160">
          <template #default="{ row }">{{ translateLoggerName(row.module) }}</template>
        </el-table-column>
        <el-table-column class-name="mobile-hide-sm" prop="source_file" label="文件" width="180" />
        <el-table-column prop="message" label="消息" min-width="360">
          <template #default="{ row }">
            <div class="summary-box">{{ row.excerpt || row.message }}</div>
          </template>
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

    <el-drawer v-model="detailVisible" title="日志详情" size="58%">
      <div v-loading="detailLoading" class="log-detail">
        <template v-if="activeRow">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="时间">{{ formatDateTime(activeRow.timestamp) }}</el-descriptions-item>
            <el-descriptions-item label="级别">
              <el-tag :type="levelTagType(activeRow.level)">{{ translateLogLevel(activeRow.level) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="模块">{{ translateLoggerName(activeRow.module) }}</el-descriptions-item>
            <el-descriptions-item label="来源文件">{{ activeRow.source_file }}</el-descriptions-item>
            <el-descriptions-item label="行号">{{ activeRow.line_start }} - {{ activeRow.line_end }}</el-descriptions-item>
            <el-descriptions-item label="消息">
              <div class="summary-box">{{ activeRow.message }}</div>
            </el-descriptions-item>
            <el-descriptions-item label="完整日志">
              <pre class="log-raw">{{ activeRow.raw_text }}</pre>
            </el-descriptions-item>
            <el-descriptions-item label="上下文">
              <pre class="log-context">{{ renderContext(activeRow.context_lines) }}</pre>
            </el-descriptions-item>
          </el-descriptions>

          <div class="toolbar" style="justify-content: flex-end; margin-top: 16px">
            <el-button @click="copyContext">复制上下文</el-button>
            <el-button @click="copyRawText">复制完整日志</el-button>
            <el-button type="primary" @click="detailVisible = false">关闭</el-button>
          </div>
        </template>
        <el-empty v-else description="请选择一条日志查看详情" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import { api } from "../api";
import type { LogDetail, LogItem, LogListResponse } from "../types";
import { formatDateTime, logLevelTagType, translateLogLevel, translateLoggerName } from "../utils";

const loading = ref(false);
const detailLoading = ref(false);
const rows = ref<LogItem[]>([]);
const recentAlerts = ref<LogItem[]>([]);
const scannedFiles = ref<string[]>([]);
const total = ref(0);
const detailVisible = ref(false);
const activeRow = ref<LogDetail | null>(null);
const timeRange = ref<string[]>([]);

const filters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  module: "",
  source_file: "",
  level: "",
  window_days: 7,
});

const levelOptions = [
  { label: "调试", value: "DEBUG" },
  { label: "信息", value: "INFO" },
  { label: "警告", value: "WARNING" },
  { label: "错误", value: "ERROR" },
  { label: "严重", value: "CRITICAL" },
];

const sourceFileOptions = computed(() => scannedFiles.value);

function levelTagType(level?: string | null) {
  return logLevelTagType(level);
}

function renderContext(lines: LogDetail["context_lines"]): string {
  return lines
    .map((line) => `${line.line_no.toString().padStart(4, " ")} ${line.is_target ? ">" : " "} ${line.text}`)
    .join("\n");
}

async function loadLogs() {
  loading.value = true;
  try {
    const query = {
      page: filters.page,
      page_size: filters.page_size,
      q: filters.q,
      module: filters.module,
      source_file: filters.source_file,
      level: filters.level,
      window_days: filters.window_days,
      start: timeRange.value[0] || "",
      end: timeRange.value[1] || "",
    };
    const data = await api.get<LogListResponse>(`/logs?${new URLSearchParams(
      Object.entries(query).reduce<Record<string, string>>((acc, [key, value]) => {
        if (value !== undefined && value !== "") acc[key] = String(value);
        return acc;
      }, {}),
    ).toString()}`);
    rows.value = data.items;
    total.value = data.total;
    recentAlerts.value = data.recent_alerts || [];
    scannedFiles.value = data.scanned_files || [];
  } finally {
    loading.value = false;
  }
}

function search() {
  filters.page = 1;
  loadLogs();
}

function reset() {
  filters.page = 1;
  filters.page_size = 20;
  filters.q = "";
  filters.module = "";
  filters.source_file = "";
  filters.level = "";
  filters.window_days = 7;
  timeRange.value = [];
  loadLogs();
}

function changePage(page: number) {
  filters.page = page;
  loadLogs();
}

function changePageSize(size: number) {
  filters.page_size = size;
  filters.page = 1;
  loadLogs();
}

async function openDetail(row: LogItem) {
  detailVisible.value = true;
  detailLoading.value = true;
  activeRow.value = null;
  try {
    activeRow.value = await api.get<LogDetail>(`/logs/${row.id}?context_lines=12`);
  } finally {
    detailLoading.value = false;
  }
}

async function copyRawText() {
  if (!activeRow.value) return;
  await navigator.clipboard.writeText(activeRow.value.raw_text);
  ElMessage.success("已复制完整日志");
}

async function copyContext() {
  if (!activeRow.value) return;
  await navigator.clipboard.writeText(renderContext(activeRow.value.context_lines));
  ElMessage.success("已复制上下文");
}

onMounted(loadLogs);
</script>

<style scoped>
.task-center.log-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

@media (max-width: 1024px) {
  .task-center.log-page :deep(.chart-grid) {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .task-center.log-page {
    gap: 14px;
  }

  .task-center.log-page :deep(.task-hero),
  .task-center.log-page :deep(.section-header),
  .task-center.log-page :deep(.toolbar) {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .task-center.log-page :deep(.hero-panel),
  .task-center.log-page :deep(.hero-panel__split) {
    width: 100%;
  }

  .task-center.log-page :deep(.chart-grid) {
    grid-template-columns: minmax(0, 1fr);
  }

  .task-center.log-page :deep(.toolbar .el-input),
  .task-center.log-page :deep(.toolbar .el-select),
  .task-center.log-page :deep(.toolbar .el-date-editor),
  .task-center.log-page :deep(.toolbar .el-button) {
    width: 100% !important;
  }

  .task-center.log-page :deep(.page-card),
  .task-center.log-page :deep(.el-drawer__body) {
    padding: 14px;
  }

  .task-center.log-page :deep(.audit-list) {
    gap: 10px;
  }

  .task-center.log-page :deep(.el-table__cell) {
    padding: 8px 6px;
    font-size: 12px;
  }

  .task-center.log-page :deep(.el-table .cell) {
    white-space: normal;
    line-height: 1.45;
  }

  .task-center.log-page :deep(.mobile-hide-sm) {
    display: none !important;
  }

  .task-center.log-page :deep(.source-file-tag) {
    margin-bottom: 8px;
  }

  .task-center.log-page :deep(.el-pagination) {
    flex-wrap: wrap;
    gap: 8px;
  }
}
</style>
