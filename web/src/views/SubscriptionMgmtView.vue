<template>
  <div class="dashboard">
    <section class="page-hero">
      <div class="page-hero__copy">
        <div class="page-hero__eyebrow">SUBSCRIPTIONS</div>
        <h1>B站 UP 主订阅</h1>
        <p class="page-hero__desc">
          管理 B 站主播订阅，并为每个订阅绑定独立的飞书推送组。未绑定时自动走默认组。
        </p>
        <div class="page-hero__chips">
          <span class="page-hero__chip">订阅总数 {{ total }}</span>
          <span class="page-hero__chip">已选 {{ selectedIds.length }}</span>
          <span class="page-hero__chip">推送组 {{ pushTargets.length }}</span>
        </div>
      </div>

      <div class="page-hero__panel">
        <div class="page-hero__panel-label">当前焦点</div>
        <div class="page-hero__panel-value">订阅 + 推送路由</div>
        <div class="page-hero__panel-note">
          订阅可以绑定单独飞书群。未绑定时会落到显式默认组，不再依赖列表顺序。
        </div>
      </div>
    </section>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">订阅列表</div>
            <div class="section__desc">支持按状态、推送组和关键字筛选，并可直接在编辑框里绑定飞书组。</div>
          </div>
          <el-space>
            <el-button @click="exportRows">导出 JSON</el-button>
            <el-button @click="triggerImport">导入 JSON</el-button>
            <el-button type="primary" @click="openEditor()">新增订阅</el-button>
          </el-space>
        </div>
      </template>

      <div class="toolbar">
        <el-input v-model="filters.q" clearable placeholder="按 MID / 名称 / 首页搜索" style="width: 240px" />
        <el-select v-model="filters.is_active" clearable placeholder="启用状态" style="width: 140px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
        <el-select v-model="filters.push_target_filter" clearable placeholder="推送组" style="width: 220px">
          <el-option label="未绑定（走默认组）" value="__unbound__" />
          <el-option
            v-for="target in pushTargets"
            :key="target.id"
            :label="renderPushTargetLabel(target)"
            :value="String(target.id)"
          />
        </el-select>
        <el-button type="primary" :loading="loading" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button type="warning" :disabled="!selectedIds.length" @click="batchUpdate(true)">批量启用</el-button>
        <el-button type="info" :disabled="!selectedIds.length" @click="batchUpdate(false)">批量停用</el-button>
        <el-button type="danger" :disabled="!selectedIds.length" @click="batchDelete">批量删除</el-button>
      </div>

      <el-table :data="rows" stripe v-loading="loading" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="48" />
        <el-table-column prop="mid" label="UP主 ID" width="180" />
        <el-table-column prop="name" label="名称" width="180" />
        <el-table-column class-name="mobile-hide-sm" prop="homepage_url" label="主页" min-width="260">
          <template #default="{ row }">
            <el-link :href="homepageUrl(row)" target="_blank" type="primary" :underline="false">
              {{ homepageUrl(row) }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="push_target_name" label="推送组" width="220">
          <template #default="{ row }">
            <el-tag v-if="row.push_target_name" type="success">{{ row.push_target_name }}</el-tag>
            <el-tag v-else type="info">默认组</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="启用" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ translateBoolean(row.is_active) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column class-name="mobile-hide-sm" prop="notes" label="备注" min-width="200" />
        <el-table-column class-name="mobile-hide-md" prop="last_check_time" label="最近检查" width="180">
          <template #default="{ row }">{{ formatDateTime(row.last_check_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-space>
              <el-button size="small" @click="openEditor(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="removeRow(row)">删除</el-button>
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

    <el-dialog v-model="editorVisible" :title="form.id ? '编辑订阅' : '新增订阅'" width="620px">
      <el-form label-width="120px">
        <el-form-item label="UP主 ID">
          <el-input v-model="form.mid" :disabled="!!form.id" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="主页">
          <el-input v-model="form.homepage_url" placeholder="https://space.bilibili.com/123456" />
        </el-form-item>
        <el-form-item label="推送组">
          <el-select v-model="form.push_target_id" clearable placeholder="不绑定则走默认组" style="width: 100%">
            <el-option label="默认组" :value="0" />
            <el-option
              v-for="target in activePushTargets"
              :key="target.id"
              :label="renderPushTargetLabel(target)"
              :value="target.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRow">保存</el-button>
      </template>
    </el-dialog>

    <input ref="fileInput" type="file" accept=".json,application/json" class="hidden-file-input" @change="handleImport" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { api } from "../api";
import type { PageResult, PushTargetItem, SubscriptionItem } from "../types";
import { buildQuery, formatDateTime, translateBoolean } from "../utils";

const loading = ref(false);
const saving = ref(false);
const rows = ref<SubscriptionItem[]>([]);
const pushTargets = ref<PushTargetItem[]>([]);
const total = ref(0);
const selectedIds = ref<number[]>([]);
const editorVisible = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

const filters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  is_active: undefined as boolean | undefined,
  push_target_filter: "",
});

const form = reactive({
  id: null as number | null,
  mid: "",
  name: "",
  homepage_url: "",
  push_target_id: 0 as number | null,
  notes: "",
  is_active: true,
});

const activePushTargets = computed(() => pushTargets.value.filter((item) => item.is_active));

function renderPushTargetLabel(target: PushTargetItem) {
  return target.is_default ? `${target.name}（默认）` : target.name;
}

function homepageUrl(row: SubscriptionItem) {
  return row.homepage_url || `https://space.bilibili.com/${row.mid}`;
}

function resetForm() {
  form.id = null;
  form.mid = "";
  form.name = "";
  form.homepage_url = "";
  form.push_target_id = 0;
  form.notes = "";
  form.is_active = true;
}

