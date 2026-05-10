<template>
  <div class="dashboard content-page">
    <section class="page-hero">
      <div class="page-hero__copy">
        <div class="page-hero__eyebrow">CONTENT CENTER</div>
        <h1>视频管理</h1>
        <p class="page-hero__desc">
          从标题、作者、状态和文档链接快速定位处理进度，适合做日常运营和问题回溯。
        </p>
        <div class="page-hero__chips">
          <span class="page-hero__chip">总条数 {{ total }}</span>
          <span class="page-hero__chip">已选 {{ selectedRows.length }}</span>
          <span class="page-hero__chip">当前状态 {{ filters.status || "全部" }}</span>
        </div>
      </div>

      <div class="page-hero__panel">
        <div class="page-hero__panel-label">筛选概览</div>
        <div class="page-hero__panel-value">{{ filters.status || "全部状态" }}</div>
        <div class="page-hero__panel-note">支持按标题、作者、状态组合检索，保留 B 站原始链接和文档跳转。</div>
        <div class="page-hero__stats">
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">总条数</div>
            <div class="page-hero__stat-value">{{ total }}</div>
          </div>
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">已选</div>
            <div class="page-hero__stat-value">{{ selectedRows.length }}</div>
          </div>
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">当前筛选</div>
            <div class="page-hero__stat-value page-hero__stat-value--muted">{{ filters.q ? "关键词" : "默认" }}</div>
          </div>
        </div>
      </div>
    </section>

    <el-card class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.q" clearable placeholder="按标题 / 视频编号搜索" style="width: 280px" />
        <el-input v-model="filters.uploader_name" clearable placeholder="按作者搜索" style="width: 180px" />
        <el-select v-model="filters.status" clearable placeholder="处理状态" style="width: 160px">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button type="warning" :disabled="!selectedIds.length" @click="batchRetry">批量重试</el-button>
        <el-button type="success" :disabled="!selectedIds.length" @click="batchMarkPending">批量标记待处理</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="48" />
        <el-table-column prop="title" label="标题" min-width="260">
          <template #default="{ row }">
            <div>
              <div class="title-link">
                <el-link :href="`https://www.bilibili.com/video/${row.bvid}`" target="_blank" type="primary">
                  {{ row.title }}
                </el-link>
              </div>
              <div class="muted">{{ row.bvid }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="uploader_name" label="作者" width="180" />
        <el-table-column prop="pub_time" label="发布时间" width="180">
          <template #default="{ row }">{{ formatUnixTime(row.pub_time) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ translateStatus(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="attempt_count" label="重试次数" width="100" />
        <el-table-column prop="doc_url" label="文档" min-width="220">
          <template #default="{ row }">
            <el-link v-if="row.doc_url" :href="row.doc_url" target="_blank" type="primary">打开</el-link>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-space>
              <el-button size="small" @click="openDetail(row)">详情</el-button>
              <el-button size="small" type="primary" :loading="isPushing(row.id)" @click="pushVideo(row)">推送</el-button>
              <el-button size="small" type="warning" @click="retry(row)">重试</el-button>
            </el-space>
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

    <el-drawer v-model="detailVisible" title="视频详情" size="50%">
      <div v-loading="detailLoading">
        <template v-if="activeRow">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="标题">{{ activeRow.title }}</el-descriptions-item>
            <el-descriptions-item label="作者">{{ activeRow.uploader_name || "-" }}</el-descriptions-item>
            <el-descriptions-item label="视频编号">{{ activeRow.bvid }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ translateStatus(activeRow.status) }}</el-descriptions-item>
            <el-descriptions-item label="发布时间">{{ formatUnixTime(activeRow.pub_time) }}</el-descriptions-item>
            <el-descriptions-item label="总结">
              <pre class="summary-box">{{ prettyJson(activeRow.summary_json) }}</pre>
            </el-descriptions-item>
            <el-descriptions-item label="原始口播">
              <pre class="summary-box">{{ activeRow.transcript_text || "-" }}</pre>
            </el-descriptions-item>
            <el-descriptions-item label="文档链接">
              <el-link v-if="activeRow.doc_url" :href="activeRow.doc_url" target="_blank" type="primary">
                {{ activeRow.doc_url }}
              </el-link>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="最后错误">{{ activeRow.last_error || "-" }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { api } from "../api";
import type { PageResult, TaskAcceptedResponse, VideoItem } from "../types";
import { buildQuery, formatDateTime, formatUnixTime, prettyJson, translateStatus } from "../utils";

const loading = ref(false);
const rows = ref<VideoItem[]>([]);
const total = ref(0);
const detailVisible = ref(false);
const activeRow = ref<VideoItem | null>(null);
const detailLoading = ref(false);
const selectedRows = ref<VideoItem[]>([]);
const pushingIds = ref<number[]>([]);

const filters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  uploader_name: "",
  status: "",
});

