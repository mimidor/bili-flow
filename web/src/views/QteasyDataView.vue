<template>
  <div class="dashboard qteasy-page">
    <section class="hero-card">
      <div class="hero-copy">
        <div class="hero-eyebrow">QTEASY / DATA CENTER</div>
        <h1>数据中心</h1>
        <p class="hero-description">
          数据中心优先展示结构化概览和查询结果。原始响应只保留在调试区，方便排障但不干扰日常使用。
        </p>
      </div>
      <div class="hero-panel">
        <div>
          <div class="hero-panel__label">常用查询</div>
          <div class="hero-panel__value">6</div>
          <div class="hero-panel__meta">概览、表查询、标的信息、行情、筛选、账户</div>
        </div>
        <div class="hero-panel__actions">
          <el-button type="primary" :loading="loading.overview" @click="loadOverview">刷新概览</el-button>
          <el-button :loading="loading.accounts" @click="loadAccounts">刷新账户</el-button>
        </div>
      </div>
    </section>

    <div class="health-grid">
      <el-card class="health-card">
        <div class="health-card__title">数据表</div>
        <div class="health-card__value">{{ tableOverviewSummary.rowCount }}</div>
        <div class="health-card__meta">/data/table-overview</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">有数据表</div>
        <div class="health-card__value">{{ tableOverviewSummary.availableCount }}</div>
        <div class="health-card__meta">适合直接用于查询与回测</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">实盘账户</div>
        <div class="health-card__value">{{ accounts.length }}</div>
        <div class="health-card__meta">/live/accounts</div>
      </el-card>
      <el-card class="health-card">
        <div class="health-card__title">最近操作</div>
        <div class="health-card__value">{{ lastActionLabel }}</div>
        <div class="health-card__meta">当前页的最近一次请求</div>
      </el-card>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="warning" :closable="false" show-icon />

    <el-card class="page-card section">
      <template #header>
        <div class="section-header section-header--space-between">
          <div>
            <div class="section__title">数据工作台</div>
            <div class="section__desc">把散乱的调试接口收成结构化页签，查询结果优先可读，原始数据放到调试区。</div>
          </div>
          <el-space wrap>
            <el-tag type="info" effect="plain">{{ activeTabLabel }}</el-tag>
            <el-button text @click="refreshCurrentTab">刷新当前页签</el-button>
          </el-space>
        </div>
      </template>

      <el-tabs v-model="activeTab" class="qteasy-tabs">
        <el-tab-pane label="概览" name="overview">
          <div class="chart-grid">
            <el-card class="page-card section qteasy-overview-card">
              <template #header>
                <div class="section-header section-header--space-between">
                  <div>
                    <div class="section__title">数据源状态</div>
                    <div class="section__desc">把 /data/overview 与 /data/table-overview 归一成首屏卡片和表格。</div>
                  </div>
                  <el-space wrap>
                    <el-button text @click="copyJson(overview)">复制概览 JSON</el-button>
                    <el-button text @click="copyJson(tableOverview)">复制表概览 JSON</el-button>
                    <el-button type="primary" :loading="loading.overview" @click="loadOverview">刷新概览</el-button>
                  </el-space>
                </div>
              </template>

              <div class="qteasy-kv-grid">
                <div v-for="item in overviewKvItems" :key="item.label" class="qteasy-kv">
                  <span class="qteasy-kv__label">{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>

              <el-table :data="tableOverviewSummary.rows" stripe border max-height="520">
                <el-table-column prop="tableName" label="表名" min-width="220" fixed />
                <el-table-column label="状态" width="110">
                  <template #default="{ row }">
                    <el-tag :type="row.hasData ? 'success' : 'info'" size="small">
                      {{ row.hasData ? "有数据" : "空表" }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="records" label="记录数" width="120" />
                <el-table-column prop="size" label="大小" width="120" />
                <el-table-column prop="pk1" label="主键 1" min-width="140" />
                <el-table-column label="主键 1 范围" min-width="180">
                  <template #default="{ row }">{{ row.min1 }} ~ {{ row.max1 }}</template>
                </el-table-column>
                <el-table-column prop="pk2" label="主键 2" min-width="140" />
                <el-table-column label="主键 2 范围" min-width="180">
                  <template #default="{ row }">
                    <span v-if="row.pk2 !== '-'">{{ row.min2 }} ~ {{ row.max2 }}</span>
                    <span v-else>-</span>
                  </template>
                </el-table-column>
                <el-table-column label="详情" width="120" fixed="right">
                  <template #default="{ row }">
                    <el-button link type="primary" @click="openRowDetail(row)">查看</el-button>
                  </template>
                </el-table-column>
              </el-table>

              <el-collapse v-model="debugPanels" class="qteasy-debug-collapse">
                <el-collapse-item title="原始响应 /data/overview" name="overview">
                  <pre class="summary-box qteasy-result-pre">{{ prettyJson(overview) }}</pre>
                </el-collapse-item>
                <el-collapse-item title="原始响应 /data/table-overview" name="table-overview">
                  <pre class="summary-box qteasy-result-pre">{{ prettyJson(tableOverview) }}</pre>
                </el-collapse-item>
              </el-collapse>
            </el-card>
          </div>
        </el-tab-pane>

        <el-tab-pane label="表查询" name="tables">
          <el-card class="page-card section">
            <template #header>
              <div class="section-header">
                <div>
                  <div class="section__title">表信息</div>
                  <div class="section__desc">输入表名，读取结构、字段和补充信息。</div>
                </div>
              </div>
            </template>

            <div class="qteasy-form-grid">
              <el-input v-model="tableName" placeholder="table_name" clearable />
              <el-button type="primary" :loading="loading.tableInfo" @click="loadTableInfo">查询</el-button>
            </div>

            <el-descriptions v-if="tableInfoRows.length" :column="2" border class="u-mt-16">
              <el-descriptions-item v-for="item in tableInfoRows" :key="item.label" :label="item.label">
                <span class="summary-box">{{ item.value }}</span>
              </el-descriptions-item>
            </el-descriptions>
            <el-empty v-else description="输入表名后开始查询" class="u-mt-16" />

            <el-collapse v-model="debugPanels" class="qteasy-debug-collapse u-mt-16">
              <el-collapse-item title="原始响应 /data/table-info" name="table-info">
                <pre class="summary-box qteasy-result-pre">{{ prettyJson(tableInfo) }}</pre>
              </el-collapse-item>
            </el-collapse>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="标的信息" name="assets">
          <div class="chart-grid">
            <el-card class="page-card section">
              <template #header>
                <div class="section-header">
                  <div>
                    <div class="section__title">基础信息</div>
                    <div class="section__desc">按代码或名称查询基础信息和股票信息。</div>
                  </div>
                </div>
              </template>

              <div class="qteasy-form-stack">
                <div class="qteasy-form-grid qteasy-form-grid--wide">
                  <el-input v-model="basicForm.code_or_name" placeholder="代码或名称" clearable />
                  <el-input v-model="basicForm.asset_types" placeholder="asset_types" clearable />
                  <el-input v-model="basicForm.match_full_name" placeholder="match_full_name" clearable />
                  <el-input v-model="basicForm.verbose" placeholder="verbose" clearable />
                </div>
                <el-space wrap>
                  <el-button type="primary" :loading="loading.basicInfo" @click="loadBasicInfo">查询基础信息</el-button>
                  <el-button :loading="loading.stockInfo" @click="loadStockInfo">查询股票信息</el-button>
                </el-space>
              </div>
            </el-card>

            <el-card class="page-card section">
              <template #header>
                <div class="section-header">
                  <div>
                    <div class="section__title">结构化结果</div>
                    <div class="section__desc">优先展示可读字段，原始 JSON 放到调试区。</div>
                  </div>
                </div>
              </template>

              <div class="qteasy-result-grid">
                <div>
                  <div class="qteasy-result-grid__title">/data/basic-info</div>
                  <el-descriptions v-if="basicInfoRows.length" :column="1" border>
                    <el-descriptions-item v-for="item in basicInfoRows" :key="`basic-${item.label}`" :label="item.label">
                      <span class="summary-box">{{ item.value }}</span>
                    </el-descriptions-item>
                  </el-descriptions>
                  <el-empty v-else description="暂无结果" />
                </div>
                <div>
                  <div class="qteasy-result-grid__title">/data/stock-info</div>
                  <el-descriptions v-if="stockInfoRows.length" :column="1" border>
                    <el-descriptions-item v-for="item in stockInfoRows" :key="`stock-${item.label}`" :label="item.label">
                      <span class="summary-box">{{ item.value }}</span>
                    </el-descriptions-item>
                  </el-descriptions>
                  <el-empty v-else description="暂无结果" />
                </div>
              </div>

              <el-collapse v-model="debugPanels" class="qteasy-debug-collapse u-mt-16">
                <el-collapse-item title="原始响应 /data/basic-info" name="basic-info">
                  <pre class="summary-box qteasy-result-pre">{{ prettyJson(basicInfo) }}</pre>
                </el-collapse-item>
                <el-collapse-item title="原始响应 /data/stock-info" name="stock-info">
                  <pre class="summary-box qteasy-result-pre">{{ prettyJson(stockInfo) }}</pre>
                </el-collapse-item>
              </el-collapse>
            </el-card>
          </div>
        </el-tab-pane>

        <el-tab-pane label="行情查询" name="history">
          <div class="chart-grid">
            <el-card class="page-card section">
              <template #header>
                <div class="section-header">
                  <div>
                    <div class="section__title">历史数据</div>
                    <div class="section__desc">控制时间窗和 max_rows，避免一次拉取过重结果集。</div>
                  </div>
                </div>
              </template>

              <div class="qteasy-form-stack">
                <div class="qteasy-form-grid qteasy-form-grid--wide">
                  <el-input v-model="historyForm.htypes" placeholder="htypes" clearable />
                  <el-input v-model="historyForm.shares" placeholder="shares" clearable />
                  <el-input v-model="historyForm.start" placeholder="start" clearable />
                  <el-input v-model="historyForm.end" placeholder="end" clearable />
                </div>
                <div class="qteasy-form-grid qteasy-form-grid--wide">
                  <el-input v-model="historyForm.rows" placeholder="rows" clearable />
                  <el-input v-model="historyForm.freq" placeholder="freq" clearable />
                  <el-input v-model="historyForm.asset_type" placeholder="asset_type" clearable />
                  <el-input v-model="historyForm.adj" placeholder="adj" clearable />
                </div>
                <div class="qteasy-form-grid qteasy-form-grid--wide">
                  <el-input v-model="historyForm.max_rows" placeholder="max_rows" clearable />
                  <el-switch v-model="historyForm.as_panel" active-text="as_panel" />
                  <el-switch v-model="historyForm.b_days_only" active-text="b_days_only" />
                  <el-switch v-model="historyForm.trade_time_only" active-text="trade_time_only" />
                </div>
                <el-button type="primary" :loading="loading.history" @click="loadHistory">查询历史数据</el-button>
              </div>

              <div class="qteasy-kv-grid u-mt-16">
                <div class="qteasy-kv" v-for="item in historySummaryRows" :key="item.label">
                  <span class="qteasy-kv__label">{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>

              <el-collapse v-model="debugPanels" class="qteasy-debug-collapse u-mt-16">
                <el-collapse-item title="原始响应 /data/history" name="history">
                  <pre class="summary-box qteasy-result-pre">{{ prettyJson(historyResult) }}</pre>
                </el-collapse-item>
              </el-collapse>
            </el-card>

            <el-card class="page-card section">
              <template #header>
                <div class="section-header">
                  <div>
                    <div class="section__title">K 线</div>
                    <div class="section__desc">适合单标的快速检查，参数更轻。</div>
                  </div>
                </div>
              </template>

              <div class="qteasy-form-stack">
                <div class="qteasy-form-grid qteasy-form-grid--wide">
                  <el-input v-model="klineForm.symbol" placeholder="symbol / shares" clearable />
                  <el-input v-model="klineForm.freq" placeholder="freq" clearable />
                  <el-input v-model="klineForm.start" placeholder="start" clearable />
                  <el-input v-model="klineForm.end" placeholder="end" clearable />
                </div>
                <div class="qteasy-form-grid qteasy-form-grid--wide">
                  <el-input v-model="klineForm.asset_type" placeholder="asset_type" clearable />
                  <el-input v-model="klineForm.adj" placeholder="adj" clearable />
                  <el-input v-model="klineForm.rows" placeholder="rows" clearable />
                  <el-input v-model="klineForm.max_rows" placeholder="max_rows" clearable />
                </div>
                <el-button type="primary" :loading="loading.kline" @click="loadKline">查询 K 线</el-button>
              </div>

              <div class="qteasy-kv-grid u-mt-16">
                <div class="qteasy-kv" v-for="item in klineSummaryRows" :key="item.label">
                  <span class="qteasy-kv__label">{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>

              <el-collapse v-model="debugPanels" class="qteasy-debug-collapse u-mt-16">
                <el-collapse-item title="原始响应 /data/kline" name="kline">
                  <pre class="summary-box qteasy-result-pre">{{ prettyJson(klineResult) }}</pre>
                </el-collapse-item>
              </el-collapse>
            </el-card>
          </div>
        </el-tab-pane>

        <el-tab-pane label="股票筛选" name="filter">
          <el-card class="page-card section">
            <template #header>
              <div class="section-header">
                <div>
                  <div class="section__title">股票筛选</div>
                  <div class="section__desc">以 JSON 条件请求筛选接口，主界面展示条数和样本，原始响应放到调试区。</div>
                </div>
              </div>
            </template>

            <div class="qteasy-form-stack">
              <el-input v-model="filterJson" type="textarea" :rows="8" placeholder='{"market":"SZ","limit":20}' />
              <el-space wrap>
                <el-button type="primary" :loading="loading.filterStocks" @click="loadFilterStocks">筛选股票</el-button>
                <el-button :loading="loading.filterCodes" @click="loadFilterStockCodes">筛选代码</el-button>
              </el-space>
            </div>

            <div class="qteasy-result-grid u-mt-16">
              <div>
                <div class="qteasy-result-grid__title">/data/filter/stocks</div>
                <div class="qteasy-kv-grid">
                  <div class="qteasy-kv" v-for="item in filterStocksSummaryRows" :key="`stocks-${item.label}`">
                    <span class="qteasy-kv__label">{{ item.label }}</span>
                    <strong>{{ item.value }}</strong>
                  </div>
                </div>
              </div>
              <div>
                <div class="qteasy-result-grid__title">/data/filter/stock-codes</div>
                <div class="qteasy-kv-grid">
                  <div class="qteasy-kv" v-for="item in filterCodesSummaryRows" :key="`codes-${item.label}`">
                    <span class="qteasy-kv__label">{{ item.label }}</span>
                    <strong>{{ item.value }}</strong>
                  </div>
                </div>
              </div>
            </div>

            <el-collapse v-model="debugPanels" class="qteasy-debug-collapse u-mt-16">
              <el-collapse-item title="原始响应 /data/filter/stocks" name="filter-stocks">
                <pre class="summary-box qteasy-result-pre">{{ prettyJson(filterStocksResult) }}</pre>
              </el-collapse-item>
              <el-collapse-item title="原始响应 /data/filter/stock-codes" name="filter-codes">
                <pre class="summary-box qteasy-result-pre">{{ prettyJson(filterCodesResult) }}</pre>
              </el-collapse-item>
            </el-collapse>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="实盘账户" name="accounts">
          <el-card class="page-card section">
            <template #header>
              <div class="section-header section-header--space-between">
                <div>
                  <div class="section__title">实盘账户</div>
                  <div class="section__desc">读取 /live/accounts，优先展示账户摘要。</div>
                </div>
                <el-button type="primary" :loading="loading.accounts" @click="loadAccounts">刷新账户</el-button>
              </div>
            </template>

            <el-table :data="accounts" stripe>
              <el-table-column prop="account_name" label="账户" min-width="180" />
              <el-table-column prop="account_id" label="ID" min-width="160" />
              <el-table-column prop="broker" label="券商" min-width="140" />
              <el-table-column prop="cash" label="现金" min-width="120" />
              <el-table-column prop="equity" label="权益" min-width="120" />
            </el-table>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="rowDetailVisible" title="表概览详情" width="760px" destroy-on-close>
      <template v-if="selectedRow">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="表名">{{ selectedRow.tableName }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ selectedRow.hasData ? "有数据" : "空表" }}</el-descriptions-item>
          <el-descriptions-item label="记录数">{{ selectedRow.records }}</el-descriptions-item>
          <el-descriptions-item label="大小">{{ selectedRow.size }}</el-descriptions-item>
          <el-descriptions-item label="主键 1">{{ selectedRow.pk1 }}</el-descriptions-item>
          <el-descriptions-item label="主键 1 记录数">{{ selectedRow.records1 }}</el-descriptions-item>
          <el-descriptions-item label="主键 1 范围">{{ selectedRow.min1 }} ~ {{ selectedRow.max1 }}</el-descriptions-item>
          <el-descriptions-item label="主键 2">{{ selectedRow.pk2 }}</el-descriptions-item>
          <el-descriptions-item label="主键 2 记录数">{{ selectedRow.records2 }}</el-descriptions-item>
          <el-descriptions-item label="主键 2 范围">{{ selectedRow.min2 }} ~ {{ selectedRow.max2 }}</el-descriptions-item>
        </el-descriptions>
        <div class="qteasy-row-dialog__raw">
          <div class="qteasy-row-dialog__title">原始记录</div>
          <pre class="summary-box qteasy-result-pre">{{ prettyJson(selectedRow.raw) }}</pre>
        </div>
      </template>
      <template #footer>
        <el-button @click="rowDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { qteasyApi, qteasyUnwrap } from "../services/qteasy";
import { prettyJson } from "../utils";
import type { QteasyDataOverviewResponse, QteasyJsonRecord, QteasyTableInfoResponse } from "../types";

type ActiveDataTab = "overview" | "tables" | "assets" | "history" | "filter" | "accounts";

type QteasyDataframeResponse = QteasyJsonRecord & {
  type?: unknown;
  shape?: unknown;
  columns?: unknown;
  index_name?: unknown;
  index?: unknown;
  records?: unknown;
};

type QteasyTableOverviewRow = {
  tableName: string;
  hasData: boolean;
  size: string;
  records: string;
  pk1: string;
  records1: string;
  min1: string;
  max1: string;
  pk2: string;
  records2: string;
  min2: string;
  max2: string;
  raw: QteasyJsonRecord;
};

const activeTab = ref<ActiveDataTab>("overview");
const loading = reactive({
  overview: false,
  tableInfo: false,
  basicInfo: false,
  stockInfo: false,
  accounts: false,
  history: false,
  kline: false,
  filterStocks: false,
  filterCodes: false,
});

const errorMessage = ref("");
const overview = ref<QteasyDataOverviewResponse>({});
const tableOverview = ref<QteasyJsonRecord[]>([]);
const tableInfo = ref<QteasyTableInfoResponse | QteasyJsonRecord>({});
const basicInfo = ref<QteasyJsonRecord>({});
const stockInfo = ref<QteasyJsonRecord>({});
const accounts = ref<QteasyJsonRecord[]>([]);
const historyResult = ref<QteasyJsonRecord>({});
const klineResult = ref<QteasyJsonRecord>({});
const filterStocksResult = ref<QteasyJsonRecord>({});
const filterCodesResult = ref<QteasyJsonRecord>({});
const debugPanels = ref<string[]>([]);
const selectedRow = ref<QteasyTableOverviewRow | null>(null);
const rowDetailVisible = ref(false);
const tableName = ref("");
const filterJson = ref('{"market":"SZ","limit":20}');
const basicForm = reactive({
  code_or_name: "",
  asset_types: "",
  match_full_name: "",
  printout: "",
  verbose: "",
});
const historyForm = reactive({
  htypes: "",
  shares: "",
  start: "",
  end: "",
  rows: "",
  freq: "",
  asset_type: "",
  adj: "",
  max_rows: "",
  as_panel: false,
  b_days_only: false,
  trade_time_only: false,
});
const klineForm = reactive({
  symbol: "",
  freq: "",
  start: "",
  end: "",
  asset_type: "",
  adj: "",
  rows: "",
  max_rows: "",
});

function isPlainObject(value: unknown): value is QteasyJsonRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function toText(value: unknown, fallback = "-"): string {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    const text = value.map((item) => toText(item, "")).filter(Boolean).join(", ");
    return text || fallback;
  }
  if (isPlainObject(value)) {
    return prettyJson(value);
  }
  return String(value);
}

function parseCountLike(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value !== "string") {
    return 0;
  }
  const normalized = value.trim().replace(/,/g, "");
  if (!normalized) {
    return 0;
  }
  const suffixMatch = normalized.match(/^(-?\d+(?:\.\d+)?)([KMBT])$/i);
  if (suffixMatch) {
    const base = Number.parseFloat(suffixMatch[1] || "0");
    const suffix = (suffixMatch[2] || "").toUpperCase();
    const multipliers: Record<string, number> = {
      K: 1_000,
      M: 1_000_000,
      B: 1_000_000_000,
      T: 1_000_000_000_000,
    };
    return Math.round(base * (multipliers[suffix] || 1));
  }
  const numeric = Number(normalized);
  return Number.isFinite(numeric) ? numeric : 0;
}

function parseSizeLike(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value !== "string") {
    return 0;
  }
  const normalized = value.trim().replace(/,/g, "");
  if (!normalized) {
    return 0;
  }
  const sizeMatch = normalized.match(/^(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)$/i);
  if (!sizeMatch) {
    const numeric = Number(normalized);
    return Number.isFinite(numeric) ? numeric : 0;
  }
  const base = Number.parseFloat(sizeMatch[1] || "0");
  const unit = (sizeMatch[2] || "B").toUpperCase();
  const multipliers: Record<string, number> = {
    B: 1,
    KB: 1024,
    MB: 1024 ** 2,
    GB: 1024 ** 3,
    TB: 1024 ** 4,
  };
  return base * (multipliers[unit] || 1);
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = unit === 0 ? 0 : value >= 100 ? 0 : value >= 10 ? 1 : 2;
  return `${value.toFixed(digits)} ${units[unit]}`;
}

