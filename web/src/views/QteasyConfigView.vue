<template>
  <div class="qteasy-form-stack">
    <div class="health-grid">
      <el-card class="health-card">
        <div class="health-card__title">启动配置</div>
        <div class="health-card__value">{{ startupKeys }}</div>
        <div class="health-card__meta">当前字段数</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">运行配置</div>
        <div class="health-card__value">{{ runtimeKeys }}</div>
        <div class="health-card__meta">当前字段数</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">最近状态</div>
        <div class="health-card__value">{{ lastMessage }}</div>
        <div class="health-card__meta">保存或加载结果</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">配置来源</div>
        <div class="health-card__value">{{ apiConfigured ? "在线" : "未连通" }}</div>
        <div class="health-card__meta">Qteasy API</div>
      </el-card>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="warning" :closable="false" show-icon />

    <div class="chart-grid">
      <el-card class="page-card section">
        <template #header>
          <div class="section-header section-header--space-between">
            <div>
              <div class="section__title">启动配置</div>
              <div class="section__desc">编辑后提交到 /config/startup。涉及进程级参数时，保存后仍建议重启 API 或 worker。</div>
            </div>
            <el-space wrap>
              <el-button type="primary" :loading="loading.saveStartup" @click="saveStartup">保存</el-button>
              <el-button :loading="loading.startup" @click="loadStartup">重新加载</el-button>
            </el-space>
          </div>
        </template>

        <el-input v-model="startupText" type="textarea" :rows="18" />
      </el-card>

      <el-card class="page-card section">
        <template #header>
          <div class="section-header section-header--space-between">
            <div>
              <div class="section__title">运行配置</div>
              <div class="section__desc">编辑后提交到 /config/runtime，适合修改运行时参数。</div>
            </div>
            <el-space wrap>
              <el-button type="primary" :loading="loading.saveRuntime" @click="saveRuntime">保存</el-button>
              <el-button :loading="loading.runtime" @click="loadRuntime">重新加载</el-button>
            </el-space>
          </div>
        </template>

        <el-input v-model="runtimeText" type="textarea" :rows="18" />
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { qteasyApi, qteasyUnwrap } from "../services/qteasy";
import { prettyJson } from "../utils";
import type { QteasyConfigResponse } from "../types";

const loading = ref({
  startup: false,
  runtime: false,
  saveStartup: false,
  saveRuntime: false,
});
const startup = ref<QteasyConfigResponse>({});
const runtime = ref<QteasyConfigResponse>({});
const startupText = ref("{}");
const runtimeText = ref("{}");
const errorMessage = ref("");
const lastMessage = ref("-");
const apiConfigured = ref(false);

const startupKeys = computed(() => Object.keys(startup.value || {}).length);
const runtimeKeys = computed(() => Object.keys(runtime.value || {}).length);

function syncTextFromData(): void {
  startupText.value = prettyJson(startup.value);
  runtimeText.value = prettyJson(runtime.value);
}

async function loadStartup(): Promise<void> {
  loading.value.startup = true;
  errorMessage.value = "";
  try {
    startup.value = qteasyUnwrap<QteasyConfigResponse>(await qteasyApi.get<unknown>("/config/startup"), {});
    apiConfigured.value = true;
    lastMessage.value = "已加载启动配置";
    syncTextFromData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.value.startup = false;
  }
}

async function loadRuntime(): Promise<void> {
  loading.value.runtime = true;
  errorMessage.value = "";
  try {
    runtime.value = qteasyUnwrap<QteasyConfigResponse>(await qteasyApi.get<unknown>("/config/runtime"), {});
    apiConfigured.value = true;
    lastMessage.value = "已加载运行配置";
    syncTextFromData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.value.runtime = false;
  }
}

async function saveStartup(): Promise<void> {
  loading.value.saveStartup = true;
  errorMessage.value = "";
  try {
    const payload = JSON.parse(startupText.value || "{}");
    startup.value = qteasyUnwrap<QteasyConfigResponse>(await qteasyApi.post<unknown>("/config/startup", payload), payload);
    lastMessage.value = "启动配置已保存";
    startupText.value = prettyJson(startup.value);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.value.saveStartup = false;
  }
}

async function saveRuntime(): Promise<void> {
  loading.value.saveRuntime = true;
  errorMessage.value = "";
  try {
    const payload = JSON.parse(runtimeText.value || "{}");
    runtime.value = qteasyUnwrap<QteasyConfigResponse>(await qteasyApi.post<unknown>("/config/runtime", payload), payload);
    lastMessage.value = "运行配置已保存";
    runtimeText.value = prettyJson(runtime.value);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.value.saveRuntime = false;
  }
}

async function loadAll(): Promise<void> {
  await Promise.all([loadStartup(), loadRuntime()]);
}

onMounted(() => {
  void loadAll();
});
</script>
