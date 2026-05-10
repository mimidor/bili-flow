<template>
  <div class="dashboard podcast-page">
    <section class="page-hero">
      <div class="page-hero__copy">
        <div class="page-hero__eyebrow">AUDIO CENTER</div>
        <h1>小宇宙管理</h1>
        <p class="page-hero__desc">
          围绕节目订阅和单集列表做统一管理，方便快速查看抓取、摘要、推送和失败情况。
        </p>
        <div class="page-hero__chips">
          <span class="page-hero__chip">节目 {{ subscriptionTotal }}</span>
          <span class="page-hero__chip">单集 {{ episodeTotal }}</span>
          <span class="page-hero__chip">当前页签 {{ activeTab === "subscriptions" ? "节目" : "单集" }}</span>
        </div>
      </div>

      <div class="page-hero__panel">
        <div class="page-hero__panel-label">当前视图</div>
        <div class="page-hero__panel-value">{{ activeTab === "subscriptions" ? "节目列表" : "单集列表" }}</div>
        <div class="page-hero__panel-note">支持节目订阅、首批抓取、失败重试以及单集详情查看。</div>
        <div class="page-hero__stats">
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">节目</div>
            <div class="page-hero__stat-value">{{ subscriptionTotal }}</div>
          </div>
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">单集</div>
            <div class="page-hero__stat-value">{{ episodeTotal }}</div>
          </div>
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">当前</div>
            <div class="page-hero__stat-value page-hero__stat-value--muted">{{ activeTab }}</div>
          </div>
        </div>
      </div>
    </section>

    <el-tabs v-model="activeTab" type="card" class="page-tabs">
      <el-tab-pane label="小宇宙节目" name="subscriptions">
        <el-card class="page-card section">
          <template #header>
            <div class="section__title">小宇宙节目</div>
          </template>

          <div class="toolbar">
            <el-input v-model="subscriptionFilters.q" clearable placeholder="按节目名 / PID 搜索" style="width: 260px" />
            <el-select v-model="subscriptionFilters.is_active" clearable placeholder="是否启用" style="width: 140px">
              <el-option label="启用" :value="true" />
              <el-option label="停用" :value="false" />
            </el-select>
            <el-button type="primary" @click="searchSubscriptions">查询</el-button>
            <el-button @click="resetSubscriptionFilters">重置</el-button>
            <el-button type="success" @click="openSubscriptionDialog()">新增节目</el-button>
            <el-button type="warning" :disabled="!subscriptionSelectedIds.length" @click="batchUpdateSubscriptions(true)">
              批量启用
            </el-button>
            <el-button type="info" :disabled="!subscriptionSelectedIds.length" @click="batchUpdateSubscriptions(false)">
              批量停用
            </el-button>
            <el-button type="danger" :disabled="!subscriptionSelectedIds.length" @click="batchDeleteSubscriptions">
              批量删除
            </el-button>
          </div>

          <el-table :data="subscriptions" stripe v-loading="loadingSubscriptions" @selection-change="handleSubscriptionSelection">
            <el-table-column type="selection" width="48" />
            <el-table-column prop="pid" label="PID" width="180" />
            <el-table-column prop="name" label="节目名" width="220" />
            <el-table-column prop="homepage_url" label="主页" min-width="280">
              <template #default="{ row }">
                <el-link :href="resolvePodcastHomepageUrl(row)" target="_blank" type="primary" :underline="false">
                  {{ resolvePodcastHomepageUrl(row) }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="启用" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ translateBoolean(row.is_active) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="bootstrap_recent_episodes" label="首批条数" width="100" />
            <el-table-column prop="last_episode_eid" label="最后单集" width="180" />
            <el-table-column prop="last_episode_pub_time" label="最后发布时间" width="180">
              <template #default="{ row }">{{ formatDateTime(row.last_episode_pub_time) }}</template>
            </el-table-column>
            <el-table-column prop="consecutive_failures" label="失败次数" width="100" />
            <el-table-column prop="last_check_time" label="最后检查" width="180">
              <template #default="{ row }">{{ formatDateTime(row.last_check_time) }}</template>
            </el-table-column>
            <el-table-column prop="notes" label="备注" min-width="180" />
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-space>
                  <el-button size="small" @click="openSubscriptionDialog(row)">编辑</el-button>
                  <el-button size="small" type="danger" @click="deleteSubscription(row)">删除</el-button>
                </el-space>
              </template>
            </el-table-column>
          </el-table>

          <div class="toolbar" style="justify-content: flex-end; margin-top: 16px">
            <el-pagination
              layout="prev, pager, next, total, sizes"
              :current-page="subscriptionFilters.page"
              :page-size="subscriptionFilters.page_size"
              :page-sizes="[10, 20, 50, 100]"
              :total="subscriptionTotal"
              @current-change="changeSubscriptionPage"
              @size-change="changeSubscriptionPageSize"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="小宇宙单集" name="episodes">
        <el-card class="page-card section">
          <template #header>
            <div class="section__title">小宇宙单集</div>
          </template>

          <div class="toolbar">
            <el-input v-model="episodeFilters.q" clearable placeholder="按标题 / EID 搜索" style="width: 240px" />
            <el-input v-model="episodeFilters.uploader_name" clearable placeholder="按节目名搜索" style="width: 180px" />
            <el-input v-model="episodeFilters.pid" clearable placeholder="按 PID 搜索" style="width: 180px" />
            <el-select v-model="episodeFilters.status" clearable placeholder="处理状态" style="width: 140px">
              <el-option label="待处理" value="pending" />
              <el-option label="处理中" value="processing" />
              <el-option label="已完成" value="done" />
              <el-option label="失败" value="failed" />
              <el-option label="过滤" value="filtered" />
            </el-select>
            <el-select v-model="episodeFilters.push_status" clearable placeholder="推送状态" style="width: 140px">
              <el-option label="待处理" value="pending" />
              <el-option label="处理中" value="processing" />
              <el-option label="成功" value="success" />
              <el-option label="失败" value="failed" />
              <el-option label="跳过" value="skipped" />
            </el-select>
            <el-button type="primary" :loading="loadingEpisodes" @click="searchEpisodes">查询</el-button>
            <el-button @click="resetEpisodeFilters">重置</el-button>
            <el-button type="warning" :disabled="!episodeSelectedIds.length" @click="batchRetryEpisodes">批量重试</el-button>
            <el-button type="info" :disabled="!episodeSelectedIds.length" @click="batchMarkPending">批量待处理</el-button>
          </div>

          <el-table :data="episodes" stripe v-loading="loadingEpisodes" @selection-change="handleEpisodeSelection">
            <el-table-column type="selection" width="48" />
            <el-table-column prop="title" label="标题" min-width="240">
              <template #default="{ row }">
                <div>
                  <div class="task-title-cell">
                    <el-link v-if="row.audio_url" :href="row.audio_url" target="_blank" type="primary" :underline="false">
                      {{ row.title }}
                    </el-link>
                    <span v-else>{{ row.title }}</span>
                  </div>
                  <div class="muted">{{ row.eid }}</div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="uploader_name" label="节目" width="180" />
            <el-table-column prop="status" label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="push_status" label="推送" width="110">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.push_status)">{{ statusText(row.push_status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="pub_time" label="发布时间" width="180">
              <template #default="{ row }">{{ formatDateTime(row.pub_time) }}</template>
            </el-table-column>
            <el-table-column prop="attempt_count" label="重试" width="80" />
            <el-table-column prop="last_error" label="错误信息" min-width="220">
              <template #default="{ row }">
                <span class="summary-box">{{ row.last_error || "-" }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-space>
                  <el-button size="small" @click="openEpisodeDetail(row)">详情</el-button>
                  <el-button size="small" type="warning" @click="retryEpisode(row)">重试</el-button>
                </el-space>
              </template>
            </el-table-column>
          </el-table>

          <div class="toolbar" style="justify-content: flex-end; margin-top: 16px">
            <el-pagination
              layout="prev, pager, next, total, sizes"
              :current-page="episodeFilters.page"
              :page-size="episodeFilters.page_size"
              :page-sizes="[10, 20, 50, 100]"
              :total="episodeTotal"
              @current-change="changeEpisodePage"
              @size-change="changeEpisodePageSize"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="subscriptionDialogVisible" :title="subscriptionForm.id ? '编辑节目' : '新增节目'" width="560px">
      <el-form label-width="120px">
        <el-form-item label="PID">
          <el-input v-model="subscriptionForm.pid" :disabled="!!subscriptionForm.id" />
        </el-form-item>
        <el-form-item label="节目名">
          <el-input v-model="subscriptionForm.name" />
        </el-form-item>
        <el-form-item label="主页">
          <el-input v-model="subscriptionForm.homepage_url" placeholder="https://www.xiaoyuzhoufm.com/podcast/xxx" />
        </el-form-item>
        <el-form-item label="首批条数">
          <el-input-number v-model="subscriptionForm.bootstrap_recent_episodes" :min="0" :max="20" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="subscriptionForm.notes" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="subscriptionForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="subscriptionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSubscription">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="episodeDetailVisible" title="单集详情" size="50%">
      <template v-if="activeEpisode">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="标题">{{ activeEpisode.title }}</el-descriptions-item>
          <el-descriptions-item label="节目">{{ activeEpisode.uploader_name || "-" }}</el-descriptions-item>
          <el-descriptions-item label="EID">{{ activeEpisode.eid }}</el-descriptions-item>
          <el-descriptions-item label="PID">{{ activeEpisode.pid }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusText(activeEpisode.status) }}</el-descriptions-item>
          <el-descriptions-item label="推送状态">{{ statusText(activeEpisode.push_status) }}</el-descriptions-item>
          <el-descriptions-item label="发布时间">{{ formatDateTime(activeEpisode.pub_time) }}</el-descriptions-item>
          <el-descriptions-item label="下载地址">
            <el-link :href="activeEpisode.audio_url" target="_blank" type="primary">{{ activeEpisode.audio_url }}</el-link>
          </el-descriptions-item>
          <el-descriptions-item label="文档链接">
            <el-link v-if="activeEpisode.doc_url" :href="activeEpisode.doc_url" target="_blank" type="primary">
              {{ activeEpisode.doc_url }}
            </el-link>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="错误信息">
            <pre class="summary-box">{{ activeEpisode.last_error || "-" }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="摘要">
            <pre class="summary-box">{{ prettyJson(activeEpisode.summary_json) }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="原始数据">
            <pre class="summary-box">{{ prettyJson(activeEpisode.raw_episode_json) }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { api } from "../api";
import type { PageResult, PodcastEpisodeItem, PodcastSubscriptionItem } from "../types";
import { buildQuery, formatDateTime, prettyJson, translateBoolean } from "../utils";

const activeTab = ref("subscriptions");
const loadingSubscriptions = ref(false);
const loadingEpisodes = ref(false);

const subscriptions = ref<PodcastSubscriptionItem[]>([]);
const subscriptionTotal = ref(0);
const episodes = ref<PodcastEpisodeItem[]>([]);
const episodeTotal = ref(0);

const subscriptionSelectedIds = ref<number[]>([]);
const episodeSelectedIds = ref<number[]>([]);

const subscriptionDialogVisible = ref(false);
const episodeDetailVisible = ref(false);
const activeEpisode = ref<PodcastEpisodeItem | null>(null);

const subscriptionFilters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  is_active: undefined as boolean | undefined,
});

const episodeFilters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  pid: "",
  uploader_name: "",
  status: "",
  push_status: "",
});