function normalizeTableRow(tableNameValue: string, record: QteasyJsonRecord | undefined): QteasyTableOverviewRow {
  const current = record ?? {};
  return {
    tableName: tableNameValue,
    hasData: Boolean(current.has_data),
    size: toText(current.size),
    records: toText(current.records),
    pk1: toText(current.pk1),
    records1: toText(current.records1),
    min1: toText(current.min1),
    max1: toText(current.max1),
    pk2: toText(current.pk2),
    records2: toText(current.records2),
    min2: toText(current.min2),
    max2: toText(current.max2),
    raw: current,
  };
}

function normalizeDataframe(payload: unknown) {
  const data = isPlainObject(payload) ? (payload as QteasyDataframeResponse) : {};
  const shape = Array.isArray(data.shape) ? data.shape : [];
  const columns = Array.isArray(data.columns) ? data.columns.filter((item): item is string => typeof item === "string") : [];
  const index = Array.isArray(data.index) ? data.index.filter((item): item is string => typeof item === "string") : [];
  const records = Array.isArray(data.records) ? data.records.filter(isPlainObject) : [];

  const rowCount = typeof shape[0] === "number" ? shape[0] : records.length || index.length;
  const columnCount = typeof shape[1] === "number" ? shape[1] : columns.length;
  const typeLabel = toText(data.type, "dataframe");
  const indexName = toText(data.index_name, "-");

  const rows = Array.from({ length: Math.max(index.length, records.length) }, (_, indexItem) => {
    const tableNameText = index[indexItem] ?? `#${indexItem + 1}`;
    return normalizeTableRow(tableNameText, records[indexItem]);
  });

  const availableCount = rows.filter((row) => row.hasData).length;
  const emptyCount = Math.max(rows.length - availableCount, 0);
  const estimatedRecords = rows.reduce((sum, row) => sum + parseCountLike(row.records), 0);
  const estimatedSize = rows.reduce((sum, row) => sum + parseSizeLike(row.size), 0);

  return {
    typeLabel,
    shapeLabel: `${rowCount} × ${columnCount}`,
    indexName,
    columnCount,
    rowCount,
    availableCount,
    emptyCount,
    estimatedRecordsLabel: new Intl.NumberFormat("zh-CN").format(estimatedRecords),
    estimatedSizeLabel: formatBytes(estimatedSize),
    rows,
  };
}

