<template>
  <div class="dashboard config-page">
    <section class="page-hero">
      <div class="page-hero__copy">
        <div class="page-hero__eyebrow">CONFIG CENTER</div>
        <h1>业务配置</h1>
        <p class="page-hero__desc">
          把订阅、规则和文件夹映射放在同一处管理，适合做日常运营、批量调整和快速排障。
        </p>
        <div class="page-hero__chips">
          <span class="page-hero__chip">订阅 {{ subscriptionTotal }}</span>
          <span class="page-hero__chip">规则 {{ ruleTotal }}</span>
          <span class="page-hero__chip">映射 {{ folderTotal }}</span>
        </div>
      </div>

      <div class="page-hero__panel">
        <div class="page-hero__panel-label">当前页签</div>
        <div class="page-hero__panel-value">{{ activeTabMeta.label }}</div>
        <div class="page-hero__panel-note">{{ activeTabMeta.desc }}</div>
        <div class="page-hero__stats">
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">订阅</div>
            <div class="page-hero__stat-value">{{ subscriptionTotal }}</div>
          </div>
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">规则</div>
            <div class="page-hero__stat-value">{{ ruleTotal }}</div>
          </div>
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">映射</div>
            <div class="page-hero__stat-value">{{ folderTotal }}</div>
          </div>
        </div>
      </div>
    </section>

    <el-tabs v-model="activeTab" type="card" class="page-tabs">
      <el-tab-pane label="B站UP主" name="subscriptions">
        <el-card class="page-card section">
          <template #header>
            <div class="section__title">B站UP主</div>
          </template>

          <div class="toolbar">
            <el-input v-model="subscriptionFilters.q" clearable placeholder="按 UP 主 ID / 名称搜索" style="width: 240px" />
            <el-select v-model="subscriptionFilters.is_active" clearable placeholder="是否启用" style="width: 140px">
              <el-option label="启用" :value="true" />
              <el-option label="停用" :value="false" />
            </el-select>
            <el-button type="primary" @click="searchSubscriptions">查询</el-button>
            <el-button @click="resetSubscriptionFilters">重置</el-button>
            <el-button type="success" @click="openSubscriptionDialog()">新增订阅</el-button>
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
            <el-table-column prop="mid" label="UP 主ID" width="180" />
            <el-table-column prop="name" label="名称" width="180" />
            <el-table-column prop="homepage_url" label="主页" min-width="280">
              <template #default="{ row }">
                <el-link :href="resolveHomepageUrl(row)" target="_blank" type="primary" :underline="false">
                  {{ resolveHomepageUrl(row) }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="启用" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ translateBoolean(row.is_active) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="notes" label="备注" min-width="220" />
            <el-table-column prop="last_video_bvid" label="最后视频编号" width="180" />
            <el-table-column prop="last_dynamic_id" label="最后动态编号" width="180" />
            <el-table-column prop="last_check_time" label="最后检查" width="180">
              <template #default="{ row }">{{ formatDateTime(row.last_check_time) }}</template>
            </el-table-column>
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

      <el-tab-pane label="规则管理" name="rules">
        <el-card class="page-card section">
          <template #header>
            <div class="section__title">规则管理</div>
          </template>

          <div class="toolbar">
            <el-input v-model="ruleFilters.q" clearable placeholder="按规则 / 文件夹搜索" style="width: 240px" />
            <el-select v-model="ruleFilters.is_active" clearable placeholder="是否启用" style="width: 140px">
              <el-option label="启用" :value="true" />
              <el-option label="停用" :value="false" />
            </el-select>
            <el-button type="primary" @click="searchRules">查询</el-button>
            <el-button @click="resetRuleFilters">重置</el-button>
            <el-button type="success" @click="openRuleDialog()">新增规则</el-button>
            <el-button type="warning" :disabled="!ruleSelectedIds.length" @click="batchUpdateRules(true)">批量启用</el-button>
            <el-button type="info" :disabled="!ruleSelectedIds.length" @click="batchUpdateRules(false)">批量停用</el-button>
            <el-button type="danger" :disabled="!ruleSelectedIds.length" @click="batchDeleteRules">批量删除</el-button>
          </div>

          <el-table :data="rules" stripe v-loading="loadingRules" @selection-change="handleRuleSelection">
            <el-table-column type="selection" width="48" />
            <el-table-column prop="uploader_name" label="作者" width="180" />
            <el-table-column prop="pattern" label="规则" min-width="220" />
            <el-table-column prop="target_folder" label="目标文件夹" min-width="220" />
            <el-table-column prop="priority" label="优先级" width="100" />
            <el-table-column prop="is_active" label="启用" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ translateBoolean(row.is_active) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-space>
                  <el-button size="small" @click="openRuleDialog(row)">编辑</el-button>
                  <el-button size="small" type="danger" @click="deleteRule(row)">删除</el-button>
                </el-space>
              </template>
            </el-table-column>
          </el-table>

          <div class="toolbar" style="justify-content: flex-end; margin-top: 16px">
            <el-pagination
              layout="prev, pager, next, total, sizes"
              :current-page="ruleFilters.page"
              :page-size="ruleFilters.page_size"
              :page-sizes="[10, 20, 50, 100]"
              :total="ruleTotal"
              @current-change="changeRulePage"
              @size-change="changeRulePageSize"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="文件夹映射" name="folders">
        <el-card class="page-card section">
          <template #header>
            <div class="section__title">文件夹映射</div>
          </template>

          <div class="toolbar">
            <el-input v-model="folderFilters.q" clearable placeholder="按路径 / 令牌搜索" style="width: 240px" />
            <el-button type="primary" @click="searchFolderMappings">查询</el-button>
            <el-button @click="resetFolderFilters">重置</el-button>
            <el-button type="danger" :disabled="!folderSelectedIds.length" @click="batchDeleteFolderMappings">
              批量删除
            </el-button>
          </div>

          <el-table :data="folderMappings" stripe v-loading="loadingFolders" @selection-change="handleFolderSelection">
            <el-table-column type="selection" width="48" />
            <el-table-column prop="uploader_name" label="作者" width="180" />
            <el-table-column prop="category" label="分类" width="180" />
            <el-table-column prop="folder_path" label="文件夹路径" min-width="240" />
            <el-table-column prop="folder_token" label="文件夹令牌" min-width="260" />
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button size="small" type="danger" @click="deleteFolderMapping(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="toolbar" style="justify-content: flex-end; margin-top: 16px">
            <el-pagination
              layout="prev, pager, next, total, sizes"
              :current-page="folderFilters.page"
              :page-size="folderFilters.page_size"
              :page-sizes="[10, 20, 50, 100]"
              :total="folderTotal"
              @current-change="changeFolderPage"
              @size-change="changeFolderPageSize"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="subscriptionDialogVisible" :title="subscriptionForm.id ? '编辑订阅' : '新增订阅'" width="560px">
      <el-form label-width="120px">
        <el-form-item label="UP 主ID">
          <el-input v-model="subscriptionForm.mid" :disabled="!!subscriptionForm.id" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="subscriptionForm.name" />
        </el-form-item>
        <el-form-item label="主页">
          <el-input v-model="subscriptionForm.homepage_url" placeholder="https://space.bilibili.com/123456" />
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

    <el-dialog v-model="ruleDialogVisible" :title="ruleForm.id ? '编辑规则' : '新增规则'" width="640px">
      <el-form label-width="120px">
        <el-form-item label="作者">
          <el-input v-model="ruleForm.uploader_name" />
        </el-form-item>
        <el-form-item label="规则">
          <el-input v-model="ruleForm.pattern" />
        </el-form-item>
        <el-form-item label="目标文件夹">
          <el-input v-model="ruleForm.target_folder" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="ruleForm.priority" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="ruleForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { api } from "../api";
import type { FolderMappingItem, PageResult, RuleItem, SubscriptionItem } from "../types";
import { formatDateTime, translateBoolean } from "../utils";

const props = withDefaults(
  defineProps<{
    initialTab?: "subscriptions" | "rules" | "folders";
  }>(),
  {
    initialTab: "subscriptions",
  },
);

const activeTab = ref(props.initialTab);
const subscriptions = ref<SubscriptionItem[]>([]);
const subscriptionTotal = ref(0);
const rules = ref<RuleItem[]>([]);
const ruleTotal = ref(0);
const folderMappings = ref<FolderMappingItem[]>([]);
const folderTotal = ref(0);

const activeTabMeta = computed(() => {
  if (activeTab.value === "subscriptions") {
    return {
      label: "订阅管理",
      desc: "按 UP 主维度管理订阅，支持批量启停、编辑和导入导出。",
    };
  }

  if (activeTab.value === "rules") {
    return {
      label: "规则管理",
      desc: "按优先级匹配规则，支持批量启停、上下调整和导入导出。",
    };
  }

  return {
    label: "文件夹映射",
    desc: "管理作者、分类、文件夹 token 与路径之间的映射关系。",
  };
});

const subscriptionDialogVisible = ref(false);
const ruleDialogVisible = ref(false);
const loadingSubscriptions = ref(false);
const loadingRules = ref(false);
const loadingFolders = ref(false);

const subscriptionSelectedIds = ref<number[]>([]);
const ruleSelectedIds = ref<number[]>([]);
const folderSelectedIds = ref<number[]>([]);

const subscriptionForm = reactive({
  id: null as number | null,
  mid: "",
  name: "",
  homepage_url: "",
  notes: "",
  is_active: true,
});

const subscriptionFilters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  is_active: undefined as boolean | undefined,
});

