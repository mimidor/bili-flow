<template>
  <div class="dashboard content-audit">
    <section class="hero-card">
      <div class="hero-copy">
        <div class="hero-eyebrow">CONTENT AUDIT</div>
        <h1>内容审核</h1>
        <p class="hero-description">
          审计推送前的 LLM 过滤命中与 skipped 记录，快速回答“为什么没推”。
        </p>
        <div class="hero-badges">
          <span class="hero-badge">跳过记录</span>
          <span class="hero-badge">原因分布</span>
          <span class="hero-badge">作者统计</span>
          <span class="hero-badge">内容类型统计</span>
        </div>
      </div>

      <div class="hero-panel">
        <div>
          <div class="hero-panel__label">跳过总数</div>
          <div class="hero-panel__value">{{ overview?.skipped_total || 0 }}</div>
          <div class="hero-panel__meta">LLM 过滤：{{ overview?.llm_filter_total || 0 }} 次，失败 {{ overview?.llm_filter_failed || 0 }} 次</div>
        </div>
        <div class="hero-panel__split">
          <el-button type="primary" @click="$router.push('/pushes?status=skipped')">查看推送历史</el-button>
          <el-button @click="$router.push('/logs')">查看日志中心</el-button>
        </div>
      </div>
    </section>

    <div class="health-grid">
      <el-card class="health-card">
        <div class="health-card__title">跳过总数</div>
        <div class="health-card__value">{{ overview?.skipped_total || 0 }}</div>
        <div class="health-card__meta">所有 skipped 推送记录</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">LLM 过滤调用</div>
        <div class="health-card__value">{{ overview?.llm_filter_total || 0 }}</div>
        <div class="health-card__meta">content_type = push_filter</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">过滤失败</div>
        <div class="health-card__value">{{ overview?.llm_filter_failed || 0 }}</div>
        <div class="health-card__meta">LLM 过滤调用失败次数</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">最近跳过</div>
        <div class="health-card__value">{{ overview?.recent_skipped.length || 0 }}</div>
        <div class="health-card__meta">当前页最新 skipped 记录</div>
      </el-card>
    </div>

    <div class="chart-grid">
      <el-card class="page-card section">
        <template #header>
          <div class="section-header">
            <div>
              <div class="section__title">跳过原因分布</div>
              <div class="section__desc">按错误信息或摘要聚合的高频原因</div>
            </div>
          </div>
        </template>
        <div class="audit-list">
          <div v-for="item in overview?.reason_rows || []" :key="item.reason" class="audit-list__item">
            <div class="audit-list__meta">
              <el-tag type="warning" size="small">{{ item.count }}</el-tag>
              <span class="muted">原因</span>
            </div>
            <div class="audit-list__title">{{ item.reason }}</div>
            <el-progress :percentage="reasonPercent(item.count)" :show-text="false" />
          </div>
        </div>
      </el-card>

      <el-card class="page-card section">
        <template #header>
          <div class="section-header">
            <div>
              <div class="section__title">内容与作者统计</div>
              <div class="section__desc">观察哪些类型和作者最常被跳过</div>
            </div>
          </div>
        </template>

        <el-table :data="contentRows" stripe size="small">
          <el-table-column prop="content_type" label="内容类型" width="120">
            <template #default="{ row }">{{ translateContentType(row.content_type) }}</template>
          </el-table-column>
          <el-table-column prop="count" label="次数" width="100" />
        </el-table>

        <el-divider />

        <el-table :data="uploaderRows" stripe size="small">
          <el-table-column prop="uploader_name" label="作者" min-width="160" />
          <el-table-column prop="count" label="次数" width="100" />
        </el-table>
      </el-card>
    </div>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">最近跳过记录</div>
            <div class="section__desc">点击标题可跳转到 B 站动态页或推送历史</div>
          </div>
          <el-button text @click="$router.push('/pushes?status=skipped')">更多记录</el-button>
        </div>
      </template>

      <el-table :data="recentSkipped" stripe v-loading="loading">
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="content_type" label="内容类型" width="120">
          <template #default="{ row }">{{ translateContentType(row.content_type) }}</template>
        </el-table-column>
        <el-table-column prop="content_title" label="标题" min-width="260">
          <template #default="{ row }">
            <el-link
              v-if="contentUrl(row.content_type, row.content_id)"
              :href="contentUrl(row.content_type, row.content_id)!"
              target="_blank"
              rel="noopener noreferrer"
              type="primary"
            >
              <span class="summary-box">{{ row.content_title || row.content_id || "-" }}</span>
            </el-link>
            <span v-else class="summary-box">{{ row.content_title || row.content_id || "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="uploader_name" label="作者" width="160" />
        <el-table-column prop="channel" label="渠道" width="120">
          <template #default="{ row }">{{ translateChannel(row.channel) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default>
            <el-tag type="info">跳过</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="response_summary" label="跳过原因" min-width="220">
          <template #default="{ row }">
            <span class="summary-box">{{ row.response_summary || row.error_message || "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="detailVisible" title="审计详情" size="52%">
      <template v-if="activeRow">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="标题">
            <el-link
              v-if="contentUrl(activeRow.content_type, activeRow.content_id)"
              :href="contentUrl(activeRow.content_type, activeRow.content_id)!"
              target="_blank"
              rel="noopener noreferrer"
              type="primary"
            >
              {{ activeRow.content_title || activeRow.content_id || "-" }}
            </el-link>
            <span v-else>{{ activeRow.content_title || activeRow.content_id || "-" }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="内容类型">{{ translateContentType(activeRow.content_type) }}</el-descriptions-item>
          <el-descriptions-item label="内容ID">{{ activeRow.content_id }}</el-descriptions-item>
          <el-descriptions-item label="作者">{{ activeRow.uploader_name || "-" }}</el-descriptions-item>
          <el-descriptions-item label="渠道">{{ translateChannel(activeRow.channel) }}</el-descriptions-item>
          <el-descriptions-item label="跳过原因">
            <pre class="summary-box">{{ activeRow.response_summary || activeRow.error_message || "-" }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="请求内容">
            <pre class="summary-box">{{ prettyJson(activeRow.request_payload) }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="响应内容">
            <pre class="summary-box">{{ prettyJson(activeRow.response_payload) }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { api } from "../api";
import type { ContentAuditOverviewResponse, PushHistoryDetail, PushHistoryItem } from "../types";
import { formatDateTime, prettyJson, translateChannel, translateContentType } from "../utils";

const loading = ref(false);
const overview = ref<ContentAuditOverviewResponse | null>(null);
const recentSkipped = computed<PushHistoryItem[]>(() => overview.value?.recent_skipped || []);
const contentRows = computed(() => overview.value?.content_rows || []);
const uploaderRows = computed(() => overview.value?.uploader_rows || []);
const totalReasons = computed(() => (overview.value?.reason_rows || []).reduce((sum, row) => sum + row.count, 0));

const detailVisible = ref(false);
const activeRow = ref<PushHistoryDetail | null>(null);

function reasonPercent(count: number) {
  const total = totalReasons.value || 1;
  return Math.max(4, Math.round((count / total) * 100));
}

function contentUrl(contentType: string, contentId: string) {
  if (contentType === "dynamic") {
    return `https://www.bilibili.com/opus/${contentId}`;
  }
  return null;
}

async function openDetail(row: PushHistoryItem) {
  try {
    activeRow.value = await api.get<PushHistoryDetail>(`/push-history/${row.id}`);
    detailVisible.value = true;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载审核详情失败");
  }
}

async function load() {
  loading.value = true;
  try {
    overview.value = await api.get<ContentAuditOverviewResponse>("/content-audit/overview");
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>
