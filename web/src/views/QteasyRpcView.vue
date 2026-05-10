<template>
  <div class="qteasy-form-stack">
    <div class="health-grid">
      <el-card class="health-card">
        <div class="health-card__title">函数数量</div>
        <div class="health-card__value">{{ rpcNames.length }}</div>
        <div class="health-card__meta">白名单调用</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">当前函数</div>
        <div class="health-card__value">{{ selectedRpc || "-" }}</div>
        <div class="health-card__meta">调用目标</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">状态</div>
        <div class="health-card__value">{{ loading ? "执行中" : "待命" }}</div>
        <div class="health-card__meta">只认 JSON</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">结果</div>
        <div class="health-card__value">{{ resultLabel }}</div>
        <div class="health-card__meta">结构化返回</div>
      </el-card>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="warning" :closable="false" show-icon />

    <div class="chart-grid">
      <el-card class="page-card section">
        <template #header>
          <div class="section-header">
            <div>
              <div class="section__title">RPC 选择</div>
              <div class="section__desc">选择白名单函数并填写 JSON 参数。这个页面定位为高级调试入口。</div>
            </div>
          </div>
        </template>

        <div class="qteasy-form-stack">
          <div class="qteasy-form-grid qteasy-form-grid--wide">
            <el-select v-model="selectedRpc" filterable placeholder="选择函数">
              <el-option v-for="name in rpcNames" :key="name" :label="name" :value="name" />
            </el-select>
            <el-input v-model="payloadText" type="textarea" :rows="10" placeholder='{"verbose": false}' />
          </div>
          <el-space wrap>
            <el-button type="primary" :loading="loading" @click="callRpc">执行 RPC</el-button>
            <el-button @click="fillExample">填充示例</el-button>
            <el-button @click="clearResult">清空结果</el-button>
          </el-space>
        </div>
      </el-card>

      <el-card class="page-card section">
        <template #header>
          <div class="section-header">
            <div>
              <div class="section__title">返回结果</div>
              <div class="section__desc">结构化结果直接展示，必要时再复制原始 JSON。</div>
            </div>
          </div>
        </template>

        <pre class="summary-box qteasy-result-pre">{{ prettyJson(result) }}</pre>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import { qteasyApi, qteasyUnwrap } from "../services/qteasy";
import { prettyJson } from "../utils";
import type { QteasyJsonRecord } from "../types";

const rpcNames = [
  "get_configurations",
  "get_config",
  "configuration",
  "get_start_up_settings",
  "update_start_up_setting",
  "remove_start_up_setting",
  "view_config_files",
  "save_config",
  "load_config",
  "reset_config",
  "is_ready",
  "get_basic_info",
  "get_stock_info",
  "get_table_info",
  "get_table_overview",
  "get_data_overview",
  "filter_stocks",
  "filter_stock_codes",
  "get_history_data",
  "get_kline",
  "built_ins",
  "built_in_list",
  "built_in_doc",
  "get_built_in_strategy",
  "live_trade_accounts",
  "rotate_trade_logs",
];

const selectedRpc = ref(rpcNames[0]);
const payloadText = ref('{\n  "verbose": false\n}');
const loading = ref(false);
const errorMessage = ref("");
const result = ref<QteasyJsonRecord>({});

const resultLabel = computed(() => (Object.keys(result.value || {}).length ? "已返回" : "-"));

function fillExample(): void {
  if (selectedRpc.value === "get_configurations" || selectedRpc.value === "built_in_list") {
    payloadText.value = '{\n  "verbose": false\n}';
    return;
  }
  if (selectedRpc.value === "get_basic_info" || selectedRpc.value === "get_stock_info") {
    payloadText.value = '{\n  "code_or_name": "000001.SZ",\n  "verbose": false\n}';
    return;
  }
  payloadText.value = "{\n}";
}

function clearResult(): void {
  result.value = {};
  errorMessage.value = "";
}

async function callRpc(): Promise<void> {
  if (!selectedRpc.value) {
    errorMessage.value = "请选择函数";
    return;
  }
  loading.value = true;
  errorMessage.value = "";
  try {
    const payload = payloadText.value.trim() ? JSON.parse(payloadText.value) : {};
    result.value = qteasyUnwrap<QteasyJsonRecord>(
      await qteasyApi.post<unknown>(`/rpc/${encodeURIComponent(selectedRpc.value)}`, payload),
      {},
    );
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.value = false;
  }
}
</script>
