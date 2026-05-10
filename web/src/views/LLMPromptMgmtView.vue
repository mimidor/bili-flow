<template>
  <div class="dashboard">
    <section class="hero-card">
      <div class="hero-copy">
        <div class="hero-eyebrow">LLM PROMPTS</div>
        <h1>LLM提示词管理</h1>
        <p class="hero-description">管理提示词模板，查看本地版本历史、回滚快照并快速编辑。</p>
      </div>
      <div class="hero-panel">
        <div>
          <div class="hero-panel__label">模板数量</div>
          <div class="hero-panel__value">{{ prompts.length }}</div>
          <div class="hero-panel__meta">本地历史快照 {{ totalSnapshots }}</div>
        </div>
      </div>
    </section>

    <div class="chart-grid">
      <el-card class="page-card section">
        <template #header>
          <div class="section-header">
            <div>
              <div class="section__title">提示词模板</div>
              <div class="section__desc">选择模型后可直接编辑并保存</div>
            </div>
          </div>
        </template>

        <el-table :data="prompts" v-loading="loading" stripe>
          <el-table-column prop="name" label="用途" width="180" />
          <el-table-column prop="description" label="说明" min-width="250" />
          <el-table-column prop="model_profile_id" label="绑定模型" width="200">
            <template #default="{ row }">
              <el-select v-model="row.model_profile_id" clearable placeholder="使用全局默认" @change="savePrompt(row)">
                <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="最近修改" width="180">
            <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="openEditor(row)">编辑提示词</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="page-card section">
        <template #header>
          <div class="section-header">
            <div>
              <div class="section__title">版本历史</div>
              <div class="section__desc">本地保存最近的提示词快照，可回滚</div>
            </div>
          </div>
        </template>

        <el-empty v-if="!snapshotList.length" description="暂无快照" />
        <div v-else class="audit-list">
          <div
            v-for="snapshot in snapshotList"
            :key="snapshot.key"
            class="audit-list__item"
            :class="{ 'is-active-snapshot': selectedSnapshot?.key === snapshot.key }"
            @click="selectSnapshot(snapshot)"
          >
            <div class="audit-list__meta">
              <el-tag size="small" type="warning">{{ snapshot.promptName }}</el-tag>
              <span class="muted">{{ snapshot.createdAt }}</span>
            </div>
            <div class="audit-list__title">{{ snapshot.preview }}</div>
          </div>
        </div>
      </el-card>
    </div>

    <el-dialog v-model="editorVisible" :title="'编辑提示词：' + (activeRow ? activeRow.name : '')" width="900px" top="5vh">
      <div style="margin-bottom: 10px; color: #666">{{ activeRow?.description }}</div>
      <div class="chart-grid">
        <el-input v-model="editPromptText" type="textarea" :rows="18" placeholder="在此输入 Prompt..." style="font-family: monospace;" />
        <div class="prompt-diff">
          <div class="section__title">变更预览</div>
          <pre class="summary-box prompt-diff__text">{{ diffText }}</pre>
        </div>
      </div>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button @click="rollbackSnapshot" :disabled="!selectedSnapshot">回滚到所选版本</el-button>
        <el-button type="primary" :loading="saving" @click="doSavePrompt">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { api } from "../api";

type PromptRow = {
  id: number;
  name: string;
  description?: string | null;
  prompt_text: string;
  model_profile_id?: number | null;
  updated_at?: string | null;
};

type PromptSnapshot = {
  key: string;
  promptId: number;
  promptName: string;
  promptText: string;
  createdAt: string;
  preview: string;
};

const prompts = ref<PromptRow[]>([]);
const models = ref<any[]>([]);
const loading = ref(false);
const saving = ref(false);
const editorVisible = ref(false);
const activeRow = ref<PromptRow | null>(null);
const editPromptText = ref("");
const selectedSnapshot = ref<PromptSnapshot | null>(null);

