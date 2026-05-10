<template>
  <div class="dashboard">
    <section class="page-hero">
      <div class="page-hero__copy">
        <div class="page-hero__eyebrow">CONFIG CENTER</div>
        <h1>规则管理</h1>
        <p class="page-hero__desc">
          按优先级匹配规则，支持命中前后调整、批量启停以及导入导出，适合高频维护。
        </p>
        <div class="page-hero__chips">
          <span class="page-hero__chip">规则总数 {{ total }}</span>
          <span class="page-hero__chip">已选 {{ selectedIds.length }}</span>
          <span class="page-hero__chip">当前筛选 {{ filters.is_active === true ? "启用" : filters.is_active === false ? "停用" : "全部" }}</span>
        </div>
      </div>

      <div class="page-hero__panel">
        <div class="page-hero__panel-label">管理焦点</div>
        <div class="page-hero__panel-value">优先级匹配</div>
        <div class="page-hero__panel-note">建议在编辑规则时同时检查优先级顺序，避免更具体的规则被通配规则覆盖。</div>
        <div class="page-hero__stats">
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">总数</div>
            <div class="page-hero__stat-value">{{ total }}</div>
          </div>
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">已选</div>
            <div class="page-hero__stat-value">{{ selectedIds.length }}</div>
          </div>
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">筛选</div>
            <div class="page-hero__stat-value page-hero__stat-value--muted">{{ filters.is_active === true ? "启用" : filters.is_active === false ? "停用" : "全部" }}</div>
          </div>
        </div>
      </div>
    </section>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">规则管理</div>
            <div class="section__desc">按优先级匹配规则，支持命中前后调整、批量启停和导入导出。</div>
          </div>
          <el-space>
            <el-button @click="exportRows">导出 JSON</el-button>
            <el-button @click="triggerImport">导入 JSON</el-button>
            <el-button type="primary" @click="openEditor()">新增规则</el-button>
          </el-space>
        </div>
      </template>

      <div class="toolbar">
        <el-input v-model="filters.q" clearable placeholder="按作者 / 规则 / 目标文件夹搜索" style="width: 260px" />
        <el-select v-model="filters.is_active" clearable placeholder="是否启用" style="width: 140px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button type="warning" :disabled="!selectedIds.length" @click="batchUpdate(true)">批量启用</el-button>
        <el-button type="info" :disabled="!selectedIds.length" @click="batchUpdate(false)">批量停用</el-button>
        <el-button type="danger" :disabled="!selectedIds.length" @click="batchDelete">批量删除</el-button>
      </div>

      <el-table :data="rows" stripe v-loading="loading" @selection-change="handleSelectionChange">
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
        <el-table-column label="操作" width="260">
          <template #default="{ row }">
            <el-space>
              <el-button size="small" @click="movePriority(row, 1)">上移</el-button>
              <el-button size="small" @click="movePriority(row, -1)">下移</el-button>
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

    <el-dialog v-model="editorVisible" :title="form.id ? '编辑规则' : '新增规则'" width="640px">
      <el-form label-width="120px">
        <el-form-item label="作者">
          <el-input v-model="form.uploader_name" />
        </el-form-item>
        <el-form-item label="规则">
          <el-input v-model="form.pattern" />
        </el-form-item>
        <el-form-item label="目标文件夹">
          <el-input v-model="form.target_folder" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="0" :max="9999" />
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
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { api } from "../api";
import type { PageResult, RuleItem } from "../types";
import { buildQuery, formatDateTime, translateBoolean } from "../utils";

const loading = ref(false);
const saving = ref(false);
const rows = ref<RuleItem[]>([]);
const total = ref(0);
const selectedIds = ref<number[]>([]);
const editorVisible = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

const filters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  is_active: undefined as boolean | undefined,
});

const form = reactive({
  id: null as number | null,
  uploader_name: "",
  pattern: "",
  target_folder: "",
  priority: 100,
  is_active: true,
});

function resetForm() {
  form.id = null;
  form.uploader_name = "";
  form.pattern = "";
  form.target_folder = "";
  form.priority = 100;
  form.is_active = true;
}

function openEditor(row?: RuleItem) {
  if (row) {
    form.id = row.id;
    form.uploader_name = row.uploader_name;
    form.pattern = row.pattern;
    form.target_folder = row.target_folder;
    form.priority = row.priority;
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
      uploader_name: form.uploader_name,
      pattern: form.pattern,
      target_folder: form.target_folder,
      priority: form.priority,
      is_active: form.is_active,
    };
    if (form.id) {
      await api.put(`/classification-rules/${form.id}`, payload);
    } else {
      await api.post("/classification-rules", payload);
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
    const data = await api.get<PageResult<RuleItem>>(`/classification-rules${buildQuery(filters)}`);
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

function handleSelectionChange(selection: RuleItem[]) {
  selectedIds.value = selection.map((row) => row.id);
}

async function removeRow(row: RuleItem) {
  await ElMessageBox.confirm(`确认删除规则 ${row.pattern}？`, "提示", { type: "warning" });
  await api.delete(`/classification-rules/${row.id}`);
  ElMessage.success("删除成功");
  await load();
}

async function batchUpdate(isActive: boolean) {
  if (!selectedIds.value.length) return;
  await ElMessageBox.confirm(`确认批量${isActive ? "启用" : "停用"} ${selectedIds.value.length} 条规则？`, "提示", {
    type: "warning",
  });
  await api.patch("/classification-rules/batch-active", { ids: selectedIds.value, is_active: isActive });
  ElMessage.success("操作成功");
  await load();
}

async function batchDelete() {
  if (!selectedIds.value.length) return;
  await ElMessageBox.confirm(`确认批量删除 ${selectedIds.value.length} 条规则？`, "提示", { type: "warning" });
  await api.post("/classification-rules/batch-delete", { ids: selectedIds.value });
  ElMessage.success("删除成功");
  await load();
}

async function movePriority(row: RuleItem, delta: number) {
  const nextPriority = Math.max(0, row.priority + delta);
  await api.put(`/classification-rules/${row.id}`, {
    uploader_name: row.uploader_name,
    pattern: row.pattern,
    target_folder: row.target_folder,
    priority: nextPriority,
    is_active: row.is_active,
  });
  ElMessage.success("优先级已更新");
  await load();
}

function exportRows() {
  const blob = new Blob([JSON.stringify(rows.value, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "classification-rules.json";
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
    const items = JSON.parse(text) as Array<Partial<RuleItem> & { id?: number }>;
    for (const item of items) {
      const payload = {
        uploader_name: item.uploader_name || "",
        pattern: item.pattern || "",
        target_folder: item.target_folder || "",
        priority: item.priority ?? 100,
        is_active: item.is_active ?? true,
      };
      if (item.id) {
        await api.put(`/classification-rules/${item.id}`, payload);
      } else if (payload.uploader_name && payload.pattern && payload.target_folder) {
        await api.post("/classification-rules", payload);
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

onMounted(load);
</script>
