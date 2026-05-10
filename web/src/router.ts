import type { RouteRecordRaw } from "vue-router";
import { createRouter, createWebHistory } from "vue-router";

import { fetchCurrentUser, hasMenuAccess, type AuthUser } from "./auth";

type AppRoute = RouteRecordRaw & { meta?: Record<string, any> };

const LoginView = () => import("./views/LoginView.vue");
const DashboardView = () => import("./views/DashboardView.vue");
const SystemMonitorView = () => import("./views/SystemMonitorView.vue");
const TaskCenterView = () => import("./views/TaskCenterView.vue");
const LogCenterView = () => import("./views/LogCenterView.vue");
const ContentAuditView = () => import("./views/ContentAuditView.vue");
const VideosView = () => import("./views/VideosView.vue");
const DynamicsView = () => import("./views/DynamicsView.vue");
const ManualPushView = () => import("./views/ManualPushView.vue");
const PushHistoryView = () => import("./views/PushHistoryView.vue");
const PushTargetView = () => import("./views/PushTargetView.vue");
const PodcastView = () => import("./views/PodcastView.vue");
const WeWeRssView = () => import("./views/WeWeRssView.vue");
const LLMModelMgmtView = () => import("./views/LLMModelMgmtView.vue");
const LLMChatWorkbenchView = () => import("./views/LLMChatWorkbenchView.vue");
const LLMPromptMgmtView = () => import("./views/LLMPromptMgmtView.vue");
const TokenStatsView = () => import("./views/TokenStatsView.vue");
const QteasyOverviewView = () => import("./views/QteasyOverviewView.vue");
const QteasyDataView = () => import("./views/QteasyDataView.vue");
const QteasyStrategiesView = () => import("./views/QteasyStrategiesView.vue");
const QteasyTasksView = () => import("./views/QteasyTasksView.vue");
const QteasyResultsView = () => import("./views/QteasyResultsView.vue");
const QteasyToolsView = () => import("./views/QteasyToolsView.vue");
const SubscriptionMgmtView = () => import("./views/SubscriptionMgmtView.vue");
const RuleMgmtView = () => import("./views/RuleMgmtView.vue");
const FolderMappingView = () => import("./views/FolderMappingView.vue");
const ConfigView = () => import("./views/ConfigView.vue");
const EnvConfigView = () => import("./views/EnvConfigView.vue");
const AccessControlView = () => import("./views/AccessControlView.vue");