const storageKey = "bili-flow.prompt-snapshots";

const snapshotList = computed(() => {
  const all = loadSnapshots();
  return all.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
});

const totalSnapshots = computed(() => snapshotList.value.length);

const diffText = computed(() => {
  if (!activeRow.value) return "-";
  const current = activeRow.value.prompt_text || "";
  const next = editPromptText.value || "";
  return buildDiff(current, next);
});

function formatTime(ts?: string | null) {
  if (!ts) return "-";
  return new Date(ts).toLocaleString();
}

function loadSnapshots(): PromptSnapshot[] {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return [];
    return JSON.parse(raw) as PromptSnapshot[];
  } catch {
    return [];
  }
}

function saveSnapshots(list: PromptSnapshot[]) {
  localStorage.setItem(storageKey, JSON.stringify(list.slice(0, 200)));
}

function pushSnapshot(row: PromptRow, text: string) {
  const list = loadSnapshots();
  list.unshift({
    key: `${row.id}-${Date.now()}`,
    promptId: row.id,
    promptName: row.name,
    promptText: text,
    createdAt: new Date().toLocaleString(),
    preview: text.split("\n").slice(0, 3).join(" ").slice(0, 180),
  });
  saveSnapshots(list);
}

function buildDiff(oldText: string, newText: string) {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");
  const max = Math.max(oldLines.length, newLines.length);
  const output: string[] = [];
  for (let index = 0; index < max; index += 1) {
    const oldLine = oldLines[index];
    const newLine = newLines[index];
    if (oldLine === newLine) {
      if (oldLine !== undefined) output.push(`  ${oldLine}`);
      continue;
    }
    if (oldLine !== undefined) output.push(`- ${oldLine}`);
    if (newLine !== undefined) output.push(`+ ${newLine}`);
  }
  return output.join("\n") || "-";
}

async function loadData() {
  loading.value = true;
  try {
    const [promptRows, modelRows] = await Promise.all([
      api.get<PromptRow[]>("/llm/prompts"),
      api.get<any[]>("/llm/profiles"),
    ]);
    prompts.value = promptRows;
    models.value = modelRows.filter((m: any) => m.is_active);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载失败");
  } finally {
    loading.value = false;
  }
}

function openEditor(row: PromptRow) {
  activeRow.value = row;
  editPromptText.value = row.prompt_text || "";
  selectedSnapshot.value = snapshotList.value.find((item) => item.promptId === row.id) || null;
  editorVisible.value = true;
}

function selectSnapshot(snapshot: PromptSnapshot) {
  selectedSnapshot.value = snapshot;
  if (activeRow.value && activeRow.value.id === snapshot.promptId) {
    editPromptText.value = snapshot.promptText;
  }
}

async function savePrompt(row: PromptRow) {
  try {
    await api.put(`/llm/prompts/${row.id}`, {
      prompt_text: row.prompt_text,
      model_profile_id: row.model_profile_id || null,
    });
    pushSnapshot(row, row.prompt_text);
    ElMessage.success("保存成功");
    await loadData();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存失败");
    loadData();
  }
}

async function doSavePrompt() {
  if (!activeRow.value) return;
  saving.value = true;
  try {
    await api.put(`/llm/prompts/${activeRow.value.id}`, {
      prompt_text: editPromptText.value,
      model_profile_id: activeRow.value.model_profile_id || null,
    });
    activeRow.value.prompt_text = editPromptText.value;
    pushSnapshot(activeRow.value, editPromptText.value);
    ElMessage.success("保存成功");
    editorVisible.value = false;
    await loadData();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存失败");
  } finally {
    saving.value = false;
  }
}

async function rollbackSnapshot() {
  if (!activeRow.value || !selectedSnapshot.value) return;
  editPromptText.value = selectedSnapshot.value.promptText;
  await doSavePrompt();
}

onMounted(() => {
  loadData();
});
</script>
