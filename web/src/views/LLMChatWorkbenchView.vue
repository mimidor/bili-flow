<template>
  <div class="llm-workbench">
    <section class="hero-card llm-workbench-hero">
      <div class="hero-copy">
        <div class="hero-eyebrow">LLM WORKBENCH</div>
        <h1>对话工作台</h1>
        <p class="hero-description">
          当前会话会自动保存到数据库，左侧可切换历史会话，右侧保留参数面板。每个会话拥有独立的模型选择、system prompt、temperature 与 max_tokens。
        </p>
      </div>
      <div class="hero-panel llm-workbench-hero-panel">
        <div class="hero-panel__label">当前会话</div>
        <div class="hero-panel__value">{{ currentSession?.title || "新会话" }}</div>
        <div class="hero-panel__meta">
          {{ currentSessionMeta }}
        </div>
        <div class="hero-panel__actions">
          <el-button size="small" type="primary" :disabled="sending" @click="createNewSession">
            新建会话
          </el-button>
          <el-button size="small" :disabled="!currentSessionKey || sending" @click="duplicateCurrentSession">
            复制
          </el-button>
        </div>
      </div>
    </section>

    <div v-if="isMobile" class="llm-mobile-nav">
      <div class="llm-mobile-nav__label">快速切换</div>
      <el-radio-group v-model="mobileSection" class="llm-mobile-nav__group" size="small">
        <el-radio-button label="sessions">会话</el-radio-button>
        <el-radio-button label="chat">对话</el-radio-button>
        <el-radio-button label="params">参数</el-radio-button>
      </el-radio-group>
    </div>

    <div class="llm-workbench-layout">
      <aside ref="sessionPaneRef" class="llm-workbench-sidebar">
        <el-card class="page-card llm-session-card" shadow="never">
          <template #header>
            <div class="section-header section-header--compact">
              <div>
                <div class="section__title">会话</div>
                <div class="section__desc">支持搜索、恢复、重命名、复制、清空和删除。</div>
              </div>
              <el-space wrap>
                <el-button size="small" type="primary" :disabled="sending" @click="createNewSession">新建</el-button>
              </el-space>
            </div>
          </template>

          <div class="llm-session-toolbar">
            <el-input
              v-model="sessionQuery"
              clearable
              placeholder="搜索会话标题或 session key"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>

          <div class="llm-current-session-card">
            <div class="llm-current-session-card__header">
              <div>
                <div class="llm-current-session-card__label">当前会话</div>
                <div class="llm-current-session-card__title">
                  {{ currentSession?.title || "新会话" }}
                </div>
              </div>
              <el-tag size="small" type="success" effect="plain">{{ activeTurnCount }} 轮</el-tag>
            </div>
            <div class="llm-current-session-card__meta">
              <span>{{ currentSession?.source || "workbench" }}</span>
              <span>{{ selectedModelIds.length }} 模型</span>
              <span>{{ formatDateTime(currentSession?.updated_at) }}</span>
            </div>
            <div class="llm-current-session-card__actions">
              <el-button size="small" :disabled="!currentSessionKey || sending" @click="renameCurrentSession">
                重命名
              </el-button>
              <el-button size="small" :disabled="!currentSessionKey || sending" @click="clearCurrentSession">
                清空
              </el-button>
              <el-popconfirm
                title="确认删除当前会话？删除后无法恢复。"
                confirm-button-text="删除"
                cancel-button-text="取消"
                @confirm="deleteCurrentSession"
              >
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!currentSessionKey || sending">删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>

          <el-scrollbar class="llm-session-scroll">
            <div v-if="sessionLoading" class="llm-inline-empty">
              <el-skeleton :rows="5" animated />
            </div>
            <div v-else-if="filteredSessions.length" class="llm-session-list">
              <button
                v-for="item in filteredSessions"
                :key="item.session_key"
                type="button"
                class="llm-session-item"
                :class="{ 'is-active': item.session_key === currentSessionKey }"
                :disabled="sending"
                @click="openSession(item.session_key)"
              >
                <div class="llm-session-item__top">
                  <div class="llm-session-item__title">{{ item.title }}</div>
                  <el-tag size="small" effect="plain">{{ item.turns_count }} 轮</el-tag>
                </div>
                <div class="llm-session-item__meta">
                  <span>{{ item.source || "workbench" }}</span>
                  <span>{{ formatDateTime(item.last_turn_at || item.updated_at) }}</span>
                </div>
                <div class="llm-session-item__chips">
                  <el-tag v-if="item.model_ids.length" size="small" type="info" effect="plain">
                    {{ item.model_ids.length }} 模型
                  </el-tag>
                  <el-tag v-if="item.system_prompt" size="small" type="warning" effect="plain">有提示词</el-tag>
                  <el-tag size="small" type="success" effect="plain">
                    {{ item.temperature.toFixed(1) }} / {{ item.max_tokens }}
                  </el-tag>
                </div>
              </button>
            </div>
            <el-empty v-else :description="sessionQuery ? '没有匹配的会话' : '还没有会话'" />
          </el-scrollbar>
        </el-card>

        <el-card class="page-card llm-model-card" shadow="never">
          <template #header>
            <div class="section-header section-header--compact">
              <div>
                <div class="section__title">模型库</div>
                <div class="section__desc">勾选多个模型后，可在当前会话里并行对比输出。</div>
              </div>
              <el-space wrap>
                <el-button size="small" text type="primary" :disabled="sending" @click="selectDefaultModels">
                  默认
                </el-button>
                <el-button size="small" text :disabled="sending" @click="clearModelSelection">
                  清空
                </el-button>
              </el-space>
            </div>
          </template>

          <div class="llm-model-toolbar">
            <el-input v-model="modelQuery" clearable placeholder="搜索模型名称、供应商或 model name">
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>

          <div class="llm-selected-strip">
            <span class="llm-selected-strip__label">已选 {{ selectedModelIds.length }} 个模型</span>
            <div class="llm-selected-strip__chips">
              <el-tag v-for="profile in selectedProfiles" :key="profile.id" size="small" effect="plain" type="info">
                {{ profile.name }}
              </el-tag>
            </div>
          </div>

          <el-scrollbar class="llm-model-scroll">
            <div v-if="filteredProfiles.length" class="llm-model-list">
              <button
                v-for="profile in filteredProfiles"
                :key="profile.id"
                type="button"
                class="llm-model-item"
                :class="{
                  'is-selected': selectedModelIds.includes(profile.id),
                  'is-inactive': !profile.is_active,
                  'is-sending': sending,
                }"
                :disabled="sending"
                @click="toggleModelSelection(profile.id)"
              >
                <div class="llm-model-item__check">
                  <span v-if="selectedModelIds.includes(profile.id)">✓</span>
                </div>
                <div class="llm-model-item__body">
                  <div class="llm-model-item__title">
                    <span>{{ profile.name }}</span>
                    <el-tag v-if="profile.is_default" size="small" type="warning" effect="plain">默认</el-tag>
                  </div>
                  <div class="llm-model-item__meta">
                    <span>{{ translateProvider(profile.provider) }}</span>
                    <span>{{ profile.model_name }}</span>
                  </div>
                  <div class="llm-model-item__tags">
                    <el-tag size="small" :type="profile.is_active ? 'success' : 'info'" effect="plain">
                      {{ profile.is_active ? "启用" : "停用" }}
                    </el-tag>
                    <el-tag
                      v-if="profile.enable_reasoning"
                      size="small"
                      type="warning"
                      effect="plain"
                    >
                      推理
                    </el-tag>
                    <el-tag
                      v-if="profile.enable_web_search"
                      size="small"
                      type="success"
                      effect="plain"
                    >
                      联网
                    </el-tag>
                    <el-tag
                      v-if="profile.enable_tools"
                      size="small"
                      type="info"
                      effect="plain"
                    >
                      工具
                    </el-tag>
                  </div>
                </div>
              </button>
            </div>
            <el-empty v-else description="没有可用模型" />
          </el-scrollbar>
        </el-card>
      </aside>

      <main ref="chatPaneRef" class="llm-workbench-main">
        <el-card class="page-card llm-turn-card" shadow="never" v-loading="sessionLoading">
          <template #header>
            <div class="section-header section-header--compact">
              <div>
                <div class="section__title">会话内容</div>
                <div class="section__desc">
                  历史会话会完整恢复当前模型选择、参数和多轮消息。每轮对话可对比多个模型的结构化输出。
                </div>
              </div>
              <el-space wrap>
                <el-tag v-if="sending" type="warning" effect="plain">生成中</el-tag>
                <el-tag v-else-if="sessionSaving" type="info" effect="plain">自动保存中</el-tag>
                <el-tag v-else type="success" effect="plain">已同步</el-tag>
              </el-space>
            </div>
          </template>

          <div v-if="displayTurns.length" ref="turnScrollRef" class="llm-turn-list">
            <article v-for="turn in displayTurns" :key="turn.key" class="llm-turn">
              <div class="llm-turn__header">
                <div>
                  <div class="llm-turn__title">
                    {{ turn.persisted ? `第 ${turn.turnIndex} 轮` : "当前草稿" }}
                  </div>
                  <div class="llm-turn__meta">
                    <span>{{ formatDateTime(turn.createdAt) }}</span>
                    <span>{{ turn.results.length }} 个模型</span>
                  </div>
                </div>
                <el-tag v-if="turn.status === 'streaming'" type="warning" effect="plain">流式生成中</el-tag>
                <el-tag v-else-if="turn.status === 'error'" type="danger" effect="plain">异常</el-tag>
                <el-tag v-else-if="turn.status === 'aborted'" type="info" effect="plain">已停止</el-tag>
                <el-tag v-else type="success" effect="plain">完成</el-tag>
              </div>

              <div class="llm-turn__prompt">
                <div class="llm-turn__prompt-label">用户消息</div>
                <div class="markdown-body" v-html="renderMarkdown(turn.prompt)"></div>
              </div>

                <div class="llm-turn__results">
                  <div v-if="isMobile && turn.results.length > 1" class="llm-result-carousel-hint">
                    左右滑动查看模型对比
                  </div>
                  <section
                    v-for="result in turn.results"
                    :key="result.profileId"
                  class="llm-result-card"
                  :class="`is-${result.status}`"
                >
                  <div class="llm-result-card__header">
                    <div>
                      <div class="llm-result-card__title">{{ result.profileName }}</div>
                      <div class="llm-result-card__meta">
                        <span>{{ translateProvider(result.provider) }}</span>
                        <span>{{ result.modelName }}</span>
                      </div>
                    </div>
                    <div class="llm-result-card__tags">
                      <el-tag
                        size="small"
                        :type="result.status === 'done' ? 'success' : result.status === 'error' ? 'danger' : result.status === 'aborted' ? 'info' : 'warning'"
                        effect="plain"
                      >
                        {{ translateResultStatus(result.status) }}
                      </el-tag>
                      <el-tag v-if="result.fallback" size="small" type="warning" effect="plain">回退</el-tag>
                      <el-tag v-if="result.webSearchMode && result.webSearchMode !== 'disabled'" size="small" type="info" effect="plain">
                        {{ translateWebSearchMode(result.webSearchMode) }}
                      </el-tag>
                    </div>
                  </div>

                  <div class="llm-result-card__summary">
                    <span v-if="result.elapsedSeconds != null">耗时 {{ result.elapsedSeconds.toFixed(2) }}s</span>
                    <span v-if="result.webSearchUsed != null">
                      联网 {{ result.webSearchUsed ? "已用" : "未用" }}
                    </span>
                    <span v-if="result.note">{{ result.note }}</span>
                  </div>

                  <div class="llm-block-list">
                    <template v-if="displayBlocks(result).length">
                      <template v-for="(block, blockIndex) in displayBlocks(result)" :key="block.key || `${block.kind}-${blockIndex}`">
                        <details v-if="block.kind === 'thinking'" class="llm-block llm-block--thinking" :open="false">
                          <summary class="llm-block__summary">思考</summary>
                          <div class="llm-block__body markdown-body" v-html="renderMarkdown(block.text)"></div>
                        </details>

                        <div v-else-if="block.kind === 'tool_call'" class="llm-block llm-block--tool-call">
                          <div class="llm-block__summary">工具调用 · {{ block.name }}</div>
                          <div class="llm-block__body markdown-body" v-html="renderMarkdown(formatToolCallBlock(block))"></div>
                        </div>

                        <div v-else-if="block.kind === 'tool_result'" class="llm-block llm-block--tool-result">
                          <div class="llm-block__summary">工具结果 · {{ block.name || "tool" }}</div>
                          <div class="llm-block__body markdown-body" v-html="renderMarkdown(block.content || '-')"></div>
                        </div>

                        <div v-else class="llm-block llm-block--text">
                          <div class="llm-block__summary">回答</div>
                          <div class="llm-block__body markdown-body" v-html="renderMarkdown(block.text || '-')"></div>
                        </div>
                      </template>
                    </template>
                    <div v-else class="llm-result-empty">
                      <el-empty :image-size="72" description="暂无回复内容" />
                    </div>
                  </div>

                  <div v-if="result.error" class="llm-result-error">
                    {{ result.error }}
                  </div>
                </section>
              </div>
            </article>
          </div>

          <el-empty v-else description="当前会话还没有发送过消息" />
        </el-card>

        <el-card class="page-card llm-composer-card" shadow="never">
          <template #header>
            <div class="section-header section-header--compact">
              <div>
                <div class="section__title">输入消息</div>
                <div class="section__desc">Ctrl + Enter 发送，停止后会保留已生成的内容并写回当前会话。</div>
              </div>
              <el-space wrap>
                <el-button :disabled="sending" @click="resetDraft">清空输入</el-button>
                <el-button type="warning" :disabled="!sending" @click="stopGeneration">停止生成</el-button>
                <el-button type="primary" :disabled="sending || !selectedModelIds.length" @click="sendPrompt">
                  发送
                </el-button>
              </el-space>
            </div>
          </template>

          <el-input
            v-model="draftPrompt"
            type="textarea"
            :rows="8"
            resize="none"
            maxlength="12000"
            show-word-limit
            placeholder="输入你的问题，支持多轮上下文和模型对比。"
            :disabled="sending"
            @keydown.ctrl.enter.prevent="sendPrompt"
          />

          <div class="llm-composer__footer">
            <div class="llm-composer__hint">
              <span>当前选中 {{ selectedModelIds.length }} 个模型</span>
              <span v-if="selectedProfiles.length">
                {{ selectedProfiles.map((item) => item.name).join(" · ") }}
              </span>
            </div>
            <div class="llm-composer__actions">
              <el-button :disabled="sending" @click="createNewSession">新建会话</el-button>
              <el-button :disabled="sending" @click="duplicateCurrentSession">复制会话</el-button>
              <el-button type="primary" :disabled="sending || !selectedModelIds.length" @click="sendPrompt">
                发送
              </el-button>
            </div>
          </div>
        </el-card>
      </main>

      <aside ref="paramsPaneRef" class="llm-workbench-inspector">
        <el-card class="page-card llm-inspector-card" shadow="never">
          <template #header>
            <div class="section-header section-header--compact">
              <div>
                <div class="section__title">会话状态</div>
                <div class="section__desc">当前会话的元信息与参数快照。</div>
              </div>
            </div>
          </template>

          <el-descriptions :column="1" border>
            <el-descriptions-item label="标题">{{ currentSession?.title || "新会话" }}</el-descriptions-item>
            <el-descriptions-item label="来源">{{ currentSession?.source || "workbench" }}</el-descriptions-item>
            <el-descriptions-item label="会话 key">{{ currentSessionKey || "-" }}</el-descriptions-item>
            <el-descriptions-item label="轮次">{{ activeTurnCount }}</el-descriptions-item>
            <el-descriptions-item label="最后更新时间">{{ formatDateTime(currentSession?.updated_at) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card class="page-card llm-inspector-card" shadow="never">
          <template #header>
            <div class="section-header section-header--compact">
              <div>
                <div class="section__title">调试参数</div>
                <div class="section__desc">仅影响当前会话，自动保存到数据库。</div>
              </div>
            </div>
          </template>

          <el-form label-position="top" class="llm-inspector-form">
            <el-form-item label="System Prompt">
              <el-input
                v-model="systemPrompt"
                type="textarea"
                :rows="8"
                resize="none"
                maxlength="4000"
                show-word-limit
                :disabled="sending"
                placeholder="可填写角色设定、输出格式、风格约束等"
              />
            </el-form-item>
            <el-form-item label="Temperature">
              <el-input-number
                v-model="temperature"
                :min="0"
                :max="2"
                :step="0.1"
                :precision="1"
                :disabled="sending"
              />
            </el-form-item>
            <el-form-item label="Max Tokens">
              <el-input-number
                v-model="maxTokens"
                :min="1"
                :max="32768"
                :step="128"
                :disabled="sending"
              />
            </el-form-item>
            <el-form-item label="上下文轮数">
              <el-input-number
                v-model="contextTurnLimit"
                :min="1"
                :max="20"
                :step="1"
                :disabled="sending"
              />
            </el-form-item>
          </el-form>
        </el-card>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
// @ts-nocheck
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search } from "@element-plus/icons-vue";

import { api } from "../api";
import type {
  LLMChatCompareResult,
  LLMChatMessage,
  LLMChatSessionCreateRequest,
  LLMChatSessionDetail,
  LLMChatSessionItem,
  LLMChatSessionTurnCreateRequest,
  LLMChatStreamEvent,
  LLMChatStructuredBlock,
  LLMModelProfileItem,
  PageResult,
} from "../types";
import { renderSimpleMarkdown } from "../utils/markdown";

type SessionTurnView = {
  key: string;
  turnIndex?: number | null;
  prompt: string;
  results: LLMChatCompareResult[];
  createdAt?: string | null;
  updatedAt?: string | null;
  persisted: boolean;
  status: "streaming" | "done" | "error" | "aborted";
};

const route = useRoute();
const router = useRouter();

const profiles = ref<LLMModelProfileItem[]>([]);
const sessions = ref<LLMChatSessionItem[]>([]);
const currentSession = ref<LLMChatSessionItem | null>(null);
const currentTurns = ref<SessionTurnView[]>([]);

const sessionQuery = ref("");
const modelQuery = ref("");
const sessionLoading = ref(false);
const profilesLoading = ref(false);
const sessionSaving = ref(false);
const sending = ref(false);
const draftPrompt = ref("");
const systemPrompt = ref("");
const temperature = ref(0.3);
const maxTokens = ref(2048);
const selectedModelIds = ref<number[]>([]);
const contextTurnLimit = ref(5);
const currentSessionKey = ref("");
const draftTurn = ref<SessionTurnView | null>(null);
const turnScrollRef = ref<HTMLElement | null>(null);
const chatAbortController = ref<AbortController | null>(null);
const sessionSyncTimer = ref<number | null>(null);
const sessionSearchTimer = ref<number | null>(null);
const sessionHydrating = ref(false);
const viewportWidth = ref(typeof window !== "undefined" ? window.innerWidth : 1440);
const mobileSection = ref<"sessions" | "chat" | "params">("chat");
const sessionPaneRef = ref<HTMLElement | null>(null);
const chatPaneRef = ref<HTMLElement | null>(null);
const paramsPaneRef = ref<HTMLElement | null>(null);

const isMobile = computed(() => viewportWidth.value <= 768);

const profileMap = computed(() => new Map(profiles.value.map((item) => [item.id, item])));
const selectedProfiles = computed(() =>
  selectedModelIds.value.map((id) => profileMap.value.get(id)).filter(Boolean) as LLMModelProfileItem[],
);
const filteredProfiles = computed(() => {
  const query = modelQuery.value.trim().toLowerCase();
  const list = [...profiles.value].sort((a, b) => {
    const activeDiff = Number(b.is_active) - Number(a.is_active);
    if (activeDiff) return activeDiff;
    const defaultDiff = Number(b.is_default) - Number(a.is_default);
    if (defaultDiff) return defaultDiff;
    return a.id - b.id;
  });
  if (!query) return list;
  return list.filter((item) => {
    const haystack = [item.name, item.provider, item.model_name, item.base_url, item.notes]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
});

const filteredSessions = computed(() => {
  const query = sessionQuery.value.trim().toLowerCase();
  const list = [...sessions.value].sort(compareSessionOrder);
  if (!query) return list;
  return list.filter((item) => {
    const haystack = [
      item.title,
      item.session_key,
      item.source,
      item.model_ids.join(","),
      item.system_prompt,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
});

const currentSessionMeta = computed(() => {
  if (!currentSession.value) return "正在准备会话";
  return `${currentSession.value.turns_count} 轮 · ${selectedModelIds.value.length} 模型 · ${formatDateTime(
    currentSession.value.updated_at,
  )}`;
});

const activeTurnCount = computed(() => currentTurns.value.length + (draftTurn.value ? 1 : 0));
const displayTurns = computed(() => {
  const turns = [...currentTurns.value];
  if (draftTurn.value) {
    turns.push(draftTurn.value);
  }
  return turns;
});

function updateViewport() {
  viewportWidth.value = window.innerWidth;
}

function scrollToMobileSection(section: "sessions" | "chat" | "params") {
  const targetMap = {
    sessions: sessionPaneRef,
    chat: chatPaneRef,
    params: paramsPaneRef,
  } as const;
  const wrapper = targetMap[section]?.value;
  const target = wrapper?.querySelector?.(".page-card") as HTMLElement | null;
  if (target) {
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (wrapper) {
    wrapper.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function compareSessionOrder(a: LLMChatSessionItem, b: LLMChatSessionItem): number {
  const aTime = toTimeValue(a.last_turn_at || a.updated_at);
  const bTime = toTimeValue(b.last_turn_at || b.updated_at);
  if (aTime !== bTime) return bTime - aTime;
  return b.id - a.id;
}

function toTimeValue(value?: string | null): number {
  if (!value) return 0;
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const timestamp = toTimeValue(value);
  if (!timestamp) return value;
  const date = new Date(timestamp);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function translateProvider(provider: string): string {
  const map: Record<string, string> = {
    aliyun_bailian: "阿里云百炼",
    "openai-compatible": "OpenAI 兼容",
    deepseek: "DeepSeek",
    doubao: "豆包",
    kimi: "Kimi",
    zhipu: "智谱",
    minimax: "MiniMax",
  };
  return map[provider] || provider || "-";
}

function translateResultStatus(status: string): string {
  const map: Record<string, string> = {
    streaming: "生成中",
    done: "完成",
    error: "异常",
    aborted: "已停止",
  };
  return map[status] || status || "-";
}

function translateWebSearchMode(mode?: string | null): string {
  const map: Record<string, string> = {
    disabled: "联网关闭",
    unsupported: "不支持联网",
    responses: "Responses 联网",
    chat_completions: "Chat 联网",
  };
  if (!mode) return "-";
  return map[mode] || mode;
}

function scheduleSessionSync() {
  if (!currentSessionKey.value || sessionHydrating.value || sending.value) {
    return;
  }
  if (sessionSyncTimer.value) {
    window.clearTimeout(sessionSyncTimer.value);
  }
  sessionSyncTimer.value = window.setTimeout(() => {
    void syncCurrentSession();
  }, 400);
}

function scheduleDraftSave() {
  if (!currentSessionKey.value) {
    return;
  }
  localStorage.setItem(draftStorageKey(currentSessionKey.value), draftPrompt.value || "");
}

function draftStorageKey(sessionKey: string): string {
  return `llm-chat-workbench:draft:${sessionKey}`;
}

function loadDraftForSession(sessionKey: string) {
  draftPrompt.value = localStorage.getItem(draftStorageKey(sessionKey)) || "";
}

function clearDraftForSession(sessionKey: string) {
  localStorage.removeItem(draftStorageKey(sessionKey));
}

function getDefaultModelIds(): number[] {
  const defaultIds = profiles.value.filter((item) => item.is_active && item.is_default).map((item) => item.id);
  if (defaultIds.length) return uniqueIds(defaultIds);
  const activeIds = profiles.value.filter((item) => item.is_active).map((item) => item.id);
  if (activeIds.length) return [activeIds[0]];
  return profiles.value.length ? [profiles.value[0].id] : [];
}

function uniqueIds(values: number[]): number[] {
  const result: number[] = [];
  for (const value of values) {
    const id = Number(value);
    if (!Number.isFinite(id) || id <= 0 || result.includes(id)) continue;
    result.push(id);
  }
  return result;
}

function parseRouteModelIds(): number[] {
  const raw = route.query.modelIds;
  const values = Array.isArray(raw) ? raw : raw ? String(raw).split(",") : [];
  return uniqueIds(values.map((item) => Number(item)).filter((item) => Number.isFinite(item) && item > 0));
}

function buildSessionPayload() {
  const modelIds = selectedModelIds.value.length ? [...selectedModelIds.value] : getDefaultModelIds();
  return {
    title: currentSession.value?.title || "新会话",
    model_ids: modelIds,
    system_prompt: systemPrompt.value || "",
    temperature: Number(temperature.value || 0.3),
    max_tokens: Number(maxTokens.value || 2048),
    source: "workbench",
  } satisfies LLMChatSessionCreateRequest;
}

function buildUpdatePayload() {
  return {
    model_ids: [...selectedModelIds.value],
    system_prompt: systemPrompt.value || "",
    temperature: Number(temperature.value || 0.3),
    max_tokens: Number(maxTokens.value || 2048),
    source: "workbench",
  };
}

function normalizeCompareBlock(block: any): LLMChatStructuredBlock {
  const kind = block?.kind || "text";
  if (kind === "thinking") {
    return {
      kind: "thinking",
      key: block?.key || "thinking",
      text: String(block?.text || block?.reasoning || ""),
    };
  }
  if (kind === "tool_call") {
    return {
      kind: "tool_call",
      key: block?.key || block?.id || `${block?.index ?? 0}-${block?.name || "tool"}`,
      id: block?.id ?? null,
      index: block?.index ?? null,
      name: String(block?.name || "tool"),
      arguments: block?.arguments ?? null,
      partial: block?.partial ?? null,
      status: block?.status ?? null,
    };
  }
  if (kind === "tool_result") {
    return {
      kind: "tool_result",
      key: block?.key || block?.id || `${block?.name || "tool"}-result`,
      id: block?.id ?? null,
      name: block?.name ?? null,
      status: block?.status ?? null,
      content: String(block?.content || ""),
    };
  }
  return {
    kind: "text",
    key: block?.key || "text",
    text: String(block?.text || block?.content || ""),
  };
}

function normalizeCompareResult(raw: any, profile?: LLMModelProfileItem): LLMChatCompareResult {
  const blocks = Array.isArray(raw?.blocks) ? raw.blocks.map(normalizeCompareBlock) : [];
  return {
    profileId: Number(raw?.profileId ?? raw?.profile_id ?? profile?.id ?? 0),
    profileName: String(raw?.profileName ?? raw?.profile_name ?? profile?.name ?? ""),
    provider: String(raw?.provider ?? profile?.provider ?? ""),
    modelName: String(raw?.modelName ?? raw?.model_name ?? profile?.model_name ?? ""),
    status: (raw?.status || "done") as LLMChatCompareResult["status"],
    content: String(raw?.content ?? ""),
    blocks,
    note: String(raw?.note ?? ""),
    error: String(raw?.error ?? ""),
    success: raw?.success ?? null,
    fallback: raw?.fallback ?? null,
    elapsedSeconds: raw?.elapsedSeconds ?? raw?.elapsed_seconds ?? null,
    webSearchMode: raw?.webSearchMode ?? raw?.web_search_mode ?? null,
    webSearchUsed: raw?.webSearchUsed ?? raw?.web_search_used ?? null,
    webSearchFallbackReason: raw?.webSearchFallbackReason ?? raw?.web_search_fallback_reason ?? null,
    hasStructuredStreamParts: Boolean(raw?.hasStructuredStreamParts ?? raw?.has_structured_stream_parts ?? false),
  };
}

function cloneTurnItem(turn: SessionTurnView): SessionTurnView {
  return {
    key: turn.key,
    turnIndex: turn.turnIndex,
    prompt: turn.prompt,
    results: turn.results.map((result) => ({
      ...result,
      blocks: result.blocks.map((block) => ({ ...block })),
    })),
    createdAt: turn.createdAt,
    updatedAt: turn.updatedAt,
    persisted: turn.persisted,
    status: turn.status,
  };
}

function turnItemToView(turn: any): SessionTurnView {
  const results = Array.isArray(turn?.model_results)
    ? turn.model_results.map((item: any) => normalizeCompareResult(item, profileMap.value.get(Number(item?.profileId ?? item?.profile_id))))
    : [];
  return {
    key: `turn-${turn?.id ?? turn?.turn_index ?? Math.random().toString(36).slice(2)}`,
    turnIndex: turn?.turn_index ?? null,
    prompt: String(turn?.user_prompt || ""),
    results,
    createdAt: turn?.created_at || null,
    updatedAt: turn?.updated_at || null,
    persisted: true,
    status: "done",
  };
}

function displayBlocks(result: LLMChatCompareResult): LLMChatStructuredBlock[] {
  if (result.blocks.length) {
    return result.blocks;
  }
  if (result.content) {
    return [{ kind: "text", key: "text", text: result.content }];
  }
  return [];
}

function renderMarkdown(text?: string | null): string {
  return renderSimpleMarkdown(text || "", {
    emptyHtml: '<p class="markdown-empty">-</p>',
    autoNestList: true,
  });
}

function formatToolCallBlock(block: LLMChatStructuredBlock): string {
  if (block.kind !== "tool_call") return "-";
  const pieces: string[] = [];
  if (block.arguments) {
    pieces.push("```json");
    pieces.push(prettyJson(block.arguments));
    pieces.push("```");
  }
  if (!pieces.length) {
    pieces.push("-");
  }
  return pieces.join("\n");
}

function prettyJson(value: string): string {
  const text = String(value || "").trim();
  if (!text) return "";
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

function mergeBlockList(existing: LLMChatStructuredBlock[], incoming: LLMChatStructuredBlock[]): LLMChatStructuredBlock[] {
  const map = new Map<string, LLMChatStructuredBlock>();
  const order: string[] = [];
  const register = (block: LLMChatStructuredBlock) => {
    const key =
      block.key ||
      (block.kind === "tool_call"
        ? `tool_call-${block.id || block.index || block.name}`
        : block.kind === "tool_result"
          ? `tool_result-${block.id || block.name}`
          : block.kind);
    if (!map.has(key)) {
      order.push(key);
    }
    map.set(key, { ...block, key });
  };
  existing.forEach(register);
  incoming.forEach(register);
  return order.map((key) => map.get(key)!).filter(Boolean);
}

function appendBlockText(blocks: LLMChatStructuredBlock[], kind: LLMChatStructuredBlock["kind"], text: string) {
  if (!text) return blocks;
  const key = kind === "text" ? "text" : kind;
  const existingIndex = blocks.findIndex((block) => block.key === key && block.kind === kind);
  const nextBlock: LLMChatStructuredBlock = kind === "thinking"
    ? { kind, key, text }
    : kind === "tool_call"
      ? { kind, key, id: null, index: null, name: "tool", arguments: text, partial: false, status: "streaming" }
      : kind === "tool_result"
        ? { kind, key, id: null, name: "tool", status: "streaming", content: text }
        : { kind: "text", key, text };
  if (existingIndex >= 0) {
    const current = blocks[existingIndex];
    if (kind === "thinking" && current.kind === "thinking") {
      blocks[existingIndex] = { ...current, text: `${current.text || ""}${text}` };
    } else if (kind === "text" && current.kind === "text") {
      blocks[existingIndex] = { ...current, text: `${current.text || ""}${text}` };
    } else {
      blocks[existingIndex] = nextBlock;
    }
  } else {
    blocks.push(nextBlock);
  }
  return blocks;
}

function makeEmptyResult(profile: LLMModelProfileItem): LLMChatCompareResult {
  return {
    profileId: profile.id,
    profileName: profile.name,
    provider: profile.provider,
    modelName: profile.model_name,
    status: "streaming",
    content: "",
    blocks: [],
    note: "等待模型返回",
    error: "",
    success: null,
    fallback: null,
    elapsedSeconds: null,
    webSearchMode: null,
    webSearchUsed: null,
    webSearchFallbackReason: null,
    hasStructuredStreamParts: false,
  };
}

function buildMessagesForProfile(profileId: number, prompt: string): LLMChatMessage[] {
  const messages: LLMChatMessage[] = [];
  if (systemPrompt.value.trim()) {
    messages.push({ role: "system", content: systemPrompt.value.trim() });
  }
  const limit = Math.max(1, Number(contextTurnLimit.value) || 5);
  const turns = currentTurns.value.slice(-limit);
  for (const turn of turns) {
    messages.push({ role: "user", content: turn.prompt });
    const result = turn.results.find((item) => item.profileId === profileId);
    const assistantText = normalizeAssistantContent(result);
    if (assistantText) {
      messages.push({ role: "assistant", content: assistantText });
    }
  }
  messages.push({ role: "user", content: prompt });
  return messages;
}

function normalizeAssistantContent(result?: LLMChatCompareResult | null): string {
  if (!result) return "";
  if (result.content && result.content.trim()) {
    return result.content.trim();
  }
  const textPieces = result.blocks
    .filter((block) => block.kind === "text" && block.text)
    .map((block) => block.text)
    .filter(Boolean);
  return textPieces.join("\n").trim();
}

async function loadProfiles() {
  profilesLoading.value = true;
  try {
    const items = await api.get<LLMModelProfileItem[]>("/llm/profiles");
    profiles.value = [...items].sort((a, b) => {
      const defaultDiff = Number(b.is_default) - Number(a.is_default);
      if (defaultDiff) return defaultDiff;
      const activeDiff = Number(b.is_active) - Number(a.is_active);
      if (activeDiff) return activeDiff;
      return a.id - b.id;
    });
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载模型失败");
  } finally {
    profilesLoading.value = false;
  }
}

async function loadSessions(query = sessionQuery.value) {
  sessionLoading.value = true;
  try {
    const url = `/llm/chat-sessions?page=1&page_size=200${query.trim() ? `&q=${encodeURIComponent(query.trim())}` : ""}`;
    const res = await api.get<PageResult<LLMChatSessionItem>>(url);
    sessions.value = [...res.items].sort(compareSessionOrder);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载会话失败");
  } finally {
    sessionLoading.value = false;
  }
}

async function openSession(sessionKey: string) {
  if (!sessionKey) return;
  if (sending.value) {
    ElMessage.warning("当前会话正在生成，请先停止后再切换会话");
    return;
  }
  sessionHydrating.value = true;
  try {
    const detail = await api.get<LLMChatSessionDetail>(`/llm/chat-sessions/${sessionKey}`);
    applySessionDetail(detail);
    router.replace({ path: "/llm-chat", query: { sessionKey } });
  } catch (error) {
    if (error instanceof Error && /404/.test(error.message)) {
      ElMessage.warning("会话已被删除，已创建新会话");
      await createNewSession();
      return;
    }
    ElMessage.error(error instanceof Error ? error.message : "打开会话失败");
  } finally {
    sessionHydrating.value = false;
  }
}

function applySessionDetail(detail: LLMChatSessionDetail) {
  currentSession.value = { ...detail.session, model_ids: [...detail.session.model_ids] };
  currentSessionKey.value = detail.session.session_key;
  currentTurns.value = detail.turns.map((turn) => cloneTurnItem(turnItemToView(turn)));
  selectedModelIds.value = uniqueIds(detail.session.model_ids || []);
  systemPrompt.value = detail.session.system_prompt || "";
  temperature.value = Number(detail.session.temperature ?? 0.3);
  maxTokens.value = Number(detail.session.max_tokens ?? 2048);
  loadDraftForSession(detail.session.session_key);
  refreshSessionInList(detail.session);
}

function refreshSessionInList(session: LLMChatSessionItem) {
  const index = sessions.value.findIndex((item) => item.session_key === session.session_key);
  const nextItem = { ...session, model_ids: [...session.model_ids] };
  if (index >= 0) {
    sessions.value.splice(index, 1, nextItem);
  } else {
    sessions.value.push(nextItem);
  }
  sessions.value.sort(compareSessionOrder);
}

async function createSession(payload?: Partial<LLMChatSessionCreateRequest>) {
  const body: LLMChatSessionCreateRequest = {
    title: payload?.title || "新会话",
    model_ids: uniqueIds(payload?.model_ids || (selectedModelIds.value.length ? [...selectedModelIds.value] : getDefaultModelIds())),
    system_prompt: payload?.system_prompt ?? systemPrompt.value ?? "",
    temperature: payload?.temperature ?? temperature.value ?? 0.3,
    max_tokens: payload?.max_tokens ?? maxTokens.value ?? 2048,
    source: payload?.source || "workbench",
  };
  const item = await api.post<LLMChatSessionItem>("/llm/chat-sessions", body);
  refreshSessionInList(item);
  return item;
}

async function createNewSession() {
  if (sending.value) {
    ElMessage.warning("当前会话正在生成，请先停止后再新建会话");
    return;
  }
  try {
    sessionHydrating.value = true;
    const item = await createSession({
      title: "新会话",
      model_ids: selectedModelIds.value.length ? selectedModelIds.value : getDefaultModelIds(),
    });
    currentSession.value = item;
    currentSessionKey.value = item.session_key;
    currentTurns.value = [];
    selectedModelIds.value = uniqueIds(item.model_ids || []);
    systemPrompt.value = item.system_prompt || "";
    temperature.value = Number(item.temperature ?? 0.3);
    maxTokens.value = Number(item.max_tokens ?? 2048);
    draftPrompt.value = "";
    clearDraftForSession(item.session_key);
    router.replace({ path: "/llm-chat", query: { sessionKey: item.session_key } });
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "创建会话失败");
  } finally {
    sessionHydrating.value = false;
  }
}

async function renameCurrentSession() {
  if (!currentSessionKey.value) return;
  try {
    const { value } = await ElMessageBox.prompt("请输入新的会话标题", "重命名会话", {
      confirmButtonText: "保存",
      cancelButtonText: "取消",
      inputValue: currentSession.value?.title || "",
      inputPlaceholder: "会话标题",
      inputValidator: (input: string) => {
        if (!input.trim()) return "标题不能为空";
        return true;
      },
    });
    const item = await api.put<LLMChatSessionItem>(`/llm/chat-sessions/${currentSessionKey.value}`, {
      title: value.trim(),
    });
    currentSession.value = item;
    refreshSessionInList(item);
    ElMessage.success("已重命名");
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    if (error instanceof Error && error.message.includes("cancel")) return;
    if (error instanceof Error && error.message.includes("closed")) return;
    if (error instanceof Error && error.message.includes("prompt cancel")) return;
    if (typeof error === "object" && error !== null && "value" in error) return;
    if (error instanceof Error) {
      ElMessage.error(error.message);
    }
  }
}

async function duplicateCurrentSession() {
  if (!currentSessionKey.value) return;
  if (sending.value) {
    ElMessage.warning("当前会话正在生成，请先停止后再复制");
    return;
  }
  try {
    const detail = await api.post<LLMChatSessionDetail>(`/llm/chat-sessions/${currentSessionKey.value}/duplicate`, {});
    applySessionDetail(detail);
    router.replace({ path: "/llm-chat", query: { sessionKey: detail.session.session_key } });
    ElMessage.success("已复制会话");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "复制会话失败");
  }
}

async function clearCurrentSession() {
  if (!currentSessionKey.value) return;
  if (sending.value) {
    ElMessage.warning("当前会话正在生成，请先停止后再清空");
    return;
  }
  try {
    await ElMessageBox.confirm("确认清空当前会话的所有消息？", "清空会话", {
      confirmButtonText: "清空",
      cancelButtonText: "取消",
      type: "warning",
    });
    const item = await api.post<LLMChatSessionItem>(`/llm/chat-sessions/${currentSessionKey.value}/clear`, {});
    currentSession.value = item;
    currentTurns.value = [];
    refreshSessionInList(item);
    clearDraftForSession(item.session_key);
    ElMessage.success("已清空");
  } catch (error) {
    if (error === "cancel" || error === "close") return;
  }
}

async function deleteCurrentSession() {
  if (!currentSessionKey.value) return;
  if (sending.value) {
    ElMessage.warning("当前会话正在生成，请先停止后再删除");
    return;
  }
  try {
    await api.delete(`/llm/chat-sessions/${currentSessionKey.value}`);
    sessions.value = sessions.value.filter((item) => item.session_key !== currentSessionKey.value);
    clearDraftForSession(currentSessionKey.value);
    currentSession.value = null;
    currentTurns.value = [];
    currentSessionKey.value = "";
    draftPrompt.value = "";
    const fallback = sessions.value[0];
    if (fallback) {
      await openSession(fallback.session_key);
    } else {
      await createNewSession();
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "删除会话失败");
  }
}

async function syncCurrentSession() {
  if (!currentSessionKey.value) return;
  sessionSaving.value = true;
  try {
    const item = await api.put<LLMChatSessionItem>(`/llm/chat-sessions/${currentSessionKey.value}`, buildUpdatePayload());
    currentSession.value = item;
    refreshSessionInList(item);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存会话失败");
  } finally {
    sessionSaving.value = false;
  }
}

function toggleModelSelection(profileId: number) {
  if (sending.value) return;
  if (selectedModelIds.value.includes(profileId)) {
    selectedModelIds.value = selectedModelIds.value.filter((id) => id !== profileId);
  } else {
    selectedModelIds.value = [...selectedModelIds.value, profileId];
  }
  scheduleSessionSync();
}

function clearModelSelection() {
  if (sending.value) return;
  selectedModelIds.value = [];
  scheduleSessionSync();
}

function selectDefaultModels() {
  if (sending.value) return;
  selectedModelIds.value = getDefaultModelIds();
  scheduleSessionSync();
}

function resetDraft() {
  draftPrompt.value = "";
  if (currentSessionKey.value) {
    clearDraftForSession(currentSessionKey.value);
  }
}

function stopGeneration() {
  if (chatAbortController.value) {
    chatAbortController.value.abort();
  }
}

async function sendPrompt() {
  const prompt = draftPrompt.value.trim();
  if (!prompt) {
    ElMessage.warning("请输入要发送的消息");
    return;
  }
  if (!selectedModelIds.value.length) {
    ElMessage.warning("请先选择至少一个模型");
    return;
  }
  if (!currentSessionKey.value) {
    ElMessage.warning("会话未准备好");
    return;
  }
  if (sending.value) {
    return;
  }

  const sessionKeyAtStart = currentSessionKey.value;
  const selectedProfilesSnapshot = [...selectedProfiles.value];
  const draftResults = selectedProfilesSnapshot.map((profile) => makeEmptyResult(profile));
  draftTurn.value = {
    key: `draft-${Date.now()}`,
    prompt,
    results: draftResults,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    persisted: false,
    status: "streaming",
  };
  draftPrompt.value = "";
  clearDraftForSession(sessionKeyAtStart);
  sending.value = true;
  chatErrorCleanup();
  await nextTick();
  scrollTurnsToBottom();

  const controller = new AbortController();
  chatAbortController.value = controller;

  const tasks = selectedProfilesSnapshot.map((profile, index) =>
    runModelChat(profile, prompt, draftResults[index], controller.signal),
  );

  try {
    await Promise.allSettled(tasks);
    if (draftTurn.value) {
      draftTurn.value.status = controller.signal.aborted ? "aborted" : "done";
    }
    const saved = await api.post<{ session: LLMChatSessionItem; turn: any }>(
      `/llm/chat-sessions/${sessionKeyAtStart}/turns`,
      {
        prompt,
        model_results: draftResults,
        model_ids: [...selectedModelIds.value],
        system_prompt: systemPrompt.value || "",
        temperature: Number(temperature.value || 0.3),
        max_tokens: Number(maxTokens.value || 2048),
        source: "workbench",
      } satisfies LLMChatSessionTurnCreateRequest,
    );
    currentSession.value = saved.session;
    refreshSessionInList(saved.session);
    currentTurns.value = [...currentTurns.value, turnItemToView(saved.turn)];
    if (currentSessionKey.value === sessionKeyAtStart) {
      draftTurn.value = null;
      await nextTick();
      scrollTurnsToBottom();
    }
    if (controller.signal.aborted) {
      ElMessage.info("已停止生成，当前轮次已保留");
    } else {
      ElMessage.success("会话已保存");
    }
  } catch (error) {
    if (controller.signal.aborted) {
      try {
        const saved = await api.post<{ session: LLMChatSessionItem; turn: any }>(
          `/llm/chat-sessions/${sessionKeyAtStart}/turns`,
          {
            prompt,
            model_results: draftResults,
            model_ids: [...selectedModelIds.value],
            system_prompt: systemPrompt.value || "",
            temperature: Number(temperature.value || 0.3),
            max_tokens: Number(maxTokens.value || 2048),
            source: "workbench",
          } satisfies LLMChatSessionTurnCreateRequest,
        );
        currentSession.value = saved.session;
        refreshSessionInList(saved.session);
        currentTurns.value = [...currentTurns.value, turnItemToView(saved.turn)];
        draftTurn.value = null;
        ElMessage.info("已停止生成，当前轮次已保留");
      } catch (saveError) {
        ElMessage.error(saveError instanceof Error ? saveError.message : "保存轮次失败");
      }
      return;
    }
    ElMessage.error(error instanceof Error ? error.message : "发送失败");
    if (draftTurn.value) {
      draftTurn.value.status = "error";
    }
  } finally {
    sending.value = false;
    chatAbortController.value = null;
    draftTurn.value = null;
    await nextTick();
    scrollTurnsToBottom();
  }
}

async function runModelChat(
  profile: LLMModelProfileItem,
  prompt: string,
  result: LLMChatCompareResult,
  signal: AbortSignal,
) {
  const messages = buildMessagesForProfile(profile.id, prompt);
  try {
    result.status = "streaming";
    result.note = "流式生成中";
    const response = await api.raw(`/llm/profiles/${profile.id}/chat`, {
      method: "POST",
      body: JSON.stringify({
        messages,
        system_prompt: systemPrompt.value || "",
        temperature: Number(temperature.value || 0.3),
        max_tokens: Number(maxTokens.value || 2048),
      }),
      signal,
    });
    await consumeStream(profile, response, result, signal);
    if (result.status === "streaming") {
      result.status = signal.aborted ? "aborted" : "done";
    }
  } catch (error) {
    if (signal.aborted) {
      result.status = "aborted";
      result.note = "已停止生成";
      result.error = "";
      return;
    }
    result.status = "error";
    result.error = error instanceof Error ? error.message : "请求失败";
    result.note = "调用失败";
  }
}

async function consumeStream(
  profile: LLMModelProfileItem,
  response: Response,
  result: LLMChatCompareResult,
  signal: AbortSignal,
) {
  if (!response.body) {
    throw new Error("响应流不可用");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    if (signal.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() || "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const event = JSON.parse(trimmed) as LLMChatStreamEvent & Record<string, any>;
      applyStreamEvent(profile, result, event);
    }
  }
  const tail = buffer.trim();
  if (tail) {
    const event = JSON.parse(tail) as LLMChatStreamEvent & Record<string, any>;
    applyStreamEvent(profile, result, event);
  }
}

function applyStreamEvent(
  profile: LLMModelProfileItem,
  result: LLMChatCompareResult,
  event: LLMChatStreamEvent & Record<string, any>,
) {
  if (event.type === "meta") {
    result.profileName = event.profile_name || result.profileName || profile.name;
    result.provider = event.provider || result.provider || profile.provider;
    result.modelName = event.model_name || result.modelName || profile.model_name;
    result.webSearchMode = event.web_search_mode ?? result.webSearchMode;
    result.webSearchUsed = event.web_search_used ?? result.webSearchUsed;
    result.webSearchFallbackReason = event.web_search_fallback_reason ?? result.webSearchFallbackReason;
    result.hasStructuredStreamParts = Boolean(event.blocks?.length || result.hasStructuredStreamParts);
    if (event.message) {
      result.note = event.message;
    }
    return;
  }
  if (event.type === "thinking" && (event.text || event.reasoning)) {
    result.hasStructuredStreamParts = true;
    result.blocks = appendOrMergeBlock(result.blocks, {
      kind: "thinking",
      key: "thinking",
      text: String(event.text || event.reasoning || ""),
    });
    result.content = result.content || "";
    return;
  }
  if (event.type === "tool_call" && event.tool_call) {
    result.hasStructuredStreamParts = true;
    result.blocks = appendOrMergeBlock(result.blocks, {
      kind: "tool_call",
      key: event.tool_call.id || `${event.tool_call.index || 0}-${event.tool_call.name || "tool"}`,
      id: event.tool_call.id || null,
      index: event.tool_call.index ?? null,
      name: event.tool_call.name || "tool",
      arguments: event.tool_call.arguments || "",
      partial: event.tool_call.partial ?? false,
      status: event.tool_call.status || "streaming",
    });
    return;
  }
  if (event.type === "tool_result" && event.tool_result) {
    result.hasStructuredStreamParts = true;
    result.blocks = appendOrMergeBlock(result.blocks, {
      kind: "tool_result",
      key: event.tool_result.id || event.tool_result.name || "tool-result",
      id: event.tool_result.id || null,
      name: event.tool_result.name || null,
      status: event.tool_result.status || "done",
      content: String(event.tool_result.content || ""),
    });
    return;
  }
  if (event.type === "delta" && event.text) {
    result.content = `${result.content || ""}${event.text}`;
    result.blocks = appendOrMergeBlock(result.blocks, {
      kind: "text",
      key: "text",
      text: result.content,
    });
    return;
  }
  if (event.type === "done") {
    result.status = event.success === false ? "error" : "done";
    result.success = event.success ?? result.success;
    result.fallback = event.fallback ?? result.fallback;
    result.elapsedSeconds = event.elapsed_seconds ?? result.elapsedSeconds;
    result.webSearchMode = event.web_search_mode ?? result.webSearchMode;
    result.webSearchUsed = event.web_search_used ?? result.webSearchUsed;
    result.webSearchFallbackReason = event.web_search_fallback_reason ?? result.webSearchFallbackReason;
    result.note = event.message || result.note || "完成";
    if (Array.isArray(event.blocks) && event.blocks.length) {
      result.blocks = mergeBlockList(result.blocks, event.blocks.map(normalizeCompareBlock));
    }
    if (event.text && !result.content) {
      result.content = String(event.text || "");
    }
    if (event.reasoning) {
      result.blocks = appendOrMergeBlock(result.blocks, {
        kind: "thinking",
        key: "thinking",
        text: String(event.reasoning || ""),
      });
    }
    return;
  }
  if (event.type === "error") {
    result.status = "error";
    result.success = false;
    result.note = event.message || "异常";
    result.error = event.message || "请求失败";
  }
}

function appendOrMergeBlock(blocks: LLMChatStructuredBlock[], block: LLMChatStructuredBlock): LLMChatStructuredBlock[] {
  const key = block.key || (block.kind === "tool_call" ? `tool_call-${block.id || block.name}` : block.kind);
  const index = blocks.findIndex((item) => (item.key || item.kind) === key);
  const nextBlock = { ...block, key };
  if (index >= 0) {
    const current = blocks[index];
    if (current.kind === "thinking" && nextBlock.kind === "thinking") {
      blocks[index] = { ...current, text: `${current.text || ""}${nextBlock.text || ""}` };
    } else if (current.kind === "text" && nextBlock.kind === "text") {
      blocks[index] = { ...current, text: nextBlock.text || current.text || "" };
    } else {
      blocks[index] = nextBlock;
    }
  } else {
    blocks.push(nextBlock);
  }
  return blocks;
}

function chatErrorCleanup() {
  // 保留预留钩子，后续可以接更细的错误状态展示。
}

function scrollTurnsToBottom() {
  nextTick(() => {
    const el = turnScrollRef.value;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  });
}

watch(sessionQuery, () => {
  if (sessionSearchTimer.value) {
    window.clearTimeout(sessionSearchTimer.value);
  }
  sessionSearchTimer.value = window.setTimeout(() => {
    void loadSessions(sessionQuery.value);
  }, 280);
});

watch(
  () => [selectedModelIds.value.join(","), systemPrompt.value, temperature.value, maxTokens.value, currentSessionKey.value],
  () => {
    scheduleSessionSync();
  },
);

watch(
  () => currentSessionKey.value,
  (value) => {
    if (!value) return;
    loadDraftForSession(value);
  },
);

watch(mobileSection, (value) => {
  if (!isMobile.value) return;
  void nextTick(() => scrollToMobileSection(value));
});

onMounted(async () => {
  updateViewport();
  window.addEventListener("resize", updateViewport, { passive: true });
  await loadProfiles();
  await loadSessions();

  const sessionKey = typeof route.query.sessionKey === "string" ? route.query.sessionKey.trim() : "";
  const routeModelIds = parseRouteModelIds();

  if (sessionKey) {
    await openSession(sessionKey);
    return;
  }

  if (routeModelIds.length) {
    selectedModelIds.value = routeModelIds;
    const item = await createSession({
      title: "新会话",
      model_ids: routeModelIds,
    });
    await openSession(item.session_key);
    return;
  }

  if (sessions.value.length) {
    await openSession(sessions.value[0].session_key);
    return;
  }

  selectedModelIds.value = getDefaultModelIds();
  await createNewSession();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", updateViewport);
  if (sessionSyncTimer.value) {
    window.clearTimeout(sessionSyncTimer.value);
  }
  if (sessionSearchTimer.value) {
    window.clearTimeout(sessionSearchTimer.value);
  }
  if (chatAbortController.value) {
    chatAbortController.value.abort();
    chatAbortController.value = null;
  }
});
</script>

<style scoped>
.llm-mobile-nav {
  display: none;
}

@media (max-width: 768px) {
  .llm-workbench-hero {
    flex-direction: column;
  }

  .llm-workbench-hero-panel {
    min-width: 0;
  }

  .llm-workbench-layout {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .llm-workbench-sidebar,
  .llm-workbench-main,
  .llm-workbench-inspector {
    width: 100%;
    min-width: 0;
  }

  .llm-workbench-sidebar,
  .llm-workbench-main,
  .llm-workbench-inspector {
    display: contents;
  }

  .llm-workbench-layout :deep(.page-card) {
    width: 100%;
  }

  .llm-mobile-nav {
    display: flex;
    flex-direction: column;
    gap: 10px;
    position: sticky;
    top: 0;
    z-index: 5;
    margin: 6px 0 2px;
    padding: 6px 0 8px;
    backdrop-filter: blur(14px);
  }

  .llm-mobile-nav__label {
    font-size: 12px;
    font-weight: 700;
    color: #475569;
  }

  .llm-mobile-nav__group {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    width: 100%;
  }

  :deep(.llm-mobile-nav__group .el-radio-button) {
    width: 100%;
  }

  :deep(.llm-mobile-nav__group .el-radio-button__inner) {
    width: 100%;
  }

  .llm-session-scroll,
  .llm-model-scroll {
    max-height: 360px;
  }

  .llm-current-session-card__header,
  .llm-result-card__header,
  .llm-turn__header,
  .llm-composer__footer,
  .llm-composer__actions,
  .llm-selected-strip,
  .llm-session-item__top,
  .llm-model-item__title {
    flex-direction: column;
    align-items: flex-start;
  }

  .llm-composer__actions,
  .llm-current-session-card__actions {
    width: 100%;
  }

  .llm-composer__actions .el-button,
  .llm-current-session-card__actions .el-button {
    width: 100%;
  }

  .llm-turn__results {
    grid-template-columns: 1fr;
  }

  .llm-result-card__tags {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .llm-turn__results {
    display: flex;
    overflow-x: auto;
    flex-wrap: nowrap;
    gap: 12px;
    scroll-snap-type: x mandatory;
    padding: 2px 2px 10px;
    margin-inline: -2px;
    -webkit-overflow-scrolling: touch;
    overscroll-behavior-x: contain;
    scrollbar-width: none;
    touch-action: pan-x;
  }

  .llm-turn__results::-webkit-scrollbar {
    display: none;
  }

  .llm-result-carousel-hint {
    position: sticky;
    left: 0;
    flex: 0 0 100%;
    font-size: 12px;
    font-weight: 700;
    color: #64748b;
    margin-bottom: -2px;
  }

  .llm-turn__results > .llm-result-card {
    flex: 0 0 min(88vw, 420px);
    scroll-snap-align: start;
  }

  .llm-turn__results > .llm-result-card:last-child {
    margin-right: 2px;
  }

  .llm-block__body {
    max-width: 100%;
    overflow-x: auto;
  }
}
</style>