function summarizeValue(payload: unknown): Array<{ label: string; value: string }> {
  if (!isPlainObject(payload)) {
    return [];
  }
  return Object.entries(payload)
    .slice(0, 12)
    .map(([label, value]) => ({ label, value: toText(value) }));
}

function summarizeDataset(payload: unknown): Array<{ label: string; value: string }> {
  if (Array.isArray(payload)) {
    return [
      { label: "类型", value: "数组" },
      { label: "条数", value: String(payload.length) },
      { label: "样本", value: payload.length ? toText(payload[0]) : "-" },
    ];
  }
  if (isPlainObject(payload)) {
    const record = payload as Record<string, unknown>;
    const records = Array.isArray(record.records) ? record.records : Array.isArray(record.data) ? record.data : null;
    const columns = Array.isArray(record.columns) ? record.columns : null;
    const shape = Array.isArray(record.shape) ? record.shape : null;
    return [
      { label: "类型", value: toText(record.type, isPlainObject(record) ? "对象" : "-") },
      { label: "shape", value: shape ? shape.join(" × ") : "-" },
      { label: "列数", value: String(columns?.length ?? 0) },
      { label: "记录数", value: String(records?.length ?? 0) },
    ];
  }
  return [{ label: "结果", value: toText(payload) }];
}

