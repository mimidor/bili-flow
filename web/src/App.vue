<template>
  <NLoadingBarProvider>
    <NNotificationProvider>
      <NDialogProvider>
        <NMessageProvider>
          <router-view v-if="isAuthLayout" />

          <a-layout v-else class="app-shell" :class="{ 'app-shell--mobile': isMobile }">
            <template v-if="isMobile">
              <a-layout-header class="mobile-header">
                <div class="mobile-header__brand">
                  <a-button class="mobile-header__menu-trigger" type="text" size="large" @click="drawerVisible = true">
                    <template #icon>
                      <a-icon><IconMenu /></a-icon>
                    </template>
                  </a-button>

                  <div class="header__brand header__brand--mobile">
                    <div class="header__badge">Admin Hub</div>
                    <div class="header__brand-copy">
                      <div class="header__title">{{ currentRouteTitle }}</div>
                      <div class="header__subtitle">内容采集、推送编排、量化回测统一管理</div>
                    </div>
                  </div>
                </div>

                <div class="header__actions header__actions--mobile">
                  <a-button class="header__action" type="text" size="small" @click="handleRefresh">
                    <template #icon>
                      <a-icon><IconRefresh /></a-icon>
                    </template>
                  </a-button>
                  <a-button class="header__action" type="text" size="small" status="danger" @click="handleLogout">
                    <template #icon>
                      <a-icon><IconPoweroff /></a-icon>
                    </template>
                  </a-button>
                </div>
              </a-layout-header>

              <a-layout-content class="content content--mobile" :style="contentStyle">
                <div class="page-container page-container--mobile">
                  <router-view />
                </div>
              </a-layout-content>

              <a-drawer
                v-model:visible="drawerVisible"
                class="mobile-nav-drawer"
                title="菜单"
                placement="left"
                :width="'86vw'"
                :footer="false"
                :mask-closable="true"
                unmount-on-close
              >
                <AdminSidebar :collapsed="false" compact />
              </a-drawer>
            </template>

            <template v-else>
              <a-layout-sider
                class="sidebar"
                :width="sidebarWidth"
                :collapsed-width="64"
                collapse-mode="width"
                show-trigger
                :collapsed="desktopCollapsed"
                @collapse="desktopCollapsed = true"
                @expand="desktopCollapsed = false"
              >
                <AdminSidebar :collapsed="desktopCollapsed" />
              </a-layout-sider>

              <a-layout class="main">
                <a-layout-header class="header">
                  <div class="header__brand">
                    <div class="header__badge">Admin Hub</div>
                    <div>
                      <div class="header__title">{{ currentRouteTitle }}</div>
                      <div class="header__subtitle">内容采集、推送编排、量化回测统一管理</div>
                    </div>
                  </div>

                  <div class="header__actions">
                    <a-button class="header__action" type="text" size="small" @click="handleRefresh">
                      刷新
                    </a-button>
                    <a-button class="header__action" type="text" size="small" status="danger" @click="handleLogout">
                      <template #icon>
                        <a-icon><IconPoweroff /></a-icon>
                      </template>
                      退出登录
                    </a-button>
                  </div>
                </a-layout-header>

                <a-layout-content class="content" :style="contentStyle">
                  <div class="page-container">
                    <router-view />
                  </div>
                </a-layout-content>
              </a-layout>
            </template>
          </a-layout>
        </NMessageProvider>
      </NDialogProvider>
    </NNotificationProvider>
  </NLoadingBarProvider>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NDialogProvider, NLoadingBarProvider, NMessageProvider, NNotificationProvider } from "naive-ui";
import { useRoute, useRouter } from "vue-router";
import { IconMenu, IconPoweroff, IconRefresh } from "@arco-design/web-vue/es/icon";

import { logout } from "./auth";
import AdminSidebar from "./components/layout/AdminSidebar.vue";
import { useBreakpoint } from "./composables/useBreakpoint";

const route = useRoute();
const router = useRouter();
const { isMobile, isTablet } = useBreakpoint();

const isAuthLayout = computed(() => route.meta.layout === "auth");
const desktopCollapsed = ref(false);
const drawerVisible = ref(false);

const sidebarWidth = computed(() => (isTablet.value ? 248 : 286));
const contentStyle = computed(() =>
  `padding: ${isMobile.value ? "12px 12px 16px" : isTablet.value ? "18px 18px 22px" : "24px"};`,
);

const currentRouteTitle = computed(() => {
  const explicitTitle = typeof route.meta?.title === "string" ? route.meta.title : "";
  if (explicitTitle) return explicitTitle;

  if (route.path.startsWith("/qteasy")) {
    const suffix = route.path.replace(/^\/qteasy\/?/, "");
    return suffix ? `量化回测 ${suffix.replace(/-/g, " ")}` : "量化回测总览";
  }
  return "管理后台";
});

watch(
  () => route.path,
  () => {
    document.title = `${currentRouteTitle.value} - bili-flow`;
    drawerVisible.value = false;
  },
  { immediate: true },
);

watch(
  isMobile,
  (mobile) => {
    if (!mobile) {
      drawerVisible.value = false;
    }
  },
  { immediate: true },
);

function handleRefresh(): void {
  window.location.reload();
}

async function handleLogout(): Promise<void> {
  await logout();
  await router.replace("/login");
}
</script>