const subscriptionForm = reactive({
  id: null as number | null,
  pid: "",
  name: "",
  homepage_url: "",
  notes: "",
  bootstrap_recent_episodes: 3,
  is_active: true,
});

function statusText(value?: string | null): string {
  if (!value) return "-";
  const labels: Record<string, string> = {
    pending: "待处理",
    processing: "处理中",
    done: "已完成",
    failed: "失败",
    failed_download: "下载失败",
    failed_asr: "识别失败",
    failed_summary: "总结失败",
    sent: "已发送",
    filtered: "已过滤",
    skipped: "已跳过",
    success: "成功",
  };
  return labels[value] || value;
}

function statusTagType(status?: string | null): "danger" | "warning" | "info" | "success" {
  if (status === "failed" || status === "failed_download" || status === "failed_asr" || status === "failed_summary") return "danger";
  if (status === "processing") return "warning";
  if (status === "pending") return "info";
  if (status === "sent" || status === "done" || status === "success") return "success";
  if (status === "filtered" || status === "skipped") return "warning";
  return "info";
}

function resolvePodcastHomepageUrl(row?: PodcastSubscriptionItem | null): string {
  if (!row) return "";
  return row.homepage_url || `https://www.xiaoyuzhoufm.com/podcast/${row.pid}`;
}

