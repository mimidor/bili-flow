<template>
  <div class="qteasy-form-stack">
    <div class="health-grid">
      <el-card class="health-card">
        <div class="health-card__title">文件数量</div>
        <div class="health-card__value">{{ files.length }}</div>
        <div class="health-card__meta">交易日志文件</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">最近文件</div>
        <div class="health-card__value">{{ files[0]?.name || "-" }}</div>
        <div class="health-card__meta">按服务返回顺序</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">状态</div>
        <div class="health-card__value">{{ loading ? "加载中" : "就绪" }}</div>
        <div class="health-card__meta">下载使用 fetch blob</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">错误</div>
        <div class="health-card__value">{{ errorMessage ? "有错误" : "正常" }}</div>
        <div class="health-card__meta">接口或下载异常</div>
      </el-card>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="warning" :closable="false" show-icon />

    <el-card class="page-card section">
      <template #header>
        <div class="section-header section-header--space-between">
          <div>
            <div class="section__title">交易日志文件</div>
            <div class="section__desc">从独立 Qteasy 服务列出交易日志，点击即可下载原始文件。</div>
          </div>
          <el-button type="primary" :loading="loading" @click="loadFiles">刷新列表</el-button>
        </div>
      </template>

      <el-table :data="files" v-loading="loading" stripe>
        <el-table-column prop="name" label="文件名" min-width="260" />
        <el-table-column prop="size" label="大小" width="120">
          <template #default="{ row }">{{ formatSize(row.size) }}</template>
        </el-table-column>
        <el-table-column prop="mtime" label="更新时间" width="180">
          <template #default="{ row }">{{ formatMtime(row.mtime) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button size="small" :loading="downloading === row.name" @click="downloadFile(row.name)">下载</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && !files.length" description="当前没有可下载的交易日志" class="u-mt-16" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import { qteasyApi } from "../services/qteasy";
import type { QteasyReportFileItem } from "../types";
import { formatDateTime } from "../utils";

const loading = ref(false);
const downloading = ref("");
const errorMessage = ref("");
const files = ref<QteasyReportFileItem[]>([]);

function formatSize(value?: number | null): string {
  if (value === null || value === undefined) return "-";
  const size = Number(value);
  if (!Number.isFinite(size) || size < 0) return "-";
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(2)} MB`;
  if (size >= 1024) return `${(size / 1024).toFixed(2)} KB`;
  return `${size} B`;
}

function formatMtime(value?: number | null): string {
  if (value === null || value === undefined) return "-";
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0) return "-";
  return formatDateTime(new Date(seconds * 1000).toISOString());
}

async function loadFiles(): Promise<void> {
  loading.value = true;
  errorMessage.value = "";
  try {
    const payload = await qteasyApi.get<{ files?: QteasyReportFileItem[] }>("/reports/trade-logs");
    files.value = Array.isArray(payload.files) ? payload.files : [];
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.value = false;
  }
}

async function downloadFile(filename: string): Promise<void> {
  downloading.value = filename;
  try {
    const response = await qteasyApi.raw(`/reports/trade-logs/${encodeURIComponent(filename)}`);
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    downloading.value = "";
  }
}

onMounted(() => {
  void loadFiles();
});
</script>