const ruleFilters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  is_active: undefined as boolean | undefined,
});

const folderFilters = reactive({
  page: 1,
  page_size: 20,
  q: "",
});

const ruleForm = reactive({
  id: null as number | null,
  uploader_name: "",
  pattern: "",
  target_folder: "",
  priority: 100,
  is_active: true,
});

function resetSubscriptionForm() {
  subscriptionForm.id = null;
  subscriptionForm.mid = "";
  subscriptionForm.name = "";
  subscriptionForm.homepage_url = "";
  subscriptionForm.notes = "";
  subscriptionForm.is_active = true;
}

function openSubscriptionDialog(row?: SubscriptionItem) {
  if (row) {
    subscriptionForm.id = row.id;
    subscriptionForm.mid = row.mid;
    subscriptionForm.name = row.name;
    subscriptionForm.homepage_url = row.homepage_url || `https://space.bilibili.com/${row.mid}`;
    subscriptionForm.notes = row.notes || "";
    subscriptionForm.is_active = row.is_active;
  } else {
    resetSubscriptionForm();
  }
  subscriptionDialogVisible.value = true;
}

async function saveSubscription() {
  const payload = {
    mid: subscriptionForm.mid,
    name: subscriptionForm.name,
    homepage_url: subscriptionForm.homepage_url || null,
    notes: subscriptionForm.notes || null,
    is_active: subscriptionForm.is_active,
  };
  if (subscriptionForm.id) {
    await api.put(`/subscriptions/${subscriptionForm.id}`, payload);
  } else {
    await api.post("/subscriptions", payload);
  }
  subscriptionDialogVisible.value = false;
  ElMessage.success("保存成功");
  await loadSubscriptions();
}