function resetSubscriptionForm() {
  subscriptionForm.id = null;
  subscriptionForm.pid = "";
  subscriptionForm.name = "";
  subscriptionForm.homepage_url = "";
  subscriptionForm.notes = "";
  subscriptionForm.bootstrap_recent_episodes = 3;
  subscriptionForm.is_active = true;
}

function openSubscriptionDialog(row?: PodcastSubscriptionItem) {
  if (row) {
    subscriptionForm.id = row.id;
    subscriptionForm.pid = row.pid;
    subscriptionForm.name = row.name;
    subscriptionForm.homepage_url = row.homepage_url || "";
    subscriptionForm.notes = row.notes || "";
    subscriptionForm.bootstrap_recent_episodes = row.bootstrap_recent_episodes || 3;
    subscriptionForm.is_active = row.is_active;
  } else {
    resetSubscriptionForm();
  }
  subscriptionDialogVisible.value = true;
}

async function saveSubscription() {
  const payload = {
    pid: subscriptionForm.pid,
    name: subscriptionForm.name,
    homepage_url: subscriptionForm.homepage_url || null,
    notes: subscriptionForm.notes || null,
    bootstrap_recent_episodes: subscriptionForm.bootstrap_recent_episodes,
    is_active: subscriptionForm.is_active,
  };
  if (subscriptionForm.id) {
    await api.put(`/podcast-subscriptions/${subscriptionForm.id}`, payload);
  } else {
    await api.post("/podcast-subscriptions", payload);
  }
  subscriptionDialogVisible.value = false;
  ElMessage.success("保存成功");
  await loadSubscriptions();
}