const overviewSummary = computed(() => normalizeDataframe(overview.value));
const tableOverviewSummary = computed(() => normalizeDataframe(tableOverview.value));

const overviewKvItems = computed(() => [
  { label: "数据帧类型", value: overviewSummary.value.typeLabel },
  { label: "数据帧形状", value: overviewSummary.value.shapeLabel },
  { label: "索引名称", value: overviewSummary.value.indexName },
  { label: "列数", value: new Intl.NumberFormat("zh-CN").format(overviewSummary.value.columnCount) },
  { label: "估算记录数", value: tableOverviewSummary.value.estimatedRecordsLabel },
  { label: "估算容量", value: tableOverviewSummary.value.estimatedSizeLabel },
]);

const tableInfoRows = computed(() => summarizeValue(tableInfo.value));
const basicInfoRows = computed(() => summarizeValue(basicInfo.value));
const stockInfoRows = computed(() => summarizeValue(stockInfo.value));
const historySummaryRows = computed(() => summarizeDataset(historyResult.value));
const klineSummaryRows = computed(() => summarizeDataset(klineResult.value));
const filterStocksSummaryRows = computed(() => summarizeDataset(filterStocksResult.value));
const filterCodesSummaryRows = computed(() => summarizeDataset(filterCodesResult.value));

