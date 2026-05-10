<template>
  <div class="dashboard">
    <section class="page-hero">
      <div class="page-hero__copy">
        <div class="page-hero__eyebrow">CONFIG CENTER</div>
        <h1>文件夹映射</h1>
        <p class="page-hero__desc">
          管理作者、分类、文件夹 token 与路径的映射关系，让内容落盘和规则路由更加清晰。
        </p>
        <div class="page-hero__chips">
          <span class="page-hero__chip">映射总数 {{ total }}</span>
          <span class="page-hero__chip">已选 {{ selectedIds.length }}</span>
          <span class="page-hero__chip">当前筛选 {{ filters.q ? "关键词" : "全部" }}</span>
        </div>
      </div>

      <div class="page-hero__panel">
        <div class="page-hero__panel-label">管理焦点</div>
        <div class="page-hero__panel-value">路径映射</div>
        <div class="page-hero__panel-note">建议保持作者、分类和 token 的命名一致，避免后续规则匹配时产生歧义。</div>
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
            <div class="page-hero__stat-value page-hero__stat-value--muted">{{ filters.q ? "关键词" : "全部" }}</div>
          </div>
        </div>
      </div>
    </section>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">文件夹映射</div>
            <div class="section__desc">管理作者、分类、文件夹 token 与路径的映射关系。</div>
          </div>
          <el-space>
            <el-button @click="exportRows">导出 JSON</el-button>
            <el-button @click="triggerImport">导入 JSON</el-button>
            <el-button type="primary" @click="openEditor()">新增映射</el-button>
          </el-space>
        </div>
      </template>

      <div class="toolbar">
        <el-input v-model="filters.q" clearable placeholder="按作者 / 分类 / token / 路径搜索" style="width: 280px" />
        <el-button type="primary" :loading="loading" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button type="danger" :disabled="!selectedIds.length" @click="batchDelete">批量删除</el-button>
      </div>

      <el-table :data="rows" stripe v-loading="loading" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="48" />
        <el-table-column prop="uploader_name" label="作者" width="180" />
        <el-table-column prop="category" label="分类" width="180" />
        <el-table-column prop="folder_path" label="文件夹路径" min-width="240" />
        <el-table-column prop="folder_token" label="文件夹 token" min-width="260" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
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

    <el-dialog v-model="editorVisible" :title="form.id ? '编辑映射' : '新增映射'" width="640px">
      <el-form label-width="120px">
        <el-form-item label="作者">
          <el-input v-model="form.uploader_name" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="form.category" />
        </el-form-item>
        <el-form-item label="文件夹 token">
          <el-input v-model="form.folder_token" />
        </el-form-item>
        <el-form-item label="文件夹路径">
          <el-input v-model="form.folder_path" />
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
import type { FolderMappingItem, PageResult } from "../types";
import { buildQuery, formatDateTime } from "../utils";

const loading = ref(false);
const saving = ref(false);
const rows = ref<FolderMappingItem[]>([]);
const total = ref(0);
const selectedIds = ref<number[]>([]);
const editorVisible = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

const filters = reactive({
  page: 1,
  page_size: 20,
  q: "",
});

const form = reactive({
  id: null as number | null,
  uploader_name: "",
  category: "",
  folder_token: "",
  folder_path: "",
});

function resetForm() {
  form.id = null;
  form.uploader_name = "";
  form.category = "";
  form.folder_token = "";
  form.folder_path = "";
}

function openEditor(row?: FolderMappingItem) {
  if (row) {
    form.id = row.id;
    form.uploader_name = row.uploader_name;
    form.category = row.category;
    form.folder_token = row.folder_token;
    form.folder_path = row.folder_path;
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
      category: form.category,
      folder_token: form.folder_token,
      folder_path: form.folder_path,
    };
    if (form.id) {
      await api.put(`/folder-mappings/${form.id}`, payload);
    } else {
      await api.post("/folder-mappings", payload);
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
    const data = await api.get<PageResult<FolderMappingItem>>(`/folder-mappings${buildQuery(filters)}`);
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

function handleSelectionChange(selection: FolderMappingItem[]) {
  selectedIds.value = selection.map((row) => row.id);
}

async function removeRow(row: FolderMappingItem) {
  await ElMessageBox.confirm(`确认删除文件夹映射 ${row.folder_path}？`, "提示", { type: "warning" });
  await api.delete(`/folder-mappings/${row.id}`);
  ElMessage.success("删除成功");
  await load();
}

async function batchDelete() {
  if (!selectedIds.value.length) return;
  await ElMessageBox.confirm(`确认批量删除 ${selectedIds.value.length} 条映射？`, "提示", { type: "warning" });
  await api.post("/folder-mappings/batch-delete", { ids: selectedIds.value });
  ElMessage.success("删除成功");
  await load();
}

function exportRows() {
  const blob = new Blob([JSON.stringify(rows.value, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "folder-mappings.json";
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
    const items = JSON.parse(text) as Array<Partial<FolderMappingItem> & { id?: number }>;
    for (const item of items) {
      const payload = {
        uploader_name: item.uploader_name || "",
        category: item.category || "",
        folder_token: item.folder_token || "",
        folder_path: item.folder_path || "",
      };
      if (item.id) {
        await api.put(`/folder-mappings/${item.id}`, payload);
      } else if (payload.uploader_name && payload.folder_token && payload.folder_path) {
        await api.post("/folder-mappings", payload);
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