async function deleteSubscription(row: PodcastSubscriptionItem) {
  await ElMessageBox.confirm(`确认删除节目 ${row.name}？`, "提示", { type: "warning" });
  await api.delete(`/podcast-subscriptions/${row.id}`);
  ElMessage.success("删除成功");
  await loadSubscriptions();
}

function buildListQuery(params: Record<string, string | number | boolean | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === "") return;
    query.set(key, String(value));
  });
  const text = query.toString();
  return text ? `?${text}` : "";
}

async function loadSubscriptions() {
  loadingSubscriptions.value = true;
  try {
    const data = await api.get<PageResult<PodcastSubscriptionItem>>(
      `/podcast-subscriptions${buildListQuery(subscriptionFilters as Record<string, string | number | boolean | undefined>)}`
    );
    subscriptions.value = data.items;
    subscriptionTotal.value = data.total;
    subscriptionSelectedIds.value = [];
  } finally {
    loadingSubscriptions.value = false;
  }
}

async function loadEpisodes() {
  loadingEpisodes.value = true;
  try {
    const data = await api.get<PageResult<PodcastEpisodeItem>>(
      `/podcast-episodes${buildListQuery(episodeFilters as Record<string, string | number | boolean | undefined>)}`
    );
    episodes.value = data.items;
    episodeTotal.value = data.total;
    episodeSelectedIds.value = [];
  } finally {
    loadingEpisodes.value = false;
  }
}

function searchSubscriptions() {
  subscriptionFilters.page = 1;
  loadSubscriptions();
}

