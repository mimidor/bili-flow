<template>
  <div class="dashboard env-page">
    <section class="page-hero">
      <div class="page-hero__copy">
        <div class="page-hero__eyebrow">SYSTEM CONFIG</div>
        <h1>环境配置</h1>
        <p class="page-hero__desc">
          查看和编辑运行时环境变量、调度参数和敏感配置。保存后会立即写入运行时配置和 `.env`。
        </p>
        <div class="page-hero__chips">
          <span class="page-hero__chip">分组 {{ groupOptions.length }}</span>
          <span class="page-hero__chip">可编辑 {{ editableRowsCount }}</span>
          <span class="page-hero__chip">当前条数 {{ filteredRows.length }}</span>
        </div>
      </div>

      <div class="page-hero__panel">
        <div class="page-hero__panel-label">配置概览</div>
        <div class="page-hero__panel-value">{{ rows.length }} 项</div>
        <div class="page-hero__panel-note">
          保存后会立即写入配置表和 `.env`。像数据库地址这类启动级配置，仍建议重启相关服务。
        </div>
        <div class="page-hero__stats">
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">总数</div>
            <div class="page-hero__stat-value">{{ rows.length }}</div>
          </div>
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">分组</div>
            <div class="page-hero__stat-value">{{ groupOptions.length }}</div>
          </div>
          <div class="page-hero__stat">
            <div class="page-hero__stat-label">可编辑</div>
            <div class="page-hero__stat-value">{{ editableRowsCount }}</div>
          </div>
        </div>
      </div>
    </section>

    <el-card class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.q" clearable placeholder="按键名 / 名称 / 分组搜索" style="width: 280px" />
        <el-select v-model="filters.group" clearable placeholder="按分组筛选" style="width: 180px">
          <el-option v-for="group in groupOptions" :key="group" :label="group" :value="group">
            <span class="env-group-option">
              <span class="env-group-dot" :style="groupStyle(group)" />
              <span>{{ group }}</span>
            </span>
          </el-option>
        </el-select>
        <el-select v-model="filters.editable" clearable placeholder="是否可编辑" style="width: 160px">
          <el-option label="可编辑" :value="true" />
          <el-option label="只读" :value="false" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <el-alert
        class="config-tip"
        type="info"
        show-icon
        :closable="false"
        title="保存后会立即写入配置表和 .env，并刷新当前进程配置；数据库地址这类启动级配置仍建议重启服务。"
      />

      <el-table :data="filteredRows" v-loading="loading" stripe :row-style="rowStyle" :cell-class-name="cellClassName">
        <el-table-column prop="group" label="分组" width="140">
          <template #default="{ row }">
            <el-tag class="env-group-tag" effect="dark" :style="groupStyle(row.group)">
              {{ row.group }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="key" label="键名" width="240" />
        <el-table-column prop="label" label="名称" width="220" />
        <el-table-column prop="value" label="当前值" min-width="220">
          <template #default="{ row }">{{ renderValue(row) }}</template>
        </el-table-column>
        <el-table-column prop="value_type" label="类型" width="140" />
        <el-table-column prop="editable" label="可编辑" width="100">
          <template #default="{ row }">{{ row.editable ? "是" : "否" }}</template>
        </el-table-column>
        <el-table-column prop="restart_required" label="需重启" width="100">
          <template #default="{ row }">{{ row.restart_required ? "是" : "否" }}</template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="320">
          <template #default="{ row }">
            <span class="summary-box">{{ row.description || "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" :disabled="!row.editable" @click="openEditor(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="editorVisible" :title="activeRow ? `编辑：${activeRow.label}` : '编辑配置'" width="620px">
      <template v-if="activeRow">
        <el-form label-width="140px">
          <el-form-item label="键名">
            <el-input :model-value="activeRow.key" disabled />
          </el-form-item>
          <el-form-item label="名称">
            <el-input :model-value="activeRow.label" disabled />
          </el-form-item>
          <el-form-item label="分组">
            <el-input :model-value="activeRow.group" disabled />
          </el-form-item>
          <el-form-item label="当前值">
            <template v-if="activeRow.value_type === 'bool'">
              <el-switch v-model="editValueBoolean" />
            </template>
            <template v-else-if="activeRow.value_type === 'int'">
              <el-input-number v-model="editValueNumber" :step="1" :min="-999999999" style="width: 240px" />
            </template>
            <template v-else-if="activeRow.value_type === 'select'">
              <el-select v-model="editValueText" filterable style="width: 100%">
                <el-option v-for="option in activeRow.options || []" :key="option" :label="option" :value="option" />
              </el-select>
            </template>
            <template v-else-if="activeRow.value_type === 'push_target_select'">
              <el-select v-model="editValueNumber" clearable filterable style="width: 100%">
                <el-option
                  v-for="option in activeRow.option_items || []"
                  :key="option.value"
                  :label="`${option.label}${option.is_default ? '（默认）' : ''}`"
                  :value="option.value"
                />
              </el-select>
            </template>
            <template v-else>
              <el-input
                v-model="editValueText"
                :show-password="activeRow.secret"
                :type="activeRow.secret ? 'password' : 'text'"
                placeholder="请输入配置值"
              />
            </template>
          </el-form-item>
          <el-form-item label="说明">
            <el-input :model-value="activeRow.description || '-'" disabled type="textarea" :rows="3" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存并应用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { api } from "../api";
import type { EnvConfigItem, EnvConfigResponse } from "../types";

const loading = ref(false);
const saving = ref(false);
const rows = ref<EnvConfigItem[]>([]);
const editorVisible = ref(false);
const activeRow = ref<EnvConfigItem | null>(null);
const editValueText = ref("");
const editValueNumber = ref<number>(0);
const editValueBoolean = ref(false);

const filters = ref({
  q: "",
  group: "",
  editable: undefined as boolean | undefined,
});

const groupOptions = computed(() => Array.from(new Set(rows.value.map((row) => row.group))).sort((a, b) => a.localeCompare(b, "zh-Hans-CN")));

const filteredRows = computed(() =>
  rows.value.filter((row) => {
    if (filters.value.q) {
      const keyword = filters.value.q.trim().toLowerCase();
      const hit =
        row.key.toLowerCase().includes(keyword) ||
        row.label.toLowerCase().includes(keyword) ||
        row.group.toLowerCase().includes(keyword) ||
        (row.description || "").toLowerCase().includes(keyword);
      if (!hit) return false;
    }
    if (filters.value.group && row.group !== filters.value.group) return false;
    if (filters.value.editable !== undefined && row.editable !== filters.value.editable) return false;
    return true;
  }),
);

const editableRowsCount = computed(() => rows.value.filter((row) => row.editable).length);

const groupPalette = [
  { accent: "#60a5fa", bg: "rgba(37, 99, 235, 0.16)" },
  { accent: "#38bdf8", bg: "rgba(14, 165, 233, 0.16)" },
  { accent: "#818cf8", bg: "rgba(99, 102, 241, 0.16)" },
  { accent: "#22c55e", bg: "rgba(34, 197, 94, 0.14)" },
  { accent: "#f59e0b", bg: "rgba(245, 158, 11, 0.16)" },
  { accent: "#ec4899", bg: "rgba(236, 72, 153, 0.14)" },
  { accent: "#14b8a6", bg: "rgba(20, 184, 166, 0.14)" },
  { accent: "#a855f7", bg: "rgba(168, 85, 247, 0.14)" },
];

function hashGroup(group: string): number {
  let hash = 0;
  for (let i = 0; i < group.length; i += 1) {
    hash = (hash * 31 + group.charCodeAt(i)) >>> 0;
  }
  return hash;
}

function getGroupPalette(group: string) {
  return groupPalette[hashGroup(group) % groupPalette.length];
}

function groupStyle(group: string) {
  const palette = getGroupPalette(group);
  return {
    "--env-group-accent": palette.accent,
    "--env-group-bg": palette.bg,
  } as Record<string, string>;
}

function rowStyle({ row }: { row: EnvConfigItem }) {
  const palette = getGroupPalette(row.group);
  return {
    ...groupStyle(row.group),
    backgroundImage: `linear-gradient(90deg, ${palette.bg} 0%, rgba(255, 255, 255, 0) 34%)`,
  } as Record<string, string>;
}

function cellClassName({ column }: { column: { property?: string } }) {
  return column.property === "group" ? "env-group-cell" : "";
}

function renderValue(row: EnvConfigItem): string {
  if (row.secret && row.value) return "******";
  if (row.value_type === "bool") return row.value ? "是" : "否";
  if (row.value_type === "push_target_select") {
    const option = (row.option_items || []).find((item) => item.value === Number(row.value || 0));
    return option ? option.label : row.value ? String(row.value) : "-";
  }
  if (row.value === null || row.value === undefined || row.value === "") return "-";
  return String(row.value);
}

async function load() {
  loading.value = true;
  try {
    const data = await api.get<EnvConfigResponse>("/configs/env");
    rows.value = data.items;
  } finally {
    loading.value = false;
  }
}

function reset() {
  filters.value.q = "";
  filters.value.group = "";
  filters.value.editable = undefined;
}

function openEditor(row: EnvConfigItem) {
  activeRow.value = row;
  editValueText.value = typeof row.value === "string" ? row.value : row.value !== null && row.value !== undefined ? String(row.value) : "";
  editValueNumber.value = typeof row.value === "number" ? row.value : Number(row.value || 0);
  editValueBoolean.value = Boolean(row.value);
  editorVisible.value = true;
}

async function save() {
  if (!activeRow.value) return;
  saving.value = true;
  try {
    const row = activeRow.value;
    let value: string | number | boolean;
    if (row.value_type === "bool") {
      value = editValueBoolean.value;
    } else if (row.value_type === "int" || row.value_type === "push_target_select") {
      value = editValueNumber.value;
    } else {
      value = editValueText.value;
    }

    const response = await api.put<EnvConfigResponse>("/configs/env", {
      updates: {
        [row.key]: value,
      },
    });
    rows.value = response.items;
    editorVisible.value = false;
    ElMessage.success("配置已保存并应用");
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>