const routes: AppRoute[] = [
  {
    path: "/login",
    name: "login",
    component: LoginView,
    meta: { public: true, layout: "auth", title: "登录" },
  },
  { path: "/", name: "dashboard", component: DashboardView, meta: { title: "总览", menuKey: "menu.dashboard" } },
  { path: "/monitor", name: "monitor", component: SystemMonitorView, meta: { title: "系统监控", menuKey: "menu.monitor" } },
  { path: "/tasks", name: "tasks", component: TaskCenterView, meta: { title: "任务中心", menuKey: "menu.tasks" } },
  { path: "/logs", name: "logs", component: LogCenterView, meta: { title: "日志中心", menuKey: "menu.logs" } },
  {
    path: "/content-audit",
    name: "content-audit",
    component: ContentAuditView,
    meta: { title: "内容审核", menuKey: "menu.content_audit" },
  },
  { path: "/videos", name: "videos", component: VideosView, meta: { title: "视频管理", menuKey: "menu.videos" } },
  { path: "/dynamics", name: "dynamics", component: DynamicsView, meta: { title: "动态管理", menuKey: "menu.dynamics" } },
  {
    path: "/manual-push",
    name: "manual-push",
    component: ManualPushView,
    meta: { title: "手动推送", menuKey: "menu.manual_push" },
  },
  {
    path: "/pushes",
    name: "pushes",
    component: PushHistoryView,
    meta: { title: "推送历史", menuKey: "menu.push_history" },
  },
  {
    path: "/push-targets",
    name: "push-targets",
    component: PushTargetView,
    meta: { title: "推送配置", menuKey: "menu.push_targets" },
  },
  { path: "/podcasts", name: "podcasts", component: PodcastView, meta: { title: "小宇宙", menuKey: "menu.podcasts" } },
  {
    path: "/wewe-rss",
    name: "wewe-rss",
    component: WeWeRssView,
    meta: { title: "公众号订阅", menuKey: "menu.wewe_rss" },
  },
  {
    path: "/llm-models",
    name: "llm-models",
    component: LLMModelMgmtView,
    meta: { title: "模型管理", menuKey: "menu.llm_models" },
  },
  {
    path: "/llm-chat",
    name: "llm-chat",
    component: LLMChatWorkbenchView,
    meta: { title: "对话工作台", menuKey: "menu.llm_chat" },
  },
  {
    path: "/llm-prompts",
    name: "llm-prompts",
    component: LLMPromptMgmtView,
    meta: { title: "提示词管理", menuKey: "menu.llm_prompts" },
  },
  { path: "/tokens", name: "tokens", component: TokenStatsView, meta: { title: "Token 统计", menuKey: "menu.tokens" } },
  {
    path: "/qteasy",
    name: "qteasy-overview",
    component: QteasyOverviewView,
    meta: { title: "量化回测总览", menuKey: "menu.qteasy", qteasySection: "overview" },
  },
  {
    path: "/qteasy/data",
    name: "qteasy-data",
    component: QteasyDataView,
    meta: { title: "数据中心", menuKey: "menu.qteasy", qteasySection: "data" },
  },
  {
    path: "/qteasy/strategies",
    name: "qteasy-strategies",
    component: QteasyStrategiesView,
    meta: { title: "策略目录", menuKey: "menu.qteasy", qteasySection: "strategies" },
  },
  {
    path: "/qteasy/tasks",
    name: "qteasy-tasks",
    component: QteasyTasksView,
    meta: { title: "任务工作台", menuKey: "menu.qteasy", qteasyTaskKind: "backtest", qteasySection: "tasks" },
  },
  { path: "/qteasy/backtests", redirect: { path: "/qteasy/tasks", query: { kind: "backtest" } } },
  { path: "/qteasy/optimizations", redirect: { path: "/qteasy/tasks", query: { kind: "optimization" } } },
  {
    path: "/qteasy/results",
    name: "qteasy-results",
    component: QteasyResultsView,
    meta: { title: "结果分析", menuKey: "menu.qteasy", qteasySection: "results" },
  },
  {
    path: "/qteasy/tools",
    name: "qteasy-tools",
    component: QteasyToolsView,
    meta: { title: "高级工具", menuKey: "menu.qteasy", qteasySection: "tools" },
  },
  { path: "/qteasy/config", redirect: { path: "/qteasy/tools", query: { tab: "config" } } },
  { path: "/qteasy/reports", redirect: { path: "/qteasy/tools", query: { tab: "reports" } } },
  { path: "/qteasy/rpc", redirect: { path: "/qteasy/tools", query: { tab: "rpc" } } },
  {
    path: "/subscriptions",
    name: "subscriptions",
    component: SubscriptionMgmtView,
    meta: { title: "订阅管理", menuKey: "menu.subscriptions" },
  },
  { path: "/rules", name: "rules", component: RuleMgmtView, meta: { title: "规则管理", menuKey: "menu.rules" } },
  {
    path: "/folder-mappings",
    name: "folder-mappings",
    component: FolderMappingView,
    meta: { title: "文件夹映射", menuKey: "menu.folder_mappings" },
  },
  { path: "/config", name: "config", component: ConfigView, meta: { title: "业务配置", menuKey: "menu.config" } },
  { path: "/env-config", name: "env-config", component: EnvConfigView, meta: { title: "环境配置", menuKey: "menu.env_config" } },
  {
    path: "/access-control",
    name: "access-control",
    component: AccessControlView,
    meta: { title: "账号与角色", menuKey: "menu.access_control" },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

function findFirstAccessiblePath(user: AuthUser): string {
  for (const route of routes) {
    if (route.meta?.public) continue;
    if (!hasMenuAccess(user, route.meta?.menuKey)) continue;
    return route.path;
  }
  return "/";
}

router.beforeEach(async (to) => {
  const user = await fetchCurrentUser();
  const isPublic = Boolean(to.meta.public);
  const targetMenuKey = typeof to.meta?.menuKey === "string" ? to.meta.menuKey : undefined;
  if (!user && !isPublic) {
    return { path: "/login", query: { redirect: to.fullPath } };
  }
  if (user && to.path === "/login") {
    return { path: findFirstAccessiblePath(user) };
  }
  if (user && !isPublic && !hasMenuAccess(user, targetMenuKey)) {
    const fallback = findFirstAccessiblePath(user);
    if (fallback === to.path) return false;
    return { path: fallback };
  }
  return true;
});

export default router;
