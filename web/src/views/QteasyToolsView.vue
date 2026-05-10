<template>
  <div class="dashboard qteasy-page">
    <section class="hero-card">
      <div class="hero-copy">
        <div class="hero-eyebrow">QTEASY / ADVANCED TOOLS</div>
        <h1>高级工具</h1>
        <p class="hero-description">
          配置、报表和 RPC 都归到这里，作为总览、策略目录、任务工作台和结果分析之外的辅助能力。
        </p>
      </div>

      <div class="hero-panel">
        <div>
          <div class="hero-panel__label">当前工具</div>
          <div class="hero-panel__value">{{ currentTabLabel }}</div>
          <div class="hero-panel__meta">配置 / 报表 / RPC</div>
        </div>
        <div class="hero-panel__actions">
          <el-button type="primary" @click="goToTab('config')">配置中心</el-button>
          <el-button @click="goToTab('reports')">报表中心</el-button>
          <el-button @click="goToTab('rpc')">RPC 工具箱</el-button>
        </div>
      </div>
    </section>

    <div class="health-grid">
      <el-card v-for="tab in tabs" :key="tab.key" class="health-card" :class="{ 'health-card--active': tab.key === activeTab }">
        <div class="health-card__title">{{ tab.label }}</div>
        <div class="health-card__value">{{ tab.shortLabel }}</div>
        <div class="health-card__meta">{{ tab.description }}</div>
      </el-card>
    </div>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="这里是高级入口。配置和 RPC 更偏运维 / 调试，日常操作优先停留在总览、策略目录、任务工作台和结果分析。"
      class="u-mb-16"
    />

    <el-card class="page-card section">
      <template #header>
        <div class="section-header section-header--space-between">
          <div>
            <div class="section__title">工具切换</div>
            <div class="section__desc">把配置、报表和 RPC 收进同一页，减少主导航分散度。</div>
          </div>
          <el-space wrap>
            <el-tag type="info" effect="plain">{{ currentTabLabel }}</el-tag>
            <el-button text @click="refreshCurrent">刷新当前</el-button>
          </el-space>
        </div>
      </template>

      <el-tabs v-model="activeTab" class="qteasy-tabs" @tab-change="handleTabChange">
        <el-tab-pane v-for="tab in tabs" :key="tab.key" :name="tab.key" :label="tab.label">
          <component :is="tab.component" :key="`${tab.key}-${refreshSeed}`" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import QteasyConfigView from "./QteasyConfigView.vue";
import QteasyReportsView from "./QteasyReportsView.vue";
import QteasyRpcView from "./QteasyRpcView.vue";

type ToolTabKey = "config" | "reports" | "rpc";

const route = useRoute();
const router = useRouter();
const activeTab = ref<ToolTabKey>("config");

const tabs = [
  {
    key: "config" as const,
    label: "配置中心",
    shortLabel: "启动 / 运行",
    description: "读取和修改启动配置、运行配置。",
    component: markRaw(QteasyConfigView),
  },
  {
    key: "reports" as const,
    label: "报表中心",
    shortLabel: "交易日志",
    description: "列出并下载交易日志文件。",
    component: markRaw(QteasyReportsView),
  },
  {
    key: "rpc" as const,
    label: "RPC 工具箱",
    shortLabel: "白名单调用",
    description: "对白名单 RPC 函数做结构化调试。",
    component: markRaw(QteasyRpcView),
  },
] as const;

const currentTabLabel = computed(() => tabs.find((tab) => tab.key === activeTab.value)?.label || "配置中心");
const refreshSeed = ref(0);

function normalizeTab(value: unknown): ToolTabKey {
  return value === "reports" || value === "rpc" ? value : "config";
}

function syncTabFromRoute(): void {
  activeTab.value = normalizeTab(route.query.tab);
}

function goToTab(tab: ToolTabKey): void {
  void router.replace({ path: "/qteasy/tools", query: { ...route.query, tab } });
}

function handleTabChange(name: string | number): void {
  goToTab(normalizeTab(name));
}

function refreshCurrent(): void {
  refreshSeed.value += 1;
}

watch(
  () => route.query.tab,
  () => {
    syncTabFromRoute();
  },
  { immediate: true },
);

onMounted(() => {
  syncTabFromRoute();
});
</script>
