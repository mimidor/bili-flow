<template>
  <div class="dashboard">
    <section class="hero-card">
      <div class="hero-copy">
        <div class="hero-eyebrow">LLM MODELS</div>
        <h1>模型管理</h1>
        <p class="hero-description">
          统一管理模型供应商、默认模型、联网搜索、推理、图片和工具能力，并支持单模型测试、多模型批量测试，以及模型级临时对话调试。
        </p>
      </div>
      <div class="hero-panel">
        <div>
          <div class="hero-panel__label">模型概览</div>
          <div class="hero-panel__value">{{ models.length }}</div>
          <div class="hero-panel__meta">
            默认 {{ defaultCount }} 路，联网 {{ webSearchCount }} 路，推理 {{ reasoningCount }} 路，图片
            {{ imageCount }} 路，工具 {{ toolsCount }}
          </div>
        </div>
      </div>
    </section>

    <div class="page-grid">
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">模型总数</div>
        <div class="stat-value">{{ models.length }}</div>
      </el-card>
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">生效模型</div>
        <div class="stat-value">{{ defaultCount }}</div>
      </el-card>
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">联网搜索</div>
        <div class="stat-value">{{ webSearchCount }}</div>
      </el-card>
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">推理开关</div>
        <div class="stat-value">{{ reasoningCount }}</div>
      </el-card>
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">图片开关</div>
        <div class="stat-value">{{ imageCount }}</div>
      </el-card>
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">工具开关</div>
        <div class="stat-value">{{ toolsCount }}</div>
      </el-card>
      <el-card class="stat-card stat-card--dashboard">
        <div class="stat-label">最近成功率</div>
        <div class="stat-value">{{ successRateLabel }}</div>
      </el-card>
    </div>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">模型列表</div>
            <div class="section__desc">支持新增、编辑、设为默认、单模型测试、行内对话和多模型并行测试。</div>
          </div>
          <el-space wrap>
            <el-tag v-if="selectedCount > 0" type="success" effect="plain">已选择 {{ selectedCount }} 个模型</el-tag>
            <el-button type="warning" :disabled="selectedCount === 0" @click="openWorkbenchForSelected">
              一键测试所选模型
            </el-button>
            <el-button type="primary" @click="openEditor(null)">新增模型配置</el-button>
          </el-space>
        </div>
      </template>

      <el-table
        ref="tableRef"
        :data="models"
        v-loading="loading"
        stripe
        row-key="id"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="48" fixed="left" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="provider" label="供应商" width="160">
          <template #default="{ row }">{{ translateProvider(row.provider) }}</template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型名" min-width="180" />
        <el-table-column label="联网" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enable_web_search ? 'success' : 'info'">
              {{ row.enable_web_search ? "开启" : "关闭" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="推理" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enable_reasoning ? 'success' : 'info'">
              {{ row.enable_reasoning ? "开启" : "关闭" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="图片" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enable_image ? 'success' : 'info'">
              {{ row.enable_image ? "开启" : "关闭" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="工具" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enable_tools ? 'success' : 'info'">
              {{ row.enable_tools ? "开启" : "关闭" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? "启用" : "停用" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="生效" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="warning">生效</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="base_url" label="Base URL" min-width="220" />
        <el-table-column label="操作" width="440" fixed="right">
          <template #default="{ row }">
            <el-space wrap>
              <el-button
                size="small"
                :type="row.is_default ? 'info' : 'warning'"
                :loading="defaulting === row.id"
                @click="activateProfile(row)"
              >
                {{ row.is_default ? "取消生效" : "设为生效" }}
              </el-button>
              <el-button size="small" type="primary" @click="openWorkbench(row)">对话工作台</el-button>
              <el-button size="small" @click="openEditor(row)">编辑</el-button>
              <el-button size="small" type="success" :loading="testing === row.id" @click="testConnection(row)">
                测试
              </el-button>
              <el-button size="small" @click="openUsage(row)">详情</el-button>
              <el-popconfirm title="确认删除该模型配置？" @confirm="deleteProfile(row)">
                <template #reference>
                  <el-button size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">最近调用历史</div>
            <div class="section__desc">展示最近 10 条 LLM 调用记录，包括联网状态、模式和结果。</div>
          </div>
        </div>
      </template>

      <el-table :data="recentUsage" stripe size="small" v-loading="usageLoading">
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="content_type" label="内容类型" width="100">
          <template #default="{ row }">{{ translateContentType(row.content_type) }}</template>
        </el-table-column>
        <el-table-column prop="content_title" label="标题" min-width="220" />
        <el-table-column prop="provider" label="供应商" width="160">
          <template #default="{ row }">{{ translateProvider(row.provider) }}</template>
        </el-table-column>
        <el-table-column prop="model" label="模型" width="180" />
        <el-table-column label="联网" width="90">
          <template #default="{ row }">
            <el-tag :type="row.web_search_enabled ? 'success' : 'info'">
              {{ row.web_search_enabled ? "开" : "关" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="模式" width="120">
          <template #default="{ row }">
            <el-tag :type="webSearchTagType(row.web_search_mode)">{{ translateWebSearchMode(row.web_search_mode) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="prompt_tokens" label="提示词 Token" width="120" />
        <el-table-column prop="completion_tokens" label="回复 Token" width="110" />
        <el-table-column prop="total_tokens" label="总 Token" width="100" />
        <el-table-column label="成功" width="90">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? "是" : "否" }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="editorVisible" :title="form.id ? '编辑模型配置' : '新增模型配置'" width="760px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="例如：百炼主模型" />
        </el-form-item>
        <el-form-item label="供应商" required>
          <el-select
            v-model="form.provider"
            style="width: 100%"
            filterable
            allow-create
            default-first-option
            placeholder="选择供应商或直接输入自定义值"
          >
            <el-option
              v-for="option in providerOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="form.base_url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" placeholder="sk-..." type="password" show-password />
        </el-form-item>
        <el-form-item label="模型名" required>
          <el-input v-model="form.model_name" placeholder="例如：qwen-plus、deepseek-chat" />
        </el-form-item>
        <el-form-item label="联网搜索">
          <el-switch v-model="form.enable_web_search" />
        </el-form-item>
        <el-form-item label="推理">
          <el-switch v-model="form.enable_reasoning" />
        </el-form-item>
        <el-form-item label="图片">
          <el-switch v-model="form.enable_image" />
        </el-form-item>
        <el-form-item label="工具使用">
          <el-switch v-model="form.enable_tools" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="生效">
          <el-switch v-model="form.is_default" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" placeholder="可选备注" />
        </el-form-item>
        <el-alert
          title="说明：联网、推理、图片、工具均为模型级能力开关，默认按关闭处理。"
          type="info"
          show-icon
          :closable="false"
        />
      </el-form>
      <template #footer>
        <el-button :loading="formTesting" @click="testCurrentConfig">测试当前配置</el-button>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveProfile">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="usageVisible" title="模型详情" size="42%">
      <template v-if="usageTarget">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="名称">{{ usageTarget.name }}</el-descriptions-item>
          <el-descriptions-item label="供应商">{{ translateProvider(usageTarget.provider) }}</el-descriptions-item>
          <el-descriptions-item label="模型名">{{ usageTarget.model_name }}</el-descriptions-item>
          <el-descriptions-item label="联网搜索">
            <el-tag :type="usageTarget.enable_web_search ? 'success' : 'info'">
              {{ usageTarget.enable_web_search ? "开启" : "关闭" }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="推理">
            <el-tag :type="usageTarget.enable_reasoning ? 'success' : 'info'">
              {{ usageTarget.enable_reasoning ? "开启" : "关闭" }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="图片">
            <el-tag :type="usageTarget.enable_image ? 'success' : 'info'">
              {{ usageTarget.enable_image ? "开启" : "关闭" }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="工具使用">
            <el-tag :type="usageTarget.enable_tools ? 'success' : 'info'">
              {{ usageTarget.enable_tools ? "开启" : "关闭" }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="联网模式">
            <el-tag :type="webSearchTagType(usageTarget.web_search_mode)">{{ translateWebSearchMode(usageTarget.web_search_mode) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="联网支持">
            <el-tag :type="usageTarget.web_search_supported ? 'success' : 'danger'">
              {{ usageTarget.web_search_supported ? "支持联网" : "不支持联网" }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Base URL">{{ usageTarget.base_url || "-" }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ usageTarget.notes || "-" }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="usageTarget.is_active ? 'success' : 'info'">{{ usageTarget.is_active ? "启用" : "停用" }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="生效">
            <el-tag v-if="usageTarget.is_default" type="warning">生效</el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">最近调用</el-divider>
        <el-table :data="profileUsageRows" size="small" stripe>
          <el-table-column prop="created_at" label="时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="content_title" label="标题" min-width="160" />
          <el-table-column label="联网" width="80">
            <template #default="{ row }">
              <el-tag :type="row.web_search_enabled ? 'success' : 'info'">
                {{ row.web_search_enabled ? "开" : "关" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="web_search_mode" label="模式" width="120">
            <template #default="{ row }">
              <el-tag :type="webSearchTagType(row.web_search_mode)">{{ translateWebSearchMode(row.web_search_mode) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="success" label="成功" width="80">
            <template #default="{ row }">
              <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? "是" : "否" }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>

    <el-dialog v-model="testResultVisible" title="测试结果" width="760px">
      <template v-if="testResult">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="状态">{{ testResult.message }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ testResult.elapsed_seconds?.toFixed(2) || "-" }}s</el-descriptions-item>
          <el-descriptions-item label="联网模式">{{ testResult.web_search_mode || "-" }}</el-descriptions-item>
          <el-descriptions-item label="Prompt">
            <pre class="summary-box test-result-box">{{ testResult.prompt_text || "-" }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="Response">
            <pre class="summary-box test-result-box">{{ testResult.response_text || "-" }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </template>
      <template #footer>
        <el-button type="primary" @click="testResultVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Message } from "@arco-design/web-vue";

import { api } from "../api";
import type {
  LLMChatMessage,
  LLMConnectionTestResponse,
  LLMProfileDetail,
  LLMModelProfileItem,
  LlmUsageItem,
} from "../types";
import { formatDateTime, translateContentType, translateProvider, translateWebSearchMode } from "../utils";

type ChatMessageView = LLMChatMessage & {
  streaming?: boolean;
  status?: "streaming" | "done" | "error" | "stopped";
  error?: string;
};

const providerOptions = [
  { label: "阿里云百炼", value: "aliyun_bailian" },
  { label: "OpenAI", value: "openai" },
  { label: "OpenAI 兼容", value: "openai-compatible" },
  { label: "Anthropic Claude", value: "anthropic" },
  { label: "Google Gemini", value: "gemini" },
  { label: "Google Vertex AI", value: "vertex_ai" },
  { label: "Azure OpenAI", value: "azure_openai" },
  { label: "AWS Bedrock", value: "bedrock" },
  { label: "Mistral", value: "mistral" },
  { label: "Cohere", value: "cohere" },
  { label: "Perplexity", value: "perplexity" },
  { label: "xAI Grok", value: "xai" },
  { label: "Together AI", value: "together" },
  { label: "OpenRouter", value: "openrouter" },
  { label: "Fireworks AI", value: "fireworks" },
  { label: "DeepSeek", value: "deepseek" },
  { label: "豆包", value: "doubao" },
  { label: "Kimi", value: "kimi" },
  { label: "智谱", value: "zhipu" },
  { label: "MiniMax", value: "minimax" },
  { label: "腾讯混元", value: "hunyuan" },
  { label: "百度千帆", value: "qianfan" },
  { label: "讯飞星火", value: "xinghuo" },
  { label: "小米 MiMo", value: "xiaomi" },
  { label: "华为盘古", value: "pangu" },
  { label: "本地 / Ollama / vLLM", value: "local" },
];

const models = ref<LLMModelProfileItem[]>([]);
const recentUsage = ref<LlmUsageItem[]>([]);
const loading = ref(false);
const saving = ref(false);
const testing = ref<number | null>(null);
const formTesting = ref(false);
const defaulting = ref<number | null>(null);
const usageLoading = ref(false);
const editorVisible = ref(false);
const usageVisible = ref(false);
const testResultVisible = ref(false);
const usageTarget = ref<LLMModelProfileItem | null>(null);
const testResult = ref<LLMConnectionTestResponse | null>(null);
const selectedRows = ref<LLMModelProfileItem[]>([]);
const router = useRouter();

const form = ref(prepareEmptyForm());

const defaultCount = computed(() => models.value.filter((row) => row.is_default).length);
const webSearchCount = computed(() => models.value.filter((row) => row.enable_web_search).length);
const reasoningCount = computed(() => models.value.filter((row) => row.enable_reasoning).length);
const imageCount = computed(() => models.value.filter((row) => row.enable_image).length);
const toolsCount = computed(() => models.value.filter((row) => row.enable_tools).length);
const selectedCount = computed(() => selectedRows.value.length);
const successRateLabel = computed(() => {
  const total = recentUsage.value.length;
  if (!total) return "-";
  const success = recentUsage.value.filter((row) => row.success).length;
  return `${Math.round((success / total) * 100)}%`;
});
const profileUsageRows = computed(() => {
  if (!usageTarget.value) return [];
  return recentUsage.value.filter(
    (row) => row.provider === usageTarget.value?.provider && row.model === usageTarget.value?.model_name,
  );
});

function prepareEmptyForm(): LLMProfileDetail & { api_key: string } {
  return {
    id: 0,
    name: "",
    provider: "aliyun_bailian",
    base_url: "",
    api_key: "",
    model_name: "",
    enable_web_search: false,
    enable_reasoning: false,
    enable_image: false,
    enable_tools: false,
    web_search_mode: "disabled",
    web_search_supported: false,
    is_active: true,
    is_default: false,
    notes: "",
    created_at: null,
    updated_at: null,
  };
}

function normalizeModelPayload(data: LLMProfileDetail & { api_key: string }) {
  return {
    name: data.name,
    provider: data.provider,
    base_url: data.base_url || "",
    api_key: data.api_key || "",
    model_name: data.model_name,
    enable_web_search: !!data.enable_web_search,
    enable_reasoning: !!data.enable_reasoning,
    enable_image: !!data.enable_image,
    enable_tools: !!data.enable_tools,
    is_active: !!data.is_active,
    is_default: !!data.is_default,
    notes: data.notes || "",
  };
}

function webSearchTagType(mode?: string | null): "info" | "success" | "warning" | "danger" {
  if (!mode || mode === "disabled") return "info";
  if (mode === "responses") return "success";
  if (mode === "chat_completions") return "warning";
  if (mode === "unsupported") return "danger";
  return "info";
}

async function openEditor(row: LLMModelProfileItem | null) {
  try {
    if (!row) {
      form.value = prepareEmptyForm();
      editorVisible.value = true;
      return;
    }
    const detail = await api.get<LLMProfileDetail>(`/llm/profiles/${row.id}`);
    form.value = { ...detail, api_key: detail.api_key || "" };
    editorVisible.value = true;
  } catch (error) {
    Message.error(error instanceof Error ? error.message : "加载模型详情失败");
  }
}

function openWorkbench(row?: LLMModelProfileItem) {
  if (row) {
    router.push({ path: "/llm-chat", query: { modelIds: String(row.id) } });
    return;
  }
  router.push({ path: "/llm-chat" });
}

function openWorkbenchForSelected() {
  const profileIds = selectedRows.value.map((row) => row.id).filter(Boolean);
  if (!profileIds.length) {
    Message.warning("请先勾选要测试的模型");
    return;
  }
  router.push({ path: "/llm-chat", query: { modelIds: profileIds.join(",") } });
}

function onSelectionChange(rows: LLMModelProfileItem[]) {
  selectedRows.value = rows;
}

async function loadModels() {
  loading.value = true;
  try {
    models.value = await api.get<LLMModelProfileItem[]>("/llm/profiles");
  } catch (error) {
    Message.error(error instanceof Error ? error.message : "加载失败");
  } finally {
    loading.value = false;
  }
}

async function loadUsage() {
  usageLoading.value = true;
  try {
    const data = await api.get<{ items: LlmUsageItem[] }>("/llm-usage?page_size=10");
    recentUsage.value = data.items || [];
  } catch (error) {
    Message.error(error instanceof Error ? error.message : "加载调用历史失败");
  } finally {
    usageLoading.value = false;
  }
}

async function saveProfile() {
  if (!form.value.name || !form.value.model_name) {
    Message.warning("请填写名称和模型名");
    return;
  }
  saving.value = true;
  try {
    const payload = normalizeModelPayload(form.value);
    if (form.value.id) {
      await api.put(`/llm/profiles/${form.value.id}`, payload);
    } else {
      await api.post("/llm/profiles", payload);
    }
    Message.success("保存成功");
    editorVisible.value = false;
    await loadModels();
  } catch (error) {
    Message.error(error instanceof Error ? error.message : "保存失败");
  } finally {
    saving.value = false;
  }
}

async function deleteProfile(row: LLMModelProfileItem) {
  try {
    await api.delete(`/llm/profiles/${row.id}`);
    Message.success("删除成功");
    await loadModels();
  } catch (error) {
    Message.error(error instanceof Error ? error.message : "删除失败");
  }
}

async function activateProfile(row: LLMModelProfileItem) {
  defaulting.value = row.id;
  try {
    await api.post(`/llm/profiles/${row.id}/activation`, { enabled: !row.is_default });
    Message.success(row.is_default ? "已取消生效" : "已设为生效模型");
    await loadModels();
  } catch (error) {
    Message.error(error instanceof Error ? error.message : "更新生效状态失败");
  } finally {
    defaulting.value = null;
  }
}

async function testConnection(row: LLMModelProfileItem) {
  testing.value = row.id;
  try {
    const res = await api.post<LLMConnectionTestResponse>(`/llm/profiles/${row.id}/test_connection`, {});
    testResult.value = res;
    testResultVisible.value = true;
    if (res.success) {
      Message.success("测试成功");
    } else {
      Message.error(res.message);
    }
  } catch (error) {
    Message.error(error instanceof Error ? error.message : "测试失败");
  } finally {
    testing.value = null;
  }
}

async function testCurrentConfig() {
  formTesting.value = true;
  try {
    const res = await api.post<LLMConnectionTestResponse>("/llm/test_connection", normalizeModelPayload(form.value));
    testResult.value = res;
    testResultVisible.value = true;
    if (res.success) {
      Message.success("测试成功");
    } else {
      Message.error(res.message);
    }
  } catch (error) {
    Message.error(error instanceof Error ? error.message : "测试失败");
  } finally {
    formTesting.value = false;
  }
}

function openUsage(row: LLMModelProfileItem) {
  usageTarget.value = row;
  usageVisible.value = true;
}

onMounted(async () => {
  await Promise.all([loadModels(), loadUsage()]);
});
</script>
