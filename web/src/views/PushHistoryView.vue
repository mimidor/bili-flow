<template>
  <div class="dashboard">
    <section class="hero-card">
      <div class="hero-copy">
        <div class="hero-eyebrow">PUSH HISTORY</div>
        <h1>推送历史</h1>
        <p class="hero-description">查看视频、动态推送结果，支持审计筛选、跳过原因和时间范围过滤。</p>
      </div>
      <div class="hero-panel">
        <div>
          <div class="hero-panel__label">跳过总数</div>
          <div class="hero-panel__value">{{ audit.skipped_total }}</div>
          <div class="hero-panel__meta">LLM 过滤调用 {{ audit.llm_filter_total }} 次</div>
        </div>
        <div class="hero-panel__split">
          <el-button type="primary" @click="$router.push('/content-audit')">内容审核</el-button>
          <el-button @click="$router.push('/logs')">日志中心</el-button>
        </div>
      </div>
    </section>

    <div class="health-grid">
      <el-card class="health-card">
        <div class="health-card__title">成功</div>
        <div class="health-card__value">{{ statusCount.success }}</div>
        <div class="health-card__meta">已发送推送</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">跳过</div>
        <div class="health-card__value">{{ statusCount.skipped }}</div>
        <div class="health-card__meta">过滤或无须推送</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">失败</div>
        <div class="health-card__value">{{ statusCount.failed }}</div>
        <div class="health-card__meta">发送失败或异常</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">最近记录</div>
        <div class="health-card__value">{{ rows.length }}</div>
        <div class="health-card__meta">当前分页行数</div>
      </el-card>
    </div>

    <div class="chart-grid">
      <el-card class="page-card section">
        <template #header>
          <div class="section-header">
            <div>
              <div class="section__title">跳过原因分布</div>
              <div class="section__desc">聚合 error_message / response_summary</div>
            </div>
          </div>
        </template>
        <div class="audit-list">
          <div v-for="item in audit.reason_rows" :key="item.reason" class="audit-list__item">
            <div class="audit-list__meta">
              <el-tag type="warning" size="small">{{ item.count }}</el-tag>
              <span class="muted">鍘熷洜</span>
            </div>
            <div class="audit-list__title">{{ item.reason }}</div>
          </div>
        </div>
      </el-card>

      <el-card class="page-card section">
        <template #header>
          <div class="section-header">
            <div>
              <div class="section__title">内容类型与作者统计</div>
              <div class="section__desc">查看哪些类型或作者最容易被跳过</div>
            </div>
          </div>
        </template>
        <el-table :data="audit.content_rows" stripe size="small">
          <el-table-column prop="content_type" label="内容类型" width="120">
            <template #default="{ row }">{{ translateContentType(row.content_type) }}</template>
          </el-table-column>
          <el-table-column prop="count" label="娆℃暟" width="100" />
        </el-table>
        <el-divider />
        <el-table :data="audit.uploader_rows" stripe size="small">
          <el-table-column prop="uploader_name" label="作者" min-width="160" />
          <el-table-column prop="count" label="次数" width="100" />
        </el-table>
      </el-card>
    </div>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">推送记录</div>
            <div class="section__desc">支持时间、类型、渠道、状态和关键字筛选</div>
          </div>
          <el-button text @click="$router.push('/content-audit')">内容审核视图</el-button>
        </div>
      </template>

      <div v-if="isMobile" class="mobile-action-strip">
        <el-button size="small" type="primary" :loading="loading" @click="load">刷新列表</el-button>
        <el-button size="small" @click="mobileFiltersVisible = true">筛选条件</el-button>
        <el-button size="small" @click="reset">重置筛选</el-button>
      </div>

      <template v-if="isMobile">
        <div v-if="rows.length" class="mobile-record-list">
          <el-card
            v-for="row in rows"
            :key="`${row.content_type}-${row.content_id}-${row.created_at}`"
            class="mobile-record-card push-mobile-card"
            shadow="never"
          >
            <template #header>
              <div class="mobile-record-card__header">
                <div class="mobile-record-card__headline">
                  <div class="mobile-record-card__badges">
                    <el-tag size="small" :type="row.content_type === 'video' ? 'success' : 'warning'" effect="plain">
                      {{ translateContentType(row.content_type) }}
                    </el-tag>
                    <el-tag size="small" :type="statusTagType(row.status)" effect="plain">
                      {{ translateStatus(row.status) }}
                    </el-tag>
                    <el-tag v-if="row.channel" size="small" type="info" effect="plain">
                      {{ translateChannel(row.channel) }}
                    </el-tag>
                  </div>
                  <div class="mobile-record-card__title">
                    <el-link
                      v-if="contentUrl(row.content_type, row.content_id)"
                      :href="contentUrl(row.content_type, row.content_id)!"
                      target="_blank"
                      rel="noopener noreferrer"
                      type="primary"
                    >
                      {{ row.content_title || row.content_id || "-" }}
                    </el-link>
                    <span v-else>{{ row.content_title || row.content_id || "-" }}</span>
                  </div>
                  <div class="mobile-record-card__subtitle">{{ row.content_id }}</div>
                </div>
              </div>
            </template>

            <div class="mobile-record-card__meta-grid">
              <div>
                <span class="mobile-record-card__meta-label">浣滆€</span>
                <strong>{{ row.uploader_name || "-" }}</strong>
              </div>
              <div>
                <span class="mobile-record-card__meta-label">娓犻亾</span>
                <strong>{{ translateChannel(row.channel) }}</strong>
              </div>
              <div>
                <span class="mobile-record-card__meta-label">鎺ㄩ€佺粍</span>
                <strong>{{ row.target_name || row.target_receive_id || "-" }}</strong>
              </div>
              <div>
                <span class="mobile-record-card__meta-label">鏃堕棿</span>
                <strong>{{ formatDateTime(row.created_at) }}</strong>
              </div>
            </div>

            <div v-if="row.response_summary" class="summary-box mobile-record-card__summary">
              {{ row.response_summary }}
            </div>
            <div v-if="row.error_message" class="summary-box mobile-record-card__summary mobile-record-card__summary--error">
              {{ row.error_message }}
            </div>

            <div class="mobile-record-card__actions">
              <el-button size="small" @click="openDetail(row)">详情</el-button>
            </div>
          </el-card>
        </div>
        <el-empty v-else :description="loading ? '正在加载推送记录' : '暂无推送记录'" />
      </template>

      <template v-else>
        <div class="toolbar">
          <el-input v-model="filters.q" clearable placeholder="按标题 / ID / 摘要搜索" style="width: 260px" />
          <el-input v-model="filters.uploader_name" clearable placeholder="按作者搜索" style="width: 180px" />
          <el-select v-model="filters.content_type" clearable placeholder="内容类型" style="width: 160px">
            <el-option v-for="item in contentTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select v-model="filters.channel" clearable placeholder="渠道" style="width: 160px">
            <el-option v-for="item in channelOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select v-model="filters.status" clearable placeholder="状态" style="width: 160px">
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
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
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </div>

        <el-table :data="rows" v-loading="loading" stripe>
          <el-table-column prop="created_at" label="时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="content_type" label="内容类型" width="120">
            <template #default="{ row }">{{ translateContentType(row.content_type) }}</template>
          </el-table-column>
          <el-table-column class-name="mobile-hide-sm" prop="content_id" label="内容ID" width="180" />
          <el-table-column prop="content_title" label="标题" min-width="240">
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
          <el-table-column class-name="mobile-hide-sm" prop="uploader_name" label="作者" width="180" />
          <el-table-column class-name="mobile-hide-md" prop="channel" label="渠道" width="120">
            <template #default="{ row }">{{ translateChannel(row.channel) }}</template>
          </el-table-column>
          <el-table-column class-name="mobile-hide-sm" prop="target_name" label="推送组" width="220">
            <template #default="{ row }">{{ row.target_name || row.target_receive_id || "-" }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">{{ translateStatus(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column class-name="mobile-hide-sm" prop="response_summary" label="响应摘要" min-width="220">
            <template #default="{ row }">
              <span class="summary-box">{{ row.response_summary || "-" }}</span>
            </template>
          </el-table-column>
          <el-table-column class-name="mobile-hide-sm" prop="error_message" label="错误信息" min-width="220">
            <template #default="{ row }">
              <span class="summary-box">{{ row.error_message || "-" }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" @click="openDetail(row)">详情</el-button>
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

    <el-drawer v-model="mobileFiltersVisible" title="推送筛选" size="85%">
      <el-form label-position="top" class="mobile-filter-form">
        <el-form-item label="关键词">
          <el-input v-model="filters.q" clearable placeholder="按标题 / ID / 摘要搜索" />
        </el-form-item>
        <el-form-item label="作者">
          <el-input v-model="filters.uploader_name" clearable placeholder="按作者搜索" />
        </el-form-item>
        <el-form-item label="内容类型">
          <el-select v-model="filters.content_type" clearable placeholder="内容类型" style="width: 100%">
            <el-option v-for="item in contentTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="渠道">
          <el-select v-model="filters.channel" clearable placeholder="渠道" style="width: 100%">
            <el-option v-for="item in channelOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="状态" style="width: 100%">
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="timeRange"
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
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </div>
      </el-form>
    </el-drawer>

    <div v-if="isMobile && detailVisible && activeRow" class="mobile-detail-page push-detail-page">
      <div class="mobile-detail-page__top">
        <el-button text class="mobile-detail-page__back" @click="closeDetail">返回列表</el-button>
        <div>
          <div class="mobile-detail-page__eyebrow">推送详情</div>
          <div class="mobile-detail-page__title">
            {{ activeRow.content_title || activeRow.content_id || "-" }}
          </div>
          <div class="mobile-detail-page__subtitle">
            {{ translateContentType(activeRow.content_type) }} · {{ translateStatus(activeRow.status) }}
          </div>
        </div>
        <div class="mobile-detail-page__actions">
          <el-button v-if="contentUrl(activeRow.content_type, activeRow.content_id)" size="small" type="primary" plain @click="openContent(activeRow)">
            打开原文
          </el-button>
          <el-button size="small" @click="closeDetail">关闭</el-button>
        </div>
      </div>

      <div class="mobile-detail-card-grid">
        <el-card shadow="never" class="mobile-detail-card">
          <template #header>基本信息</template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="标题">
              <span>{{ activeRow.content_title || activeRow.content_id || "-" }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="内容类型">{{ translateContentType(activeRow.content_type) }}</el-descriptions-item>
            <el-descriptions-item label="内容ID">{{ activeRow.content_id }}</el-descriptions-item>
            <el-descriptions-item label="作者">{{ activeRow.uploader_name || "-" }}</el-descriptions-item>
            <el-descriptions-item label="渠道">{{ translateChannel(activeRow.channel) }}</el-descriptions-item>
            <el-descriptions-item label="推送组">{{ activeRow.target_name || activeRow.target_receive_id || "-" }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ translateStatus(activeRow.status) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card shadow="never" class="mobile-detail-card">
          <template #header>请求内容</template>
          <pre class="summary-box mobile-detail-pre">{{ prettyJson(activeRow.request_payload) }}</pre>
        </el-card>

        <el-card shadow="never" class="mobile-detail-card">
          <template #header>响应内容</template>
          <pre class="summary-box mobile-detail-pre">{{ prettyJson(activeRow.response_payload) }}</pre>
        </el-card>
      </div>
    </div>

    <el-drawer v-else v-model="detailVisible" title="推送详情" size="50%">
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
          <el-descriptions-item label="推送组">{{ activeRow.target_name || activeRow.target_receive_id || "-" }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ translateStatus(activeRow.status) }}</el-descriptions-item>
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
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { useRoute } from "vue-router";

import { api } from "../api";
import { useBreakpoint } from "../composables/useBreakpoint";
import type { ContentAuditOverviewResponse, PageResult, PushHistoryDetail, PushHistoryItem } from "../types";
import { buildBilibiliContentUrl, buildQuery, formatDateTime, prettyJson, translateChannel, translateContentType, translateStatus } from "../utils";

const route = useRoute();
const { isMobile } = useBreakpoint();
const loading = ref(false);
const rows = ref<PushHistoryItem[]>([]);
const total = ref(0);
const detailVisible = ref(false);
const activeRow = ref<PushHistoryDetail | null>(null);
const mobileFiltersVisible = ref(false);
const audit = ref<ContentAuditOverviewResponse>({
  skipped_total: 0,
  llm_filter_total: 0,
  llm_filter_failed: 0,
  reason_rows: [],
  content_rows: [],
  uploader_rows: [],
  recent_skipped: [],
});
const timeRange = ref<string[]>([]);

const filters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  uploader_name: "",
  content_type: "",
  channel: "",
  status: "",
});

