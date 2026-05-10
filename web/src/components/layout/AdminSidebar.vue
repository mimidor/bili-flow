<template>
  <div class="sidebar admin-sidebar" :class="{ 'sidebar--compact': props.compact }">
    <div class="sidebar__top">
      <div class="brand">
        <div class="brand__logo">
          <img class="brand__icon" src="/bilibili-logo.svg" alt="Bilibili logo" />
        </div>
        <div v-if="!props.collapsed" class="brand__copy">
          <div class="brand__title">bili-flow 管理后台</div>
          <div class="brand__subtitle">内容采集、推送编排、量化回测统一管理</div>
        </div>
      </div>

      <div v-if="!props.collapsed" class="brand__chips">
        <span>内容运营</span>
        <span>量化回测</span>
        <span>LLM 中心</span>
      </div>
    </div>

    <div v-if="!props.collapsed" class="sidebar__search">
      <a-input v-model="menuQuery" allow-clear placeholder="搜索菜单、关键词或路径" class="sidebar__search-input">
        <template #prefix>
          <a-icon><IconSearch /></a-icon>
        </template>
      </a-input>
      <div class="sidebar__search-meta">
        <span>{{ filteredMenuCount }} 项结果</span>
        <span v-if="menuQuery">关键词：{{ menuQuery }}</span>
      </div>
    </div>

    <div class="sidebar__scroll">
      <a-menu
        class="menu"
        theme="dark"
        :selected-keys="[route.path]"
        :collapsed="props.collapsed"
        :collapsed-width="64"
        :accordion="false"
        :open-keys="openKeys"
        @menu-item-click="handleMenuSelect"
        @update:openKeys="handleOpenKeysUpdate"
      >
        <a-menu-item v-if="showDashboard" key="/">
          <template #icon>
            <a-icon class="menu-item__icon"><IconDashboard /></a-icon>
          </template>
          <span class="menu-item__label menu-item__label--home">总览</span>
        </a-menu-item>

        <a-sub-menu
          v-for="group in filteredMenuGroups"
          :key="group.key"
          class="menu-group"
          :style="{ '--group-accent': group.accent }"
        >
          <template #icon>
            <a-icon class="menu-group__icon"><component :is="group.icon" /></a-icon>
          </template>
          <template #title>
            <span class="menu-group__title">{{ group.title }}</span>
            <span class="menu-group__count">{{ group.items.length }}</span>
          </template>
          <a-menu-item v-for="item in group.items" :key="item.path">
            <template #icon>
              <a-icon class="menu-item__icon"><component :is="item.icon || group.icon" /></a-icon>
            </template>
            <span class="menu-item__label">{{ item.label }}</span>
          </a-menu-item>
        </a-sub-menu>
      </a-menu>

      <div v-if="!showDashboard && !filteredMenuGroups.length" class="sidebar__empty">
        <a-empty description="当前账号没有可用菜单" />
      </div>
      <div v-else-if="!filteredMenuGroups.length && menuQuery" class="sidebar__empty">
        <a-empty description="没有匹配的菜单" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, type Component } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  IconApps,
  IconBarChart,
  IconBook,
  IconDashboard,
  IconExperiment,
  IconFile,
  IconFire,
  IconFolder,
  IconSafe,
  IconSearch,
  IconSettings,
  IconTool,
  IconUser,
  IconUserGroup,
} from "@arco-design/web-vue/es/icon";

import { currentUserState, hasMenuAccess } from "../../auth";

type MenuItem = {
  label: string;
  path: string;
  icon?: Component;
  menuKey: string;
  keywords?: string[];
};

type MenuGroup = {
  key: string;
  title: string;
  icon: Component;
  accent: string;
  items: MenuItem[];
};

const props = withDefaults(
  defineProps<{
    collapsed?: boolean;
    compact?: boolean;
  }>(),
  {
    collapsed: false,
    compact: false,
  },
);

const route = useRoute();
const router = useRouter();
const menuQuery = ref("");
const manualOpenKeys = ref<string[]>([]);

