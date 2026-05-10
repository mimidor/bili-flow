<template>
  <div class="dashboard qteasy-page">
    <section class="hero-card">
      <div class="hero-copy">
        <div class="hero-eyebrow">QTEASY / STRATEGY CATALOG</div>
        <h1>策略目录</h1>
        <p class="hero-description">
          这里统一展示内置策略和自定义策略。先在目录里确认策略，再把它带入任务工作台，不在这里做在线编辑。
        </p>
      </div>

      <div class="hero-panel">
        <div>
          <div class="hero-panel__label">策略总数</div>
          <div class="hero-panel__value">{{ builtinStrategies.length + customStrategies.length }}</div>
          <div class="hero-panel__meta">内置 {{ builtinStrategies.length }} / 自定义 {{ customStrategies.length }}</div>
        </div>
        <div class="hero-panel__actions">
          <el-button type="primary" :loading="loading.builtin || loading.custom" @click="refreshAll">刷新目录</el-button>
          <el-button @click="$router.push('/qteasy/tasks')">去任务工作台</el-button>
        </div>
      </div>
    </section>

    <div class="health-grid">
      <el-card class="health-card">
        <div class="health-card__title">内置策略</div>
        <div class="health-card__value">{{ builtinStrategies.length }}</div>
        <div class="health-card__meta">/strategies/builtins</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">自定义策略</div>
        <div class="health-card__value">{{ customStrategies.length }}</div>
        <div class="health-card__meta">/strategies/custom</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">当前目录</div>
        <div class="health-card__value">{{ activeTabLabel }}</div>
        <div class="health-card__meta">点击左侧目录查看详情</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">当前策略</div>
        <div class="health-card__value">{{ currentTitle }}</div>
        <div class="health-card__meta">{{ currentSubtitle }}</div>
      </el-card>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="warning" :closable="false" show-icon />

    <div class="chart-grid">
      <el-card class="page-card section">
        <template #header>
          <div class="section-header section-header--space-between">
            <div>
              <div class="section__title">策略目录</div>
              <div class="section__desc">左侧选策略，右侧看摘要、文档和导入路径，再带入任务工作台。</div>
            </div>
          </div>
        </template>

        <el-tabs v-model="activeTab" class="qteasy-tabs">
          <el-tab-pane label="内置策略" name="builtins">
            <el-empty v-if="!builtinStrategies.length && !loading.builtin" description="暂无内置策略" />
            <div v-else class="qteasy-strategy-grid">
              <button
                v-for="strategy in builtinStrategies"
                :key="strategy.strategy_id"
                class="qteasy-strategy-item"
                :class="{ 'is-active': selectedBuiltinId === strategy.strategy_id }"
                type="button"
                @click="loadBuiltinStrategy(strategy.strategy_id)"
              >
                <div class="qteasy-strategy-item__top">
                  <strong>{{ strategy.strategy_id }}</strong>
                  <el-tag size="small" type="info" effect="plain">built-in</el-tag>
                </div>
                <div class="summary-box qteasy-strategy-item__summary">
                  {{ strategy.summary || strategy.doc || strategy.repr || "-" }}
                </div>
              </button>
            </div>
          </el-tab-pane>

          <el-tab-pane label="自定义策略" name="custom">
            <el-empty
              v-if="customUnavailable && !loading.custom"
              description="当前 Qteasy 服务还没有提供 /strategies/custom"
            />
            <el-empty v-else-if="!customStrategies.length && !loading.custom" description="暂无自定义策略" />
            <div v-else class="qteasy-strategy-grid">
              <button
                v-for="strategy in customStrategies"
                :key="strategy.name"
                class="qteasy-strategy-item"
                :class="{ 'is-active': selectedCustomName === strategy.name }"
                type="button"
                @click="loadCustomStrategy(strategy.name)"
              >
                <div class="qteasy-strategy-item__top">
                  <strong>{{ strategy.name }}</strong>
                  <el-tag size="small" type="warning" effect="plain">import</el-tag>
                </div>
                <div class="summary-box qteasy-strategy-item__summary">
                  {{ strategy.summary || strategy.import_path || strategy.class_name || "-" }}
                </div>
              </button>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>

      <el-card class="page-card section">
        <template #header>
          <div class="section-header section-header--space-between">
            <div>
              <div class="section__title">策略详情</div>
              <div class="section__desc">显示摘要、文档和导入路径，便于直接带入任务工作台。</div>
            </div>
            <el-space wrap>
              <el-button v-if="detailKind === 'builtins' && builtinDetail?.strategy_id" text @click="copyText(builtinDetail.strategy_id)">
                复制 strategy_id
              </el-button>
              <el-button v-if="detailKind === 'custom' && customDetail?.import_path" text @click="copyText(customDetail.import_path || '')">
                复制 import_path
              </el-button>
              <el-button v-if="detailKind === 'custom' && customDetail?.class_name" text @click="copyText(customDetail.class_name || '')">
                复制 class_name
              </el-button>
              <el-button type="primary" :disabled="!hasCurrentDetail" @click="goToTaskWorkbench">带入任务</el-button>
            </el-space>
          </div>
        </template>

        <el-empty v-if="!hasCurrentDetail" description="请选择一个策略查看详情" />

        <template v-else-if="detailKind === 'builtins' && builtinDetail">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="strategy_id">{{ builtinDetail.strategy_id }}</el-descriptions-item>
            <el-descriptions-item label="class_name">{{ builtinDetail.class_name || "-" }}</el-descriptions-item>
            <el-descriptions-item label="repr"><span class="summary-box">{{ builtinDetail.repr || "-" }}</span></el-descriptions-item>
            <el-descriptions-item label="summary"><span class="summary-box">{{ builtinDetail.summary || "-" }}</span></el-descriptions-item>
            <el-descriptions-item label="doc"><pre class="summary-box qteasy-result-pre">{{ builtinDetail.doc || "-" }}</pre></el-descriptions-item>
          </el-descriptions>
        </template>

        <template v-else-if="detailKind === 'custom' && customDetail">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="name">{{ customDetail.name }}</el-descriptions-item>
            <el-descriptions-item label="import_path">{{ customDetail.import_path || "-" }}</el-descriptions-item>
            <el-descriptions-item label="module">{{ customDetail.module || "-" }}</el-descriptions-item>
            <el-descriptions-item label="class_name">{{ customDetail.class_name || "-" }}</el-descriptions-item>
            <el-descriptions-item label="repr"><span class="summary-box">{{ customDetail.repr || "-" }}</span></el-descriptions-item>
            <el-descriptions-item label="summary"><span class="summary-box">{{ customDetail.summary || "-" }}</span></el-descriptions-item>
            <el-descriptions-item label="doc"><pre class="summary-box qteasy-result-pre">{{ customDetail.doc || "-" }}</pre></el-descriptions-item>
          </el-descriptions>
        </template>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { qteasyApi, qteasyUnwrap } from "../services/qteasy";