const contentTypeOptions = [
  { label: "视频", value: "video" },
  { label: "动态", value: "dynamic" },
];

const channelOptions = [{ label: "椋炰功", value: "feishu" }];

const statusOptions = [
  { label: "成功", value: "success" },
  { label: "已跳过", value: "skipped" },
  { label: "失败", value: "failed" },
];

const statusCount = computed(() => ({
  success: rows.value.filter((row) => row.status === "success").length,
  skipped: rows.value.filter((row) => row.status === "skipped").length,
  failed: rows.value.filter((row) => row.status === "failed").length,
}));

function contentUrl(contentType: string, contentId: string) {
  return buildBilibiliContentUrl(contentType, contentId);
}

function statusTagType(status: string) {
  if (status === "success") return "success";
  if (status === "skipped") return "info";
  return "danger";
}

async function loadAudit() {
  audit.value = await api.get<ContentAuditOverviewResponse>("/content-audit/overview");
}

async function load() {
  loading.value = true;
  try {
    const query = {
      ...filters,
      start: timeRange.value[0] || "",
      end: timeRange.value[1] || "",
    };
    const data = await api.get<PageResult<PushHistoryItem>>(`/push-history${buildQuery(query)}`);
    rows.value = data.items;
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

function reset() {
  filters.page = 1;
  filters.q = "";
  filters.uploader_name = "";
  filters.content_type = "";
  filters.channel = "";
  filters.status = route.query.status ? String(route.query.status) : "";
  timeRange.value = [];
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

async function openDetail(row: PushHistoryItem) {
  try {
    activeRow.value = await api.get<PushHistoryDetail>(`/push-history/${row.id}`);
    detailVisible.value = true;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载推送详情失败");
  }
}

function closeDetail() {
  detailVisible.value = false;
}

function openContent(row: PushHistoryItem) {
  const url = contentUrl(row.content_type, row.content_id);
  if (url) {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

onMounted(async () => {
  if (route.query.status) {
    filters.status = String(route.query.status);
  }
  await Promise.all([loadAudit(), load()]);
});
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

@media (max-width: 1024px) {
  .dashboard :deep(.health-grid) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard :deep(.chart-grid) {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .dashboard {
    gap: 14px;
  }

  .dashboard :deep(.hero-card),
  .dashboard :deep(.section-header),
  .dashboard :deep(.toolbar) {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .dashboard :deep(.hero-panel),
  .dashboard :deep(.hero-panel__split) {
    width: 100%;
  }

  .dashboard :deep(.hero-panel__split) {
    flex-wrap: wrap;
  }

  .dashboard :deep(.health-grid),
  .dashboard :deep(.chart-grid) {
    grid-template-columns: minmax(0, 1fr);
  }

  .dashboard :deep(.toolbar .el-input),
  .dashboard :deep(.toolbar .el-select),
  .dashboard :deep(.toolbar .el-date-editor),
  .dashboard :deep(.toolbar .el-button) {
    width: 100% !important;
  }

  .dashboard :deep(.page-card) {
    padding: 14px;
  }

  .dashboard :deep(.mobile-hide-sm),
  .dashboard :deep(.mobile-hide-md) {
    display: none !important;
  }

  .mobile-detail-page__title {
    word-break: break-word;
  }
}
</style>