const statusOptions = [
  { label: "待处理", value: "pending" },
  { label: "处理中", value: "processing" },
  { label: "已完成", value: "done" },
  { label: "已过滤", value: "filtered" },
  { label: "失败", value: "failed" },
];

function statusTagType(status: string) {
  if (status === "done") return "success";
  if (status === "failed") return "danger";
  if (status === "processing") return "warning";
  if (status === "filtered") return "info";
  return "info";
}

async function load() {
  loading.value = true;
  try {
    const data = await api.get<PageResult<VideoItem>>(
      `/videos${buildQuery(filters as Record<string, string | number | boolean | null | undefined>)}`
    );
    rows.value = data.items;
    total.value = data.total;
    selectedRows.value = [];
  } finally {
    loading.value = false;
  }
}

function reset() {
  filters.page = 1;
  filters.q = "";
  filters.uploader_name = "";
  filters.status = "";
  load();
}

function changePage(page: number) {
  filters.page = page;
  load();
}

function changePageSize(size: number) {
  filters.page_size = size;
  filters.page = 1;
  load();
}

async function openDetail(row: VideoItem) {
  detailVisible.value = true;
  detailLoading.value = true;
  activeRow.value = row;
  try {
    activeRow.value = await api.get<VideoItem>(`/videos/${row.id}`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载视频详情失败");
  } finally {
    detailLoading.value = false;
  }
}

function isPushing(videoId: number) {
  return pushingIds.value.includes(videoId);
}

function setPushing(videoId: number, pushing: boolean) {
  if (pushing) {
    if (!pushingIds.value.includes(videoId)) {
      pushingIds.value = [...pushingIds.value, videoId];
    }
    return;
  }
  pushingIds.value = pushingIds.value.filter((id) => id !== videoId);
}

function isTerminalStatus(status?: string | null) {
  return ["done", "failed", "filtered", "silented"].includes(status || "");
}

async function waitForPushResult(videoId: number, timeoutMs = 300_000, intervalMs = 2000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const video = await api.get<VideoItem>(`/videos/${videoId}`);
    if (isTerminalStatus(video.status)) {
      return video;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return await api.get<VideoItem>(`/videos/${videoId}`);
}

async function pushVideo(row: VideoItem) {
  if (isPushing(row.id)) return;
  setPushing(row.id, true);
  try {
    const result = await api.post<TaskAcceptedResponse>(`/tasks/async/video/${row.bvid}`);
    ElMessage.success(result.message || `已触发推送 ${row.bvid}`);

    const finalVideo = await waitForPushResult(row.id);
    if (finalVideo.status === "done") {
      ElMessage.success(`推送完成：${finalVideo.title}`);
    } else if (finalVideo.status === "filtered") {
      ElMessage.info(finalVideo.last_error || "视频已过滤，未执行推送");
    } else if (finalVideo.status === "silented") {
      ElMessage.info(finalVideo.last_error || "当前处于静音时段，推送已暂缓");
    } else if (finalVideo.status === "failed") {
      ElMessage.error(finalVideo.last_error || "推送失败");
    } else {
      ElMessage.info(`已触发：当前状态 ${translateStatus(finalVideo.status)}`);
    }
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "推送触发失败");
  } finally {
    setPushing(row.id, false);
  }
}

async function retry(row: VideoItem) {
  await api.post(`/videos/${row.id}/retry`);
  ElMessage.success("已提交重试");
  await load();
}

const selectedIds = computed(() => selectedRows.value.map((row) => row.id));

function handleSelectionChange(selection: VideoItem[]) {
  selectedRows.value = selection;
}

async function batchRetry() {
  if (!selectedIds.value.length) return;
  await ElMessageBox.confirm(`确定批量重试 ${selectedIds.value.length} 条视频吗？`, "提示", { type: "warning" });
  await api.post("/videos/batch-retry", { ids: selectedIds.value });
  ElMessage.success("批量重试已提交");
  await load();
}

async function batchMarkPending() {
  if (!selectedIds.value.length) return;
  await ElMessageBox.confirm(`确定批量标记 ${selectedIds.value.length} 条视频为待处理吗？`, "提示", { type: "warning" });
  await api.patch("/videos/batch-status", { ids: selectedIds.value, status: "pending" });
  ElMessage.success("批量状态已更新");
  await load();
}

onMounted(load);
</script>