function resolveHomepageUrl(row?: SubscriptionItem | null) {
  if (!row) return "";
  return row.homepage_url || `https://space.bilibili.com/${row.mid}`;
}

async function deleteSubscription(row: SubscriptionItem) {
  await ElMessageBox.confirm(`确认删除订阅 ${row.name}？`, "提示", { type: "warning" });
  await api.delete(`/subscriptions/${row.id}`);
  ElMessage.success("删除成功");
  await loadSubscriptions();
}

function resetRuleForm() {
  ruleForm.id = null;
  ruleForm.uploader_name = "";
  ruleForm.pattern = "";
  ruleForm.target_folder = "";
  ruleForm.priority = 100;
  ruleForm.is_active = true;
}

function openRuleDialog(row?: RuleItem) {
  if (row) {
    ruleForm.id = row.id;
    ruleForm.uploader_name = row.uploader_name;
    ruleForm.pattern = row.pattern;
    ruleForm.target_folder = row.target_folder;
    ruleForm.priority = row.priority;
    ruleForm.is_active = row.is_active;
  } else {
    resetRuleForm();
  }
  ruleDialogVisible.value = true;
}

async function saveRule() {
  const payload = {
    uploader_name: ruleForm.uploader_name,
    pattern: ruleForm.pattern,
    target_folder: ruleForm.target_folder,
    priority: ruleForm.priority,
    is_active: ruleForm.is_active,
  };
  if (ruleForm.id) {
    await api.put(`/classification-rules/${ruleForm.id}`, payload);
  } else {
    await api.post("/classification-rules", payload);
  }
  ruleDialogVisible.value = false;
  ElMessage.success("保存成功");
  await loadRules();
}

async function deleteRule(row: RuleItem) {
  await ElMessageBox.confirm(`确认删除规则 ${row.pattern}？`, "提示", { type: "warning" });
  await api.delete(`/classification-rules/${row.id}`);
  ElMessage.success("删除成功");
  await loadRules();
}

async function deleteFolderMapping(row: FolderMappingItem) {
  await ElMessageBox.confirm(`确认删除文件夹映射 ${row.folder_path}？`, "提示", { type: "warning" });
  await api.delete(`/folder-mappings/${row.id}`);
  ElMessage.success("删除成功");
  await loadFolderMappings();
}

function buildListQuery(params: Record<string, string | number | boolean | undefined>) {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === "") return;
    searchParams.set(key, String(value));
  });
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