async function loadPushTargets() {
  const data = await api.get<PageResult<PushTargetItem>>("/push-targets?page=1&page_size=200");
  pushTargets.value = data.items;
}

function openEditor(row?: SubscriptionItem) {
  if (row) {
    form.id = row.id;
    form.mid = row.mid;
    form.name = row.name;
    form.homepage_url = row.homepage_url || "";
    form.push_target_id = row.push_target_id ?? 0;
    form.notes = row.notes || "";
    form.is_active = row.is_active;
  } else {
    resetForm();
  }
  editorVisible.value = true;
}

async function saveRow() {
  saving.value = true;
  try {
    const payload = {
      mid: form.mid,
      name: form.name,
      homepage_url: form.homepage_url || null,
      push_target_id: form.push_target_id || null,
      notes: form.notes || null,
      is_active: form.is_active,
    };
    if (form.id) {
      await api.put(`/subscriptions/${form.id}`, payload);
    } else {
      await api.post("/subscriptions", payload);
    }
    ElMessage.success("保存成功");
    editorVisible.value = false;
    await load();
  } finally {
    saving.value = false;
  }
}

async function load() {
  loading.value = true;
  try {
    if (!pushTargets.value.length) {
      await loadPushTargets();
    }
    const query: Record<string, string | number | boolean> = {
      page: filters.page,
      page_size: filters.page_size,
    };
    if (filters.q) query.q = filters.q;
    if (filters.is_active !== undefined) query.is_active = filters.is_active;
    if (filters.push_target_filter === "__unbound__") {
      query.unbound = true;
    } else if (filters.push_target_filter) {
      query.push_target_id = Number(filters.push_target_filter);
    }
    const data = await api.get<PageResult<SubscriptionItem>>(`/subscriptions${buildQuery(query)}`);
    rows.value = data.items;
    total.value = data.total;
    selectedIds.value = [];
  } finally {
    loading.value = false;
  }
}

function search() {
  filters.page = 1;
  load();
}

function reset() {
  filters.page = 1;
  filters.q = "";
  filters.is_active = undefined;
  filters.push_target_filter = "";
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

function handleSelectionChange(selection: SubscriptionItem[]) {
  selectedIds.value = selection.map((row) => row.id);
}

async function removeRow(row: SubscriptionItem) {
  await ElMessageBox.confirm(`确认删除订阅 ${row.name}？`, "提示", { type: "warning" });
  await api.delete(`/subscriptions/${row.id}`);
  ElMessage.success("删除成功");
  await load();
}

async function batchUpdate(isActive: boolean) {
  if (!selectedIds.value.length) return;
  await ElMessageBox.confirm(`确认批量${isActive ? "启用" : "停用"} ${selectedIds.value.length} 条订阅？`, "提示", {
    type: "warning",
  });
  await api.patch("/subscriptions/batch-active", { ids: selectedIds.value, is_active: isActive });
  ElMessage.success("操作成功");
  await load();
}

async function batchDelete() {
  if (!selectedIds.value.length) return;
  await ElMessageBox.confirm(`确认批量删除 ${selectedIds.value.length} 条订阅？`, "提示", { type: "warning" });
  await api.post("/subscriptions/batch-delete", { ids: selectedIds.value });
  ElMessage.success("删除成功");
  await load();
}

function exportRows() {
  const blob = new Blob([JSON.stringify(rows.value, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "subscriptions.json";
  a.click();
  URL.revokeObjectURL(url);
}

function triggerImport() {
  fileInput.value?.click();
}

async function handleImport(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  try {
    const text = await file.text();
    const items = JSON.parse(text) as Array<Partial<SubscriptionItem> & { id?: number }>;
    for (const item of items) {
      const payload = {
        mid: item.mid || "",
        name: item.name || "",
        homepage_url: item.homepage_url || null,
        push_target_id: item.push_target_id ?? 0,
        notes: item.notes || null,
        is_active: item.is_active ?? true,
      };
      if (item.id) {
        await api.put(`/subscriptions/${item.id}`, payload);
      } else if (payload.mid) {
        await api.post("/subscriptions", payload);
      }
    }
    ElMessage.success("导入完成");
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "导入失败");
  } finally {
    input.value = "";
  }
}

onMounted(async () => {
  await loadPushTargets();
  await load();
});
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

@media (max-width: 1024px) {
  .dashboard :deep(.page-grid--five) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .dashboard {
    gap: 14px;
  }

  .dashboard :deep(.page-hero),
  .dashboard :deep(.section-header),
  .dashboard :deep(.toolbar),
  .dashboard :deep(.el-dialog__footer) {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .dashboard :deep(.page-hero__panel) {
    width: 100%;
  }

  .dashboard :deep(.page-grid--five) {
    grid-template-columns: minmax(0, 1fr);
  }

  .dashboard :deep(.toolbar .el-input),
  .dashboard :deep(.toolbar .el-select),
  .dashboard :deep(.toolbar .el-button),
  .dashboard :deep(.el-dialog .el-input),
  .dashboard :deep(.el-dialog .el-select),
  .dashboard :deep(.el-dialog .el-switch) {
    width: 100% !important;
  }

  .dashboard :deep(.page-card),
  .dashboard :deep(.el-dialog__body) {
    padding: 14px;
  }

  .dashboard :deep(.el-table__cell) {
    padding: 8px 6px;
    font-size: 12px;
  }

  .dashboard :deep(.el-table .cell) {
    white-space: normal;
    line-height: 1.45;
  }

  .dashboard :deep(.mobile-hide-sm),
  .dashboard :deep(.mobile-hide-md) {
    display: none !important;
  }

  .dashboard :deep(.el-pagination) {
    flex-wrap: wrap;
    gap: 8px;
  }
}
</style>
