<template>
  <div class="dashboard podcast-page">
    <section class="page-hero">
      <div class="page-hero__copy">
        <div class="page-hero__eyebrow">WEWE RSS</div>
        <h1>公众号订阅</h1>
        <p class="page-hero__desc">
          同步 WeWe RSS 的公众号源列表，按 feedId 管理订阅，定时拉取后直接按全文推送到现有推送渠道，不生成 LLM 总结和文档。
        </p>
        <div class="page-hero__chips">
          <span class="page-hero__chip">订阅 {{ subscriptionTotal }}</span>
          <span class="page-hero__chip">文章 {{ articleTotal }}</span>
          <span class="page-hero__chip">源列表 {{ feedTotal }}</span>
        </div>
      </div>

      <div class="page-hero__panel">
        <div class="page-hero__panel-label">当前焦点</div>
        <div class="page-hero__panel-value">{{ activeTabLabel }}</div>
        <div class="page-hero__panel-note">
          默认使用 Atom 作为主消费格式；单源手动刷新时才会触发 update=true。
        </div>
      </div>
    </section>

    <el-tabs v-model="activeTab" type="card" class="page-tabs">
      <el-tab-pane label="公众号源列表" name="feeds">
        <el-card class="page-card section">
          <template #header>
            <div class="section-header">
              <div>
                <div class="section__title">公众号源列表</div>
                <div class="section__desc">从 WeWe RSS 的 /feeds/ 同步可订阅的公众号源，点击即可创建订阅。</div>
              </div>
              <el-space>
                <el-button :loading="loadingFeeds" @click="loadFeeds">同步列表</el-button>
                <el-button type="primary" @click="openSubscriptionDialog()">手动新增订阅</el-button>
              </el-space>
            </div>
          </template>

          <div class="toolbar">
            <el-input v-model="feedFilters.q" clearable placeholder="按 feedId / 标题搜索" style="width: 260px" />
            <el-button type="primary" :loading="loadingFeeds" @click="searchFeeds">查询</el-button>
            <el-button @click="resetFeedFilters">重置</el-button>
          </div>

          <el-table :data="feeds" stripe v-loading="loadingFeeds">
            <el-table-column prop="feed_id" label="Feed ID" width="220" />
            <el-table-column prop="title" label="公众号名称" min-width="220" />
            <el-table-column prop="homepage_url" label="首页" min-width="280">
              <template #default="{ row }">
                <el-link :href="row.homepage_url" target="_blank" type="primary" :underline="false">
                  {{ row.homepage_url }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column prop="atom_url" label="Atom" min-width="260">
              <template #default="{ row }">
                <el-link :href="row.atom_url" target="_blank" type="primary" :underline="false">
                  {{ row.atom_url }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column prop="rss_url" label="RSS" min-width="260">
              <template #default="{ row }">
                <el-link :href="row.rss_url" target="_blank" type="primary" :underline="false">
                  {{ row.rss_url }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column prop="json_url" label="JSON" min-width="260">
              <template #default="{ row }">
                <el-link :href="row.json_url" target="_blank" type="primary" :underline="false">
                  {{ row.json_url }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="openSubscriptionDialog(row)">订阅</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="订阅管理" name="subscriptions">
        <el-card class="page-card section">
          <template #header>
            <div class="section-header">
              <div>
                <div class="section__title">订阅管理</div>
                <div class="section__desc">为每个公众号源绑定推送组，未绑定时自动走默认飞书推送组。</div>
              </div>
              <el-space>
                <el-button type="primary" @click="openSubscriptionDialog()">新增订阅</el-button>
                <el-button type="warning" :disabled="!subscriptionSelectedIds.length" @click="batchUpdateSubscriptions(true)">
                  批量启用
                </el-button>
                <el-button type="info" :disabled="!subscriptionSelectedIds.length" @click="batchUpdateSubscriptions(false)">
                  批量停用
                </el-button>
                <el-button type="danger" :disabled="!subscriptionSelectedIds.length" @click="batchDeleteSubscriptions">
                  批量删除
                </el-button>
              </el-space>
            </div>
          </template>

          <div class="toolbar">
            <el-input v-model="subscriptionFilters.q" clearable placeholder="按 feedId / 名称搜索" style="width: 240px" />
            <el-select v-model="subscriptionFilters.push_target_filter" clearable placeholder="推送组" style="width: 220px">
              <el-option label="未绑定（默认组）" value="__unbound__" />
              <el-option v-for="target in pushTargets" :key="target.id" :label="renderPushTargetLabel(target)" :value="String(target.id)" />
            </el-select>
            <el-select v-model="subscriptionFilters.is_active" clearable placeholder="是否启用" style="width: 140px">
              <el-option label="启用" :value="true" />
              <el-option label="停用" :value="false" />
            </el-select>
            <el-button type="primary" :loading="loadingSubscriptions" @click="searchSubscriptions">查询</el-button>
            <el-button @click="resetSubscriptionFilters">重置</el-button>
          </div>

          <el-table :data="subscriptions" stripe v-loading="loadingSubscriptions" @selection-change="handleSubscriptionSelection">
            <el-table-column type="selection" width="48" />
            <el-table-column prop="feed_id" label="Feed ID" width="220" />
            <el-table-column prop="name" label="名称" width="220" />
            <el-table-column prop="homepage_url" label="首页" min-width="260">
              <template #default="{ row }">
                <el-link :href="resolveHomepageUrl(row)" target="_blank" type="primary" :underline="false">
                  {{ resolveHomepageUrl(row) }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column prop="feed_format" label="格式" width="100" />
            <el-table-column prop="push_target_name" label="推送组" width="220">
              <template #default="{ row }">
                <el-tag v-if="row.push_target_name" type="success">{{ row.push_target_name }}</el-tag>
                <el-tag v-else type="info">默认组</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="bootstrap_recent_items" label="首批" width="80" />
            <el-table-column prop="is_active" label="启用" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ translateBoolean(row.is_active) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_entry_id" label="最新文章" width="220" />
            <el-table-column prop="last_check_time" label="最近检查" width="180">
              <template #default="{ row }">{{ formatDateTime(row.last_check_time) }}</template>
            </el-table-column>
            <el-table-column prop="last_success_time" label="最近成功" width="180">
              <template #default="{ row }">{{ formatDateTime(row.last_success_time) }}</template>
            </el-table-column>
            <el-table-column prop="consecutive_failures" label="失败次数" width="90" />
            <el-table-column label="操作" width="260">
              <template #default="{ row }">
                <el-space wrap>
                  <el-button size="small" @click="openSubscriptionDialog(row)">编辑</el-button>
                  <el-button size="small" type="primary" @click="refreshSubscription(row)">手动刷新</el-button>
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

      <el-tab-pane label="文章管理" name="articles">
        <el-card class="page-card section">
          <template #header>
            <div class="section-header">
              <div>
                <div class="section__title">文章管理</div>
                <div class="section__desc">WeWe RSS 抓取到的文章会在这里入库、去重、推送和重试。</div>
              </div>
              <el-space>
                <el-button type="warning" :disabled="!articleSelectedIds.length" @click="batchRetryArticles">批量重试</el-button>
                <el-button type="info" :disabled="!articleSelectedIds.length" @click="batchMarkPending">批量待处理</el-button>
              </el-space>
            </div>
          </template>

          <div class="toolbar">
            <el-input v-model="articleFilters.q" clearable placeholder="按标题 / Entry ID 搜索" style="width: 240px" />
            <el-select v-model="articleFilters.feed_id" clearable filterable placeholder="公众号" style="width: 240px">
              <el-option v-for="sub in subscriptions" :key="sub.id" :label="`${sub.name} (${sub.feed_id})`" :value="sub.feed_id" />
            </el-select>
            <el-select v-model="articleFilters.status" clearable placeholder="处理状态" style="width: 140px">
              <el-option label="待处理" value="pending" />
              <el-option label="处理中" value="processing" />
              <el-option label="已发送" value="sent" />
              <el-option label="失败" value="failed" />
              <el-option label="跳过" value="skipped" />
            </el-select>
            <el-select v-model="articleFilters.push_status" clearable placeholder="推送状态" style="width: 140px">
              <el-option label="待处理" value="pending" />
              <el-option label="处理中" value="processing" />
              <el-option label="成功" value="success" />
              <el-option label="失败" value="failed" />
              <el-option label="跳过" value="skipped" />
            </el-select>
            <el-button type="primary" :loading="loadingArticles" @click="searchArticles">查询</el-button>
            <el-button @click="resetArticlesFilters">重置</el-button>
          </div>

          <el-table :data="articles" stripe v-loading="loadingArticles" @selection-change="handleArticleSelection">
            <el-table-column type="selection" width="48" />
            <el-table-column prop="title" label="标题" min-width="280">
              <template #default="{ row }">
                <div>
                  <div class="task-title-cell">
                    <el-link :href="row.link" target="_blank" type="primary" :underline="false">
                      {{ row.title }}
                    </el-link>
                  </div>
                  <div class="muted">{{ row.entry_id }}</div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="feed_name" label="公众号" width="200" />
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
                  <el-button size="small" @click="openArticleDetail(row)">详情</el-button>
                  <el-button size="small" type="warning" @click="retryArticle(row)">重试</el-button>
                </el-space>
              </template>
            </el-table-column>
          </el-table>

          <div class="toolbar" style="justify-content: flex-end; margin-top: 16px">
            <el-pagination
              layout="prev, pager, next, total, sizes"
              :current-page="articleFilters.page"
              :page-size="articleFilters.page_size"
              :page-sizes="[10, 20, 50, 100]"
              :total="articleTotal"
              @current-change="changeArticlePage"
              @size-change="changeArticlePageSize"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="subscriptionDialogVisible" :title="subscriptionForm.id ? '编辑订阅' : '新增订阅'" width="680px">
      <el-form label-width="120px">
        <el-form-item label="Feed ID">
          <el-input v-model="subscriptionForm.feed_id" :disabled="!!subscriptionForm.id" placeholder="MP_WXS_123" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="subscriptionForm.name" />
        </el-form-item>
        <el-form-item label="首页">
          <el-input v-model="subscriptionForm.homepage_url" placeholder="https://wewe-rss-host:4000/feeds/xxx" />
        </el-form-item>
        <el-form-item label="格式">
          <el-select v-model="subscriptionForm.feed_format" style="width: 100%">
            <el-option label="Atom" value="atom" />
            <el-option label="RSS" value="rss" />
            <el-option label="JSON" value="json" />
          </el-select>
        </el-form-item>
        <el-form-item label="推送组">
          <el-select v-model="subscriptionForm.push_target_id" clearable placeholder="不绑定则走默认组" style="width: 100%">
            <el-option label="默认组" :value="0" />
            <el-option v-for="target in activePushTargets" :key="target.id" :label="renderPushTargetLabel(target)" :value="target.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="首批条数">
          <el-input-number v-model="subscriptionForm.bootstrap_recent_items" :min="0" :max="20" />
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
        <el-button type="primary" :loading="savingSubscription" @click="saveSubscription">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="articleDetailVisible" title="文章详情" size="52%">
      <template v-if="activeArticle">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="标题">{{ activeArticle.title }}</el-descriptions-item>
          <el-descriptions-item label="公众号">{{ activeArticle.feed_name || "-" }}</el-descriptions-item>
          <el-descriptions-item label="Entry ID">{{ activeArticle.entry_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusText(activeArticle.status) }}</el-descriptions-item>
          <el-descriptions-item label="推送状态">{{ statusText(activeArticle.push_status) }}</el-descriptions-item>
          <el-descriptions-item label="发布时间">{{ formatDateTime(activeArticle.pub_time) }}</el-descriptions-item>
          <el-descriptions-item label="链接">
            <el-link :href="activeArticle.link" target="_blank" type="primary">{{ activeArticle.link }}</el-link>
          </el-descriptions-item>
          <el-descriptions-item label="正文">
            <pre class="summary-box">{{ activeArticle.content_text || "-" }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="原始数据">
            <pre class="summary-box">{{ prettyJson(activeArticle.raw_entry_json) }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="错误信息">
            <pre class="summary-box">{{ activeArticle.last_error || "-" }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { api } from "../api";
import type { PageResult, PushTargetItem, WeWeRssArticleItem, WeWeRssFeedItem, WeWeRssSubscriptionItem } from "../types";
import { buildQuery, formatDateTime, prettyJson, translateBoolean } from "../utils";

const activeTab = ref("feeds");
const loadingFeeds = ref(false);
const loadingSubscriptions = ref(false);
const loadingArticles = ref(false);
const savingSubscription = ref(false);

const feeds = ref<WeWeRssFeedItem[]>([]);
const feedTotal = ref(0);
const subscriptions = ref<WeWeRssSubscriptionItem[]>([]);
const subscriptionTotal = ref(0);
const articles = ref<WeWeRssArticleItem[]>([]);
const articleTotal = ref(0);
const pushTargets = ref<PushTargetItem[]>([]);

const subscriptionSelectedIds = ref<number[]>([]);
const articleSelectedIds = ref<number[]>([]);

const subscriptionDialogVisible = ref(false);
const articleDetailVisible = ref(false);
const activeArticle = ref<WeWeRssArticleItem | null>(null);

const feedFilters = reactive({
  q: "",
});

const subscriptionFilters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  is_active: undefined as boolean | undefined,
  push_target_filter: "",
});

const articleFilters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  feed_id: "",
  status: "",
  push_status: "",
});

const subscriptionForm = reactive({
  id: null as number | null,
  feed_id: "",
  name: "",
  homepage_url: "",
  feed_format: "atom",
  push_target_id: 0 as number | null,
  notes: "",
  bootstrap_recent_items: 3,
  is_active: true,
});

const activePushTargets = computed(() => pushTargets.value.filter((item) => item.is_active));

const activeTabLabel = computed(() => {
  if (activeTab.value === "subscriptions") return "订阅管理";
  if (activeTab.value === "articles") return "文章管理";
  return "公众号源列表";
});

function renderPushTargetLabel(target: PushTargetItem) {
  return target.is_default ? `${target.name}（默认）` : target.name;
}

function resolveHomepageUrl(row: WeWeRssSubscriptionItem) {
  return row.homepage_url || "";
}

function resetSubscriptionForm() {
  subscriptionForm.id = null;
  subscriptionForm.feed_id = "";
  subscriptionForm.name = "";
  subscriptionForm.homepage_url = "";
  subscriptionForm.feed_format = "atom";
  subscriptionForm.push_target_id = 0;
  subscriptionForm.notes = "";
  subscriptionForm.bootstrap_recent_items = 3;
  subscriptionForm.is_active = true;
}

function openSubscriptionDialog(feed?: WeWeRssFeedItem | WeWeRssSubscriptionItem) {
  if (feed && "feed_id" in feed) {
    subscriptionForm.id = "id" in feed ? feed.id : null;
    subscriptionForm.feed_id = feed.feed_id;
    subscriptionForm.name = "title" in feed ? feed.title || "" : feed.name || "";
    subscriptionForm.homepage_url = feed.homepage_url || "";
    subscriptionForm.feed_format = "feed_format" in feed && feed.feed_format ? feed.feed_format : "atom";
    subscriptionForm.push_target_id = "push_target_id" in feed ? feed.push_target_id ?? 0 : 0;
    subscriptionForm.notes = "notes" in feed ? feed.notes || "" : "";
    subscriptionForm.bootstrap_recent_items = "bootstrap_recent_items" in feed ? feed.bootstrap_recent_items || 3 : 3;
    subscriptionForm.is_active = "is_active" in feed ? feed.is_active : true;
  } else {
    resetSubscriptionForm();
  }
  activeTab.value = "subscriptions";
  subscriptionDialogVisible.value = true;
}

function statusText(value?: string | null): string {
  if (!value) return "-";
  const labels: Record<string, string> = {
    pending: "待处理",
    processing: "处理中",
    sent: "已发送",
    failed: "失败",
    skipped: "跳过",
    filtered: "已过滤",
    success: "成功",
    done: "已完成",
  };
  return labels[value] || value;
}

function statusTagType(status?: string | null): "danger" | "warning" | "info" | "success" {
  if (status === "failed") return "danger";
  if (status === "processing") return "warning";
  if (status === "pending") return "info";
  if (status === "sent" || status === "success" || status === "done") return "success";
  if (status === "skipped" || status === "filtered") return "warning";
  return "info";
}

async function loadPushTargets() {
  const data = await api.get<PageResult<PushTargetItem>>("/push-targets?page=1&page_size=200");
  pushTargets.value = data.items || [];
}

async function loadFeeds() {
  loadingFeeds.value = true;
  try {
    const data = await api.get<{ total: number; items: WeWeRssFeedItem[] }>(`/wewe-rss/feeds${buildQuery(feedFilters)}`);
    feeds.value = data.items || [];
    feedTotal.value = data.total || (data.items?.length ?? 0);
  } catch (error: any) {
    feeds.value = [];
    feedTotal.value = 0;
    ElMessage.warning(error?.message || "同步公众号源失败");
  } finally {
    loadingFeeds.value = false;
  }
}

async function loadSubscriptions() {
  loadingSubscriptions.value = true;
  try {
    const query: Record<string, string | number | boolean> = {
      page: subscriptionFilters.page,
      page_size: subscriptionFilters.page_size,
    };
    if (subscriptionFilters.q) query.q = subscriptionFilters.q;
    if (subscriptionFilters.is_active !== undefined) query.is_active = subscriptionFilters.is_active;
    if (subscriptionFilters.push_target_filter === "__unbound__") {
      query.unbound = true;
    } else if (subscriptionFilters.push_target_filter) {
      query.push_target_id = Number(subscriptionFilters.push_target_filter);
    }
    const data = await api.get<PageResult<WeWeRssSubscriptionItem>>(`/wewe-rss-subscriptions${buildQuery(query)}`);
    subscriptions.value = data.items || [];
    subscriptionTotal.value = data.total || 0;
    subscriptionSelectedIds.value = [];
  } catch (error: any) {
    subscriptions.value = [];
    subscriptionTotal.value = 0;
    ElMessage.error(error?.message || "加载订阅失败");
  } finally {
    loadingSubscriptions.value = false;
  }
}

async function loadArticles() {
  loadingArticles.value = true;
  try {
    const query: Record<string, string | number | boolean> = {
      page: articleFilters.page,
      page_size: articleFilters.page_size,
    };
    if (articleFilters.q) query.q = articleFilters.q;
    if (articleFilters.feed_id) query.feed_id = articleFilters.feed_id;
    if (articleFilters.status) query.status = articleFilters.status;
    if (articleFilters.push_status) query.push_status = articleFilters.push_status;
    const data = await api.get<PageResult<WeWeRssArticleItem>>(`/wewe-rss-articles${buildQuery(query)}`);
    articles.value = data.items || [];
    articleTotal.value = data.total || 0;
    articleSelectedIds.value = [];
  } catch (error: any) {
    articles.value = [];
    articleTotal.value = 0;
    ElMessage.error(error?.message || "加载文章失败");
  } finally {
    loadingArticles.value = false;
  }
}

async function reloadFeeds() {
  await loadFeeds();
  ElMessage.success("源列表已同步");
}

function searchFeeds() {
  loadFeeds();
}

function resetFeedFilters() {
  feedFilters.q = "";
  loadFeeds();
}

async function saveSubscription() {
  savingSubscription.value = true;
  try {
    const payload = {
      feed_id: subscriptionForm.feed_id,
      name: subscriptionForm.name,
      homepage_url: subscriptionForm.homepage_url || null,
      feed_format: subscriptionForm.feed_format,
      push_target_id: subscriptionForm.push_target_id || null,
      notes: subscriptionForm.notes || null,
      bootstrap_recent_items: subscriptionForm.bootstrap_recent_items,
      is_active: subscriptionForm.is_active,
    };
    if (subscriptionForm.id) {
      await api.put(`/wewe-rss-subscriptions/${subscriptionForm.id}`, payload);
    } else {
      await api.post("/wewe-rss-subscriptions", payload);
    }
    ElMessage.success("保存成功");
    subscriptionDialogVisible.value = false;
    await loadSubscriptions();
  } finally {
    savingSubscription.value = false;
  }
}

async function deleteSubscription(row: WeWeRssSubscriptionItem) {
  await ElMessageBox.confirm(`确认删除订阅 ${row.name}？`, "提示", { type: "warning" });
  await api.delete(`/wewe-rss-subscriptions/${row.id}`);
  ElMessage.success("删除成功");
  await loadSubscriptions();
}

function searchSubscriptions() {
  subscriptionFilters.page = 1;
  loadSubscriptions();
}

function resetSubscriptionFilters() {
  subscriptionFilters.page = 1;
  subscriptionFilters.q = "";
  subscriptionFilters.is_active = undefined;
  subscriptionFilters.push_target_filter = "";
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

function handleSubscriptionSelection(selection: WeWeRssSubscriptionItem[]) {
  subscriptionSelectedIds.value = selection.map((row) => row.id);
}

async function batchUpdateSubscriptions(isActive: boolean) {
  if (!subscriptionSelectedIds.value.length) return;
  await ElMessageBox.confirm(
    `确认批量${isActive ? "启用" : "停用"} ${subscriptionSelectedIds.value.length} 个订阅？`,
    "提示",
    { type: "warning" },
  );
  await api.patch("/wewe-rss-subscriptions/batch-active", {
    ids: subscriptionSelectedIds.value,
    is_active: isActive,
  });
  ElMessage.success("操作成功");
  await loadSubscriptions();
}

async function batchDeleteSubscriptions() {
  if (!subscriptionSelectedIds.value.length) return;
  await ElMessageBox.confirm(`确认批量删除 ${subscriptionSelectedIds.value.length} 个订阅？`, "提示", {
    type: "warning",
  });
  await api.post("/wewe-rss-subscriptions/batch-delete", { ids: subscriptionSelectedIds.value });
  ElMessage.success("删除成功");
  await loadSubscriptions();
}

async function refreshSubscription(row: WeWeRssSubscriptionItem) {
  await api.post(`/wewe-rss-subscriptions/${row.id}/refresh`, {});
  ElMessage.success("刷新任务已执行");
  await loadSubscriptions();
  await loadArticles();
}

function searchArticles() {
  articleFilters.page = 1;
  loadArticles();
}

function resetArticlesFilters() {
  articleFilters.page = 1;
  articleFilters.q = "";
  articleFilters.feed_id = "";
  articleFilters.status = "";
  articleFilters.push_status = "";
  loadArticles();
}

function changeArticlePage(page: number) {
  articleFilters.page = page;
  loadArticles();
}

function changeArticlePageSize(size: number) {
  articleFilters.page_size = size;
  articleFilters.page = 1;
  loadArticles();
}

function handleArticleSelection(selection: WeWeRssArticleItem[]) {
  articleSelectedIds.value = selection.map((row) => row.id);
}

async function retryArticle(row: WeWeRssArticleItem) {
  await api.post(`/wewe-rss-articles/${row.id}/retry`, {});
  ElMessage.success("已重试");
  await loadArticles();
}

async function batchRetryArticles() {
  if (!articleSelectedIds.value.length) return;
  await ElMessageBox.confirm(`确认批量重试 ${articleSelectedIds.value.length} 篇文章？`, "提示", {
    type: "warning",
  });
  await api.post("/wewe-rss-articles/batch-retry", { ids: articleSelectedIds.value });
  ElMessage.success("批量重试成功");
  await loadArticles();
}

async function batchMarkPending() {
  if (!articleSelectedIds.value.length) return;
  await ElMessageBox.confirm(`确认批量标记 ${articleSelectedIds.value.length} 篇文章为待处理？`, "提示", {
    type: "warning",
  });
  await api.patch("/wewe-rss-articles/batch-status", {
    ids: articleSelectedIds.value,
    status: "pending",
  });
  ElMessage.success("更新成功");
  await loadArticles();
}

async function openArticleDetail(row: WeWeRssArticleItem) {
  activeArticle.value = row;
  articleDetailVisible.value = true;
  try {
    activeArticle.value = await api.get<WeWeRssArticleItem>(`/wewe-rss-articles/${row.id}`);
  } catch {
    // keep current row
  }
}

async function loadAll() {
  await loadPushTargets();
  await Promise.all([loadFeeds(), loadSubscriptions(), loadArticles()]);
}

onMounted(loadAll);
</script>