async function loadSubscriptions() {
  loadingSubscriptions.value = true;
  try {
    const data = await api.get<PageResult<SubscriptionItem>>(
      `/subscriptions${buildListQuery(subscriptionFilters as Record<string, string | number | boolean | undefined>)}`
    );
    subscriptions.value = data.items;
    subscriptionTotal.value = data.total;
    subscriptionSelectedIds.value = [];
  } finally {
    loadingSubscriptions.value = false;
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

async function loadRules() {
  loadingRules.value = true;
  try {
    const data = await api.get<PageResult<RuleItem>>(
      `/classification-rules${buildListQuery(ruleFilters as Record<string, string | number | boolean | undefined>)}`
    );
    rules.value = data.items;
    ruleTotal.value = data.total;
    ruleSelectedIds.value = [];
  } finally {
    loadingRules.value = false;
  }
}

function searchRules() {
  ruleFilters.page = 1;
  loadRules();
}

function resetRuleFilters() {
  ruleFilters.page = 1;
  ruleFilters.q = "";
  ruleFilters.is_active = undefined;
  loadRules();
}

async function loadFolderMappings() {
  loadingFolders.value = true;
  try {
    const data = await api.get<PageResult<FolderMappingItem>>(
      `/folder-mappings${buildListQuery(folderFilters as Record<string, string | number | boolean | undefined>)}`
    );
    folderMappings.value = data.items;
    folderTotal.value = data.total;
    folderSelectedIds.value = [];
  } finally {
    loadingFolders.value = false;
  }
}

function searchFolderMappings() {
  folderFilters.page = 1;
  loadFolderMappings();
}

function resetFolderFilters() {
  folderFilters.page = 1;
  folderFilters.q = "";
  loadFolderMappings();
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

function changeRulePage(page: number) {
  ruleFilters.page = page;
  loadRules();
}

function changeRulePageSize(size: number) {
  ruleFilters.page_size = size;
  ruleFilters.page = 1;
  loadRules();
}

function changeFolderPage(page: number) {
  folderFilters.page = page;
  loadFolderMappings();
}

function changeFolderPageSize(size: number) {
  folderFilters.page_size = size;
  folderFilters.page = 1;
  loadFolderMappings();
}

function handleSubscriptionSelection(selection: SubscriptionItem[]) {
  subscriptionSelectedIds.value = selection.map((row) => row.id);
}

function handleRuleSelection(selection: RuleItem[]) {
  ruleSelectedIds.value = selection.map((row) => row.id);
}

function handleFolderSelection(selection: FolderMappingItem[]) {
  folderSelectedIds.value = selection.map((row) => row.id);
}

async function batchUpdateSubscriptions(isActive: boolean) {
  if (!subscriptionSelectedIds.value.length) return;
  const actionText = isActive ? "启用" : "停用";
  await ElMessageBox.confirm(
    `确定批量${actionText} ${subscriptionSelectedIds.value.length} 条订阅吗？`,
    "提示",
    { type: "warning" }
  );
  await api.patch("/subscriptions/batch-active", { ids: subscriptionSelectedIds.value, is_active: isActive });
  ElMessage.success(`批量${actionText}成功`);
  await loadSubscriptions();
}

async function batchDeleteSubscriptions() {
  if (!subscriptionSelectedIds.value.length) return;
  await ElMessageBox.confirm(
    `确定批量删除 ${subscriptionSelectedIds.value.length} 条订阅吗？`,
    "提示",
    { type: "warning" }
  );
  await api.post("/subscriptions/batch-delete", { ids: subscriptionSelectedIds.value });
  ElMessage.success("批量删除成功");
  await loadSubscriptions();
}

async function batchUpdateRules(isActive: boolean) {
  if (!ruleSelectedIds.value.length) return;
  const actionText = isActive ? "启用" : "停用";
  await ElMessageBox.confirm(
    `确定批量${actionText} ${ruleSelectedIds.value.length} 条规则吗？`,
    "提示",
    { type: "warning" }
  );
  await api.patch("/classification-rules/batch-active", { ids: ruleSelectedIds.value, is_active: isActive });
  ElMessage.success(`批量${actionText}成功`);
  await loadRules();
}

async function batchDeleteRules() {
  if (!ruleSelectedIds.value.length) return;
  await ElMessageBox.confirm(
    `确定批量删除 ${ruleSelectedIds.value.length} 条规则吗？`,
    "提示",
    { type: "warning" }
  );
  await api.post("/classification-rules/batch-delete", { ids: ruleSelectedIds.value });
  ElMessage.success("批量删除成功");
  await loadRules();
}

async function batchDeleteFolderMappings() {
  if (!folderSelectedIds.value.length) return;
  await ElMessageBox.confirm(
    `确定批量删除 ${folderSelectedIds.value.length} 条文件夹映射吗？`,
    "提示",
    { type: "warning" }
  );
  await api.post("/folder-mappings/batch-delete", { ids: folderSelectedIds.value });
  ElMessage.success("批量删除成功");
  await loadFolderMappings();
}

async function loadAll() {
  await Promise.all([loadSubscriptions(), loadRules(), loadFolderMappings()]);
}

onMounted(loadAll);
</script>