const activeTabLabel = computed(() => {
  const labels: Record<ActiveDataTab, string> = {
    overview: "概览",
    tables: "表查询",
    assets: "标的信息",
    history: "行情查询",
    filter: "股票筛选",
    accounts: "实盘账户",
  };
  return labels[activeTab.value];
});

const lastActionLabel = computed(() => {
  if (loading.history) return "历史数据";
  if (loading.kline) return "K 线";
  if (loading.filterStocks || loading.filterCodes) return "股票筛选";
  if (loading.tableInfo) return "表信息";
  if (loading.basicInfo || loading.stockInfo) return "标的信息";
  if (loading.accounts) return "实盘账户";
  return "概览";
});

function buildParams(source: Record<string, unknown>): Record<string, string | number | boolean | null | undefined> {
  return Object.fromEntries(
    Object.entries(source).map(([key, value]) => [key, value === "" ? undefined : value]),
  ) as Record<string, string | number | boolean | null | undefined>;
}

function openRowDetail(row: QteasyTableOverviewRow): void {
  selectedRow.value = row;
  rowDetailVisible.value = true;
}

async function copyJson(payload: unknown): Promise<void> {
  const text = prettyJson(payload as QteasyJsonRecord);
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

async function loadOverview(): Promise<void> {
  loading.overview = true;
  errorMessage.value = "";
  try {
    const [overviewResp, tableOverviewResp] = await Promise.all([
      qteasyApi.get<unknown>("/data/overview"),
      qteasyApi.get<unknown>("/data/table-overview"),
    ]);
    overview.value = qteasyUnwrap<QteasyDataOverviewResponse>(overviewResp, {});
    tableOverview.value = qteasyUnwrap<QteasyJsonRecord[]>(tableOverviewResp, []);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.overview = false;
  }
}

async function loadTableInfo(): Promise<void> {
  if (!tableName.value.trim()) {
    tableInfo.value = { error: "请输入 table_name" };
    return;
  }
  loading.tableInfo = true;
  errorMessage.value = "";
  try {
    tableInfo.value = await qteasyApi.get<QteasyTableInfoResponse>(`/data/table-info/${encodeURIComponent(tableName.value.trim())}`);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.tableInfo = false;
  }
}

async function loadBasicInfo(): Promise<void> {
  loading.basicInfo = true;
  errorMessage.value = "";
  try {
    basicInfo.value = await qteasyApi.get<QteasyJsonRecord>("/data/basic-info", buildParams(basicForm));
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.basicInfo = false;
  }
}

async function loadStockInfo(): Promise<void> {
  loading.stockInfo = true;
  errorMessage.value = "";
  try {
    stockInfo.value = await qteasyApi.get<QteasyJsonRecord>("/data/stock-info", buildParams(basicForm));
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.stockInfo = false;
  }
}

async function loadAccounts(): Promise<void> {
  loading.accounts = true;
  errorMessage.value = "";
  try {
    accounts.value = qteasyUnwrap<QteasyJsonRecord[]>(await qteasyApi.get<unknown>("/live/accounts"), []);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.accounts = false;
  }
}

function parseFilterParams(): Record<string, string | number | boolean | null | undefined> {
  try {
    const parsed = JSON.parse(filterJson.value || "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }
    return parsed as Record<string, string | number | boolean | null | undefined>;
  } catch {
    return {};
  }
}

async function loadFilterStocks(): Promise<void> {
  loading.filterStocks = true;
  errorMessage.value = "";
  try {
    filterStocksResult.value = await qteasyApi.get<QteasyJsonRecord>("/data/filter/stocks", parseFilterParams());
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.filterStocks = false;
  }
}

async function loadFilterStockCodes(): Promise<void> {
  loading.filterCodes = true;
  errorMessage.value = "";
  try {
    filterCodesResult.value = await qteasyApi.get<QteasyJsonRecord>("/data/filter/stock-codes", parseFilterParams());
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.filterCodes = false;
  }
}

async function loadHistory(): Promise<void> {
  loading.history = true;
  errorMessage.value = "";
  try {
    historyResult.value = await qteasyApi.get<QteasyJsonRecord>("/data/history", buildParams(historyForm));
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.history = false;
  }
}

async function loadKline(): Promise<void> {
  loading.kline = true;
  errorMessage.value = "";
  try {
    klineResult.value = await qteasyApi.get<QteasyJsonRecord>(
      "/data/kline",
      buildParams({
        shares: klineForm.symbol,
        freq: klineForm.freq,
        start: klineForm.start,
        end: klineForm.end,
        asset_type: klineForm.asset_type,
        adj: klineForm.adj,
        rows: klineForm.rows,
        max_rows: klineForm.max_rows,
      }),
    );
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    loading.kline = false;
  }
}

function refreshCurrentTab(): void {
  if (activeTab.value === "overview") {
    void loadOverview();
    return;
  }
  if (activeTab.value === "tables") {
    void loadTableInfo();
    return;
  }
  if (activeTab.value === "assets") {
    void Promise.all([loadBasicInfo(), loadStockInfo()]);
    return;
  }
  if (activeTab.value === "history") {
    void Promise.all([loadHistory(), loadKline()]);
    return;
  }
  if (activeTab.value === "filter") {
    void Promise.all([loadFilterStocks(), loadFilterStockCodes()]);
    return;
  }
  void loadAccounts();
}

onMounted(() => {
  void loadOverview();
  void loadAccounts();
});
</script>
