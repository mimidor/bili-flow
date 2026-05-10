<template>
  <div class="dashboard content-page">
    <section class="page-hero">
      <div class="page-hero__copy">
        <div class="page-hero__eyebrow">CONTENT CENTER</div>
        <h1>动态管理</h1>
        <p class="page-hero__desc">
          聚焦正文、作者、状态与推送结果，方便快速查看哪些动态已经发送、跳过或失败。
        </p>
        <div class="page-hero__chips">
          <span class="page-hero__chip">总条数 {{ total }}</span>
          <span class="page-hero__chip">已选 {{ selectedRows.length }}</span>
          <span class="page-hero__chip">当前推送 {{ filters.push_status || "全部" }}</span>
        </div>
      </div>

      <div class="page-hero__panel">
        <div class="page-hero__panel-label">筛选概览</div>
        <div class="page-hero__panel-value">{{ filters.push_status || "全部状态" }}</div>
        <div class="page-hero__panel-note">支持按正文、作者、任务状态和推送状态组合检索，标题可直达 B 站动态页。</div>
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
        <el-input v-model="filters.q" clearable placeholder="按正文 / 动态ID搜索" style="width: 280px" />
        <el-input v-model="filters.uploader_name" clearable placeholder="按作者搜索" style="width: 180px" />
        <el-select v-model="filters.status" clearable placeholder="状态" style="width: 160px">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.push_status" clearable placeholder="推送状态" style="width: 160px">
          <el-option v-for="item in pushStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button type="warning" :disabled="!selectedIds.length" @click="batchRetry">批量重试</el-button>
        <el-button type="success" :disabled="!selectedIds.length" @click="batchMarkPending">批量标记待处理</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="48" />
        <el-table-column prop="text" label="正文" min-width="280">
          <template #default="{ row }">
            <el-link
              v-if="dynamicUrl(row.dynamic_id)"
              :href="dynamicUrl(row.dynamic_id)!"
              target="_blank"
              rel="noopener noreferrer"
              type="primary"
              class="title-link"
            >
              {{ truncate(displayDynamicText(row.text || row.dynamic_id), 120) }}
            </el-link>
            <div v-else class="summary-box">{{ truncate(displayDynamicText(row.text || row.dynamic_id), 120) }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="uploader_name" label="作者" width="180" />
        <el-table-column prop="pub_time" label="发布时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.pub_time) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ translateStatus(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="push_status" label="推送状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.push_status)">{{ translateStatus(row.push_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="doc_url" label="文档" min-width="220">
          <template #default="{ row }">
            <el-link v-if="row.doc_url" :href="row.doc_url" target="_blank" type="primary">打开</el-link>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-space>
              <el-button size="small" @click="openDetail(row)">详情</el-button>
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

    <el-drawer v-model="detailVisible" title="动态详情" size="50%">
      <template v-if="activeRow">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="作者">{{ activeRow.uploader_name || "-" }}</el-descriptions-item>
          <el-descriptions-item label="动态ID">{{ activeRow.dynamic_id }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ activeRow.type ?? "-" }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ translateStatus(activeRow.status) }}</el-descriptions-item>
          <el-descriptions-item label="推送状态">{{ translateStatus(activeRow.push_status) }}</el-descriptions-item>
          <el-descriptions-item label="发布时间">{{ formatDateTime(activeRow.pub_time) }}</el-descriptions-item>
          <el-descriptions-item label="总结">
            <pre class="summary-box">{{ prettyJson(activeRow.summary_json) }}</pre>
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
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { api } from "../api";
import type { DynamicItem, PageResult } from "../types";
import { buildBilibiliOpusUrl, buildQuery, formatDateTime, prettyJson, translateStatus, truncate } from "../utils";

const loading = ref(false);
const rows = ref<DynamicItem[]>([]);
const total = ref(0);
const detailVisible = ref(false);
const activeRow = ref<DynamicItem | null>(null);
const selectedRows = ref<DynamicItem[]>([]);

const filters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  uploader_name: "",
  status: "",
  push_status: "",
});

const statusOptions = [
  { label: "待处理", value: "pending" },
  { label: "处理中", value: "processing" },
  { label: "已发送", value: "sent" },
  { label: "已过滤", value: "filtered" },
  { label: "失败", value: "failed" },
];

const pushStatusOptions = [
  { label: "待处理", value: "pending" },
  { label: "处理中", value: "processing" },
  { label: "已发送", value: "sent" },
  { label: "已过滤", value: "filtered" },
  { label: "失败", value: "failed" },
];

function statusTagType(status: string) {
  if (status === "sent" || status === "done") return "success";
  if (status === "failed") return "danger";
  if (status === "processing") return "warning";
  if (status === "filtered") return "info";
  return "info";
}

function dynamicUrl(dynamicId: string) {
  return buildBilibiliOpusUrl(dynamicId);
}

function displayDynamicText(value: string) {
  return value.split(/\r?\n/)[0].trim();
}

async function load() {
  loading.value = true;
  try {
    const data = await api.get<PageResult<DynamicItem>>(
      `/dynamics${buildQuery(filters as Record<string, string | number | boolean | null | undefined>)}`
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
  filters.push_status = "";
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

function openDetail(row: DynamicItem) {
  activeRow.value = row;
  detailVisible.value = true;
}

async function retry(row: DynamicItem) {
  await api.post(`/dynamics/${row.id}/retry`);
  ElMessage.success("已提交重试");
  await load();
}

const selectedIds = computed(() => selectedRows.value.map((row) => row.id));

function handleSelectionChange(selection: DynamicItem[]) {
  selectedRows.value = selection;
}

async function batchRetry() {
  if (!selectedIds.value.length) return;
  await ElMessageBox.confirm(`确定批量重试 ${selectedIds.value.length} 条动态吗？`, "提示", { type: "warning" });
  await api.post("/dynamics/batch-retry", { ids: selectedIds.value });
  ElMessage.success("批量重试已提交");
  await load();
}

async function batchMarkPending() {
  if (!selectedIds.value.length) return;
  await ElMessageBox.confirm(`确定批量标记 ${selectedIds.value.length} 条动态为待处理吗？`, "提示", {
    type: "warning",
  });
  await api.patch("/dynamics/batch-status", { ids: selectedIds.value, status: "pending" });
  ElMessage.success("批量状态已更新");
  await load();
}

onMounted(load);
</script>