import type { QteasyCustomStrategyItem, QteasyStrategyItem } from "../types";

const router = useRouter();
const activeTab = ref<"builtins" | "custom">("builtins");
const loading = ref({ builtin: false, custom: false });
const errorMessage = ref("");
const builtinStrategies = ref<QteasyStrategyItem[]>([]);
const customStrategies = ref<QteasyCustomStrategyItem[]>([]);
const selectedBuiltinId = ref("");
const selectedCustomName = ref("");
const builtinDetail = ref<QteasyStrategyItem | null>(null);
const customDetail = ref<QteasyCustomStrategyItem | null>(null);
const customUnavailable = ref(false);

const detailKind = computed<"builtins" | "custom" | "">(() => {
  if (activeTab.value === "custom" && customDetail.value) return "custom";
  if (activeTab.value === "builtins" && builtinDetail.value) return "builtins";
  return "";
});

const hasCurrentDetail = computed(() => Boolean(detailKind.value === "builtins" ? builtinDetail.value : customDetail.value));
const activeTabLabel = computed(() => (activeTab.value === "custom" ? "自定义策略" : "内置策略"));
const currentTitle = computed(() => {
  if (detailKind.value === "custom") return customDetail.value?.name || "-";
  return builtinDetail.value?.strategy_id || "-";
});
const currentSubtitle = computed(() => {
  if (detailKind.value === "custom") return customDetail.value?.class_name || customDetail.value?.import_path || "-";
  return builtinDetail.value?.class_name || "-";
});