function resetSubscriptionFilters() {
  subscriptionFilters.page = 1;
  subscriptionFilters.q = "";
  subscriptionFilters.is_active = undefined;
  loadSubscriptions();
}

function changeSubscriptionPage(page: number) {
  subscriptionFilters.page = page;
  loadSubscriptions();
}

function changeSubscriptionPageSize(size: number) {
  subscriptionFilters.page_size = size;
  subscriptionFilters.page = 1;
  loadSubscriptions();
}

function searchEpisodes() {
  episodeFilters.page = 1;
  loadEpisodes();
}

function resetEpisodeFilters() {
  episodeFilters.page = 1;
  episodeFilters.q = "";
  episodeFilters.pid = "";
  episodeFilters.uploader_name = "";
  episodeFilters.status = "";
  episodeFilters.push_status = "";
  loadEpisodes();
}

function changeEpisodePage(page: number) {
  episodeFilters.page = page;
  loadEpisodes();
}

function changeEpisodePageSize(size: number) {
  episodeFilters.page_size = size;
  episodeFilters.page = 1;
  loadEpisodes();
}

function handleSubscriptionSelection(selection: PodcastSubscriptionItem[]) {
  subscriptionSelectedIds.value = selection.map((row) => row.id);
}

function handleEpisodeSelection(selection: PodcastEpisodeItem[]) {
  episodeSelectedIds.value = selection.map((row) => row.id);
}

async function batchUpdateSubscriptions(isActive: boolean) {
  if (!subscriptionSelectedIds.value.length) return;
  const actionText = isActive ? "启用" : "停用";
  await ElMessageBox.confirm(`确定批量${actionText} ${subscriptionSelectedIds.value.length} 个节目吗？`, "提示", {
    type: "warning",
  });
  await api.patch("/podcast-subscriptions/batch-active", {
    ids: subscriptionSelectedIds.value,
    is_active: isActive,
  });
  ElMessage.success(`批量${actionText}成功`);
  await loadSubscriptions();
}

async function batchDeleteSubscriptions() {
  if (!subscriptionSelectedIds.value.length) return;
  await ElMessageBox.confirm(`确定批量删除 ${subscriptionSelectedIds.value.length} 个节目吗？`, "提示", {
    type: "warning",
  });
  await api.post("/podcast-subscriptions/batch-delete", { ids: subscriptionSelectedIds.value });
  ElMessage.success("批量删除成功");
  await loadSubscriptions();
}

async function retryEpisode(row: PodcastEpisodeItem) {
  await api.post(`/podcast-episodes/${row.id}/retry`, {});
  ElMessage.success("已重新入队");
  await loadEpisodes();
}

async function batchRetryEpisodes() {
  if (!episodeSelectedIds.value.length) return;
  await ElMessageBox.confirm(`确定批量重试 ${episodeSelectedIds.value.length} 条单集吗？`, "提示", { type: "warning" });
  await api.post("/podcast-episodes/batch-retry", { ids: episodeSelectedIds.value });
  ElMessage.success("批量重试成功");
  await loadEpisodes();
}

async function batchMarkPending() {
  if (!episodeSelectedIds.value.length) return;
  await ElMessageBox.confirm(`确定批量标记 ${episodeSelectedIds.value.length} 条单集为待处理吗？`, "提示", { type: "warning" });
  await api.patch("/podcast-episodes/batch-status", {
    ids: episodeSelectedIds.value,
    status: "pending",
  });
  ElMessage.success("批量更新成功");
  await loadEpisodes();
}

async function openEpisodeDetail(row: PodcastEpisodeItem) {
  activeEpisode.value = row;
  episodeDetailVisible.value = true;
  try {
    const detail = await api.get<PodcastEpisodeItem>(`/podcast-episodes/${row.id}`);
    activeEpisode.value = detail;
  } catch {
    // 保留列表项本地数据
  }
}

async function loadAll() {
  await Promise.all([loadSubscriptions(), loadEpisodes()]);
}

onMounted(loadAll);
</script>
