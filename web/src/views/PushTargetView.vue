<template>
  <div class="dashboard">
    <section class="page-hero">
      <div class="page-hero__copy">
        <div class="page-hero__eyebrow">PUSH TARGETS</div>
        <h1>推送配置</h1>
        <p class="page-hero__desc">
          管理飞书推送组。这里只配置群名、receive_id 和 receive_id_type，飞书应用凭证仍使用全局配置。
        </p>
        <div class="page-hero__chips">
          <span class="page-hero__chip">推送组 {{ total }}</span>
          <span class="page-hero__chip">默认组 {{ defaultCount }}</span>
          <span class="page-hero__chip">启用 {{ activeCount }}</span>
        </div>
      </div>

      <div class="page-hero__panel">
        <div class="page-hero__panel-label">路由规则</div>
        <div class="page-hero__panel-value">显式默认组</div>
        <div class="page-hero__panel-note">
          B站订阅未绑定推送组时，会自动落到这里的默认组。默认组只能有一条，且不能被停用或删除。
        </div>
      </div>
    </section>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">飞书推送组</div>
            <div class="section__desc">支持增删改查、设默认和启停。群名称仅用于展示与审计，不参与发送。</div>
          </div>
          <el-button type="primary" @click="openEditor()">新增推送组</el-button>
        </div>
      </template>

      <div class="toolbar">
        <el-input v-model="filters.q" clearable placeholder="按群名称 / receive_id 搜索" style="width: 260px" />
        <el-select v-model="filters.is_active" clearable placeholder="启用状态" style="width: 140px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <el-table :data="rows" stripe v-loading="loading">
        <el-table-column prop="name" label="群名称" width="220">
          <template #default="{ row }">
            <el-space>
              <span>{{ row.name }}</span>
              <el-tag v-if="row.is_default" type="warning">默认</el-tag>
            </el-space>
          </template>
        </el-table-column>
        <el-table-column prop="receive_id" label="Receive ID" min-width="260" />
        <el-table-column prop="receive_id_type" label="类型" width="140" />
        <el-table-column prop="is_active" label="启用" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? "启用" : "停用" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="220" />
        <el-table-column prop="updated_at" label="更新时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280">
          <template #default="{ row }">
            <el-space wrap>
              <el-button size="small" @click="openEditor(row)">编辑</el-button>
              <el-button size="small" type="warning" :disabled="row.is_default" @click="setDefault(row)">设为默认</el-button>
              <el-button
                size="small"
                :type="row.is_active ? 'info' : 'success'"
                :disabled="row.is_default && row.is_active"
                @click="toggleActive(row)"
              >
                {{ row.is_active ? "停用" : "启用" }}
              </el-button>
              <el-button size="small" type="danger" :disabled="row.is_default" @click="removeRow(row)">删除</el-button>
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

    <el-dialog v-model="editorVisible" :title="form.id ? '编辑推送组' : '新增推送组'" width="620px">
      <el-form label-width="120px">
        <el-form-item label="群名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="Receive ID">
          <el-input v-model="form.receive_id" />
        </el-form-item>
        <el-form-item label="Receive Type">
          <el-select v-model="form.receive_id_type" style="width: 100%">
            <el-option label="chat_id" value="chat_id" />
            <el-option label="open_id" value="open_id" />
            <el-option label="user_id" value="user_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRow">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { api } from "../api";
import type { PageResult, PushTargetItem } from "../types";
import { buildQuery, formatDateTime } from "../utils";

const loading = ref(false);
const saving = ref(false);
const rows = ref<PushTargetItem[]>([]);
const total = ref(0);
const editorVisible = ref(false);

const filters = reactive({
  page: 1,
  page_size: 20,
  q: "",
  is_active: undefined as boolean | undefined,
});

const form = reactive({
  id: null as number | null,
  name: "",
  receive_id: "",
  receive_id_type: "chat_id",
  notes: "",
  is_active: true,
  is_default: false,
});

const defaultCount = computed(() => rows.value.filter((row) => row.is_default).length);
const activeCount = computed(() => rows.value.filter((row) => row.is_active).length);

function resetForm() {
  form.id = null;
  form.name = "";
  form.receive_id = "";
  form.receive_id_type = "chat_id";
  form.notes = "";
  form.is_active = true;
  form.is_default = false;
}

function openEditor(row?: PushTargetItem) {
  if (row) {
    form.id = row.id;
    form.name = row.name;
    form.receive_id = row.receive_id;
    form.receive_id_type = row.receive_id_type;
    form.notes = row.notes || "";
    form.is_active = row.is_active;
    form.is_default = row.is_default;
  } else {
    resetForm();
  }
  editorVisible.value = true;
}

async function saveRow() {
  saving.value = true;
  try {
    const payload = {
      channel: "feishu",
      name: form.name,
      receive_id: form.receive_id,
      receive_id_type: form.receive_id_type,
      notes: form.notes || null,
      is_active: form.is_active,
      is_default: form.is_default,
    };
    if (form.id) {
      await api.put(`/push-targets/${form.id}`, payload);
    } else {
      await api.post("/push-targets", payload);
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
    const query: Record<string, string | number | boolean> = {
      page: filters.page,
      page_size: filters.page_size,
    };
    if (filters.q) query.q = filters.q;
    if (filters.is_active !== undefined) query.is_active = filters.is_active;
    const data = await api.get<PageResult<PushTargetItem>>(`/push-targets${buildQuery(query)}`);
    rows.value = data.items;
    total.value = data.total;
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

async function setDefault(row: PushTargetItem) {
  await api.patch(`/push-targets/${row.id}/default`, {});
  ElMessage.success("已切换默认组");
  await load();
}

async function toggleActive(row: PushTargetItem) {
  const status = row.is_active ? "inactive" : "active";
  await api.patch(`/push-targets/${row.id}/active`, { status });
  ElMessage.success("状态已更新");
  await load();
}

async function removeRow(row: PushTargetItem) {
  await ElMessageBox.confirm(`确认删除推送组 ${row.name}？`, "提示", { type: "warning" });
  await api.delete(`/push-targets/${row.id}`);
  ElMessage.success("删除成功");
  await load();
}

onMounted(load);
</script>