const menuGroups: MenuGroup[] = [
  {
    key: "ops",
    title: "运维中心",
    icon: IconSafe,
    accent: "#3b82f6",
    items: [
      { label: "系统监控", path: "/monitor", icon: IconSafe, menuKey: "menu.monitor" },
      { label: "任务中心", path: "/tasks", icon: IconTool, menuKey: "menu.tasks" },
      { label: "日志中心", path: "/logs", icon: IconFile, menuKey: "menu.logs" },
    ],
  },
  {
    key: "content",
    title: "内容运营",
    icon: IconFire,
    accent: "#2563eb",
    items: [
      { label: "内容审核", path: "/content-audit", icon: IconSafe, menuKey: "menu.content_audit" },
      { label: "视频管理", path: "/videos", icon: IconFile, menuKey: "menu.videos" },
      { label: "动态管理", path: "/dynamics", icon: IconApps, menuKey: "menu.dynamics" },
      {
        label: "手动推送",
        path: "/manual-push",
        icon: IconTool,
        menuKey: "menu.manual_push",
        keywords: ["推送", "BV", "任务"],
      },
      { label: "推送历史", path: "/pushes", icon: IconFire, menuKey: "menu.push_history" },
      {
        label: "推送配置",
        path: "/push-targets",
        icon: IconApps,
        menuKey: "menu.push_targets",
        keywords: ["飞书", "推送组"],
      },
      { label: "小宇宙", path: "/podcasts", icon: IconBook, menuKey: "menu.podcasts" },
      {
        label: "公众号订阅",
        path: "/wewe-rss",
        icon: IconBook,
        menuKey: "menu.wewe_rss",
        keywords: ["wewe", "rss", "公众号"],
      },
    ],
  },
  {
    key: "llm",
    title: "LLM 中心",
    icon: IconExperiment,
    accent: "#8b5cf6",
    items: [
      { label: "模型管理", path: "/llm-models", icon: IconExperiment, menuKey: "menu.llm_models" },
      {
        label: "对话工作台",
        path: "/llm-chat",
        icon: IconBook,
        menuKey: "menu.llm_chat",
        keywords: ["chat", "模型对比"],
      },
      {
        label: "提示词管理",
        path: "/llm-prompts",
        icon: IconFile,
        menuKey: "menu.llm_prompts",
        keywords: ["prompt", "提示词"],
      },
    ],
  },
  {
    key: "stats",
    title: "数据统计",
    icon: IconBarChart,
    accent: "#14b8a6",
    items: [
      {
        label: "Token 统计",
        path: "/tokens",
        icon: IconBarChart,
        menuKey: "menu.tokens",
        keywords: ["成本", "调用"],
      },
    ],
  },
  {
    key: "qteasy",
    title: "量化回测",
    icon: IconExperiment,
    accent: "#7c3aed",
    items: [
      { label: "总览", path: "/qteasy", icon: IconDashboard, menuKey: "menu.qteasy" },
      { label: "数据中心", path: "/qteasy/data", icon: IconBarChart, menuKey: "menu.qteasy" },
      { label: "策略目录", path: "/qteasy/strategies", icon: IconTool, menuKey: "menu.qteasy" },
      { label: "任务工作台", path: "/qteasy/tasks", icon: IconFire, menuKey: "menu.qteasy" },
      { label: "结果分析", path: "/qteasy/results", icon: IconBarChart, menuKey: "menu.qteasy" },
      { label: "高级工具", path: "/qteasy/tools", icon: IconSettings, menuKey: "menu.qteasy" },
    ],
  },
  {
    key: "config",
    title: "配置中心",
    icon: IconSettings,
    accent: "#0ea5e9",
    items: [
      { label: "订阅管理", path: "/subscriptions", icon: IconUserGroup, menuKey: "menu.subscriptions" },
      { label: "规则管理", path: "/rules", icon: IconTool, menuKey: "menu.rules" },
      { label: "文件夹映射", path: "/folder-mappings", icon: IconFolder, menuKey: "menu.folder_mappings" },
      { label: "业务配置", path: "/config", icon: IconSettings, menuKey: "menu.config" },
      {
        label: "环境配置",
        path: "/env-config",
        icon: IconSafe,
        menuKey: "menu.env_config",
        keywords: ["变量", "运行时配置"],
      },
      {
        label: "账号与角色",
        path: "/access-control",
        icon: IconUser,
        menuKey: "menu.access_control",
        keywords: ["rbac", "权限", "用户", "角色"],
      },
    ],
  },
];

const currentUser = computed(() => currentUserState.value ?? null);

const visibleMenuGroups = computed(() =>
  menuGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => hasMenuAccess(currentUser.value, item.menuKey)),
    }))
    .filter((group) => group.items.length > 0),
);

const filteredMenuGroups = computed(() => {
  const query = menuQuery.value.trim().toLowerCase();
  if (!query) return visibleMenuGroups.value;

  return visibleMenuGroups.value
    .map((group) => {
      const groupMatch = group.title.toLowerCase().includes(query);
      const items = group.items.filter((item) => {
        const haystack = [item.label, item.path, item.menuKey, ...(item.keywords || [])].join(" ").toLowerCase();
        return groupMatch || haystack.includes(query);
      });
      return { ...group, items };
    })
    .filter((group) => group.items.length > 0);
});

const showDashboard = computed(() => hasMenuAccess(currentUser.value, "menu.dashboard"));

const filteredMenuCount = computed(
  () => filteredMenuGroups.value.reduce((total, group) => total + group.items.length, 0) + (showDashboard.value ? 1 : 0),
);

const openKeys = computed(() => {
  const query = menuQuery.value.trim();
  if (query) return filteredMenuGroups.value.map((group) => group.key);
  if (manualOpenKeys.value.length) return manualOpenKeys.value;
  const currentGroup = filteredMenuGroups.value.find((group) => group.items.some((item) => item.path === route.path));
  return currentGroup ? [currentGroup.key] : [];
});

function handleMenuSelect(value: string | number): void {
  const path = String(value);
  if (path.startsWith("/")) {
    void router.push(path);
  }
}

function handleOpenKeysUpdate(keys: Array<string | number>): void {
  manualOpenKeys.value = keys.map((key) => String(key));
}
</script>