function normalizeCustomStrategy(payload: unknown, fallbackName = ""): QteasyCustomStrategyItem {
  const source = payload && typeof payload === "object" && !Array.isArray(payload) ? (payload as Record<string, unknown>) : {};
  return {
    name: String(source.name || fallbackName || ""),
    import_path: typeof source.import_path === "string" ? source.import_path : typeof source.path === "string" ? source.path : null,
    class_name: typeof source.class_name === "string" ? source.class_name : null,
    module: typeof source.module === "string" ? source.module : null,
    summary: typeof source.summary === "string" ? source.summary : typeof source.doc === "string" ? source.doc : null,
    doc: typeof source.doc === "string" ? source.doc : null,
    repr: typeof source.repr === "string" ? source.repr : null,
    ...source,
  };
}

async function copyText(value: string): Promise<void> {
  if (!value) return;
  await navigator.clipboard.writeText(value);
  ElMessage.success("已复制");
}

async function loadBuiltinStrategies(): Promise<void> {
  loading.value.builtin = true;
  errorMessage.value = "";
  try {
    builtinStrategies.value = qteasyUnwrap<QteasyStrategyItem[]>(await qteasyApi.get<unknown>("/strategies/builtins"), []);
    if (!selectedBuiltinId.value && builtinStrategies.value.length) {
      await loadBuiltinStrategy(builtinStrategies.value[0].strategy_id);
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.value.builtin = false;
  }
}

async function loadBuiltinStrategy(strategyId: string): Promise<void> {
  selectedBuiltinId.value = strategyId;
  errorMessage.value = "";
  try {
    builtinDetail.value = qteasyUnwrap<QteasyStrategyItem>(
      await qteasyApi.get<unknown>(`/strategies/builtins/${encodeURIComponent(strategyId)}`),
      { strategy_id: strategyId },
    );
    activeTab.value = "builtins";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  }
}

async function loadCustomStrategies(): Promise<void> {
  loading.value.custom = true;
  customUnavailable.value = false;
  errorMessage.value = "";
  try {
    const payload = await qteasyApi.get<unknown>("/strategies/custom");
    const items = qteasyUnwrap<unknown[]>(payload, []);
    customStrategies.value = Array.isArray(items) ? items.map((item) => normalizeCustomStrategy(item)).filter((item) => item.name) : [];
    if (!selectedCustomName.value && customStrategies.value.length) {
      await loadCustomStrategy(customStrategies.value[0].name);
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (message.includes("404") || message.includes("Not Found")) {
      customUnavailable.value = true;
      customStrategies.value = [];
      customDetail.value = null;
    } else {
      errorMessage.value = message;
    }
  } finally {
    loading.value.custom = false;
  }
}

async function loadCustomStrategy(name: string): Promise<void> {
  selectedCustomName.value = name;
  errorMessage.value = "";
  try {
    const payload = await qteasyApi.get<unknown>(`/strategies/custom/${encodeURIComponent(name)}`);
    customDetail.value = normalizeCustomStrategy(qteasyUnwrap<unknown>(payload, {}), name);
    activeTab.value = "custom";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  }
}

function goToTaskWorkbench(): void {
  if (detailKind.value === "custom" && customDetail.value) {
    void router.push({
      path: "/qteasy/tasks",
      query: {
        kind: "backtest",
        strategy_source: "custom",
        strategy_name: customDetail.value.name,
        strategy_path: customDetail.value.import_path || "",
      },
    });
    return;
  }

  if (detailKind.value === "builtins" && builtinDetail.value) {
    void router.push({
      path: "/qteasy/tasks",
      query: {
        kind: "backtest",
        strategy_source: "built_in",
        strategy_id: builtinDetail.value.strategy_id,
      },
    });
  }
}

function refreshAll(): void {
  void Promise.all([loadBuiltinStrategies(), loadCustomStrategies()]);
}

watch(activeTab, (tab) => {
  if (tab === "builtins" && builtinStrategies.value.length && !builtinDetail.value) {
    void loadBuiltinStrategy(builtinStrategies.value[0].strategy_id);
  }
  if (tab === "custom" && customStrategies.value.length && !customDetail.value) {
    void loadCustomStrategy(customStrategies.value[0].name);
  }
});

onMounted(() => {
  refreshAll();
});
</script>
