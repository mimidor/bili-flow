import type { EnvConfigItem } from "./types";

export function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    searchParams.set(key, String(value));
  });
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatUnixTime(value?: number | null): string {
  if (value === undefined || value === null) return "-";
  const ms = value < 10_000_000_000 ? value * 1000 : value;
  return formatDateTime(new Date(ms).toISOString());
}

export function truncate(value: string | null | undefined, length = 120): string {
  const text = value || "";
  if (text.length <= length) return text;
  return `${text.slice(0, length)}...`;
}

export function prettyJson(value: unknown): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

const STATUS_LABELS: Record<string, string> = {
  pending: "待处理",
  processing: "处理中",
  done: "已完成",
  failed: "失败",
  failed_download: "下载失败",
  failed_asr: "识别失败",
  failed_summary: "总结失败",
  sent: "已发送",
  filtered: "已过滤",
  skipped: "已跳过",
  success: "成功",
  running: "运行中",
  paused: "已暂停",
  error: "异常",
};

export function translateStatus(value?: string | null): string {
  if (!value) return "-";
  return STATUS_LABELS[value] || value;
}

export function translateContentType(value?: string | null): string {
  if (!value) return "-";
  if (value === "video") return "视频";
  if (value === "dynamic") return "动态";
  if (value === "podcast") return "小宇宙";
  if (value === "wewe_rss") return "公众号";
  return value;
}

export function translateChannel(value?: string | null): string {
  if (!value) return "-";
  if (value === "feishu") return "飞书";
  return value;
}

export function translateProvider(value?: string | null): string {
  if (!value) return "-";
  if (value === "openai") return "OpenAI接口";
  if (value === "openai-compatible") return "OpenAI兼容";
  if (value === "aliyun_bailian") return "阿里云百炼";
  if (value === "anthropic") return "Anthropic Claude";
  if (value === "gemini") return "Google Gemini";
  if (value === "vertex_ai") return "Google Vertex AI";
  if (value === "azure_openai") return "Azure OpenAI";
  if (value === "bedrock") return "AWS Bedrock";
  if (value === "mistral") return "Mistral";
  if (value === "cohere") return "Cohere";
  if (value === "perplexity") return "Perplexity";
  if (value === "xai") return "xAI Grok";
  if (value === "together") return "Together AI";
  if (value === "openrouter") return "OpenRouter";
  if (value === "fireworks") return "Fireworks AI";
  if (value === "deepseek") return "DeepSeek";
  if (value === "doubao") return "豆包";
  if (value === "kimi") return "Kimi";
  if (value === "zhipu") return "智谱";
  if (value === "minimax") return "MiniMax";
  if (value === "hunyuan") return "腾讯混元";
  if (value === "qianfan") return "百度千帆";
  if (value === "xinghuo") return "讯飞星火";
  if (value === "xiaomi") return "小米 MiMo";
  if (value === "pangu") return "华为盘古";
  if (value === "local") return "本地";
  return value;
}

export function translateWebSearchMode(value?: string | null): string {
  if (!value || value === "disabled") return "关闭";
  if (value === "chat_completions") return "Chat Completions";
  if (value === "responses") return "Responses";
  if (value === "unsupported") return "不支持";
  return value;
}

export function translateModule(value?: string | null): string {
  if (!value) return "-";
  if (value === "video") return "视频";
  if (value === "dynamic") return "动态";
  if (value === "podcast") return "小宇宙";
  if (value === "push") return "推送";
  if (value === "llm") return "LLM";
  return value;
}

export function translateBoolean(value: boolean | null | undefined): string {
  return value ? "是" : "否";
}

const LOG_LEVEL_LABELS: Record<string, string> = {
  DEBUG: "调试",
  INFO: "信息",
  WARNING: "警告",
  ERROR: "错误",
  CRITICAL: "严重",
};

export function translateLogLevel(value?: string | null): string {
  if (!value) return "-";
  return LOG_LEVEL_LABELS[value.toUpperCase()] || value;
}

export function logLevelTagType(value?: string | null): "info" | "success" | "warning" | "danger" {
  const level = (value || "").toUpperCase();
  if (level === "WARNING") return "warning";
  if (level === "ERROR" || level === "CRITICAL") return "danger";
  if (level === "INFO") return "success";
  return "info";
}

export function translateLoggerName(value?: string | null): string {
  if (!value) return "-";
  const labels: Record<string, string> = {
    main: "主进程",
    scheduler: "调度器",
    queue_worker: "队列 Worker",
    processor: "LLM 处理",
    push: "推送",
    init: "初始化",
  };
  return labels[value] || value;
}

export function buildBilibiliOpusUrl(dynamicId?: string | null): string | null {
  if (!dynamicId) return null;
  return `https://www.bilibili.com/opus/${dynamicId}`;
}

export function buildBilibiliContentUrl(contentType?: string | null, contentId?: string | null): string | null {
  if (!contentId) return null;
  if (contentType === "dynamic") {
    return buildBilibiliOpusUrl(contentId);
  }
  return null;
}

export type TokenCostRates = {
  inputPricePerMillion: number;
  outputPricePerMillion: number;
};

const DEFAULT_TOKEN_COST_RATES: TokenCostRates = {
  inputPricePerMillion: 2,
  outputPricePerMillion: 12,
};

export function resolveTokenCostRates(
  items: Array<Pick<EnvConfigItem, "key" | "value">> | null | undefined,
  fallback: TokenCostRates = DEFAULT_TOKEN_COST_RATES,
): TokenCostRates {
  if (!items?.length) {
    return fallback;
  }

  const lookup = new Map(items.map((item) => [item.key, item.value]));
  const inputValue = Number(lookup.get("LLM_INPUT_TOKEN_PRICE_PER_MILLION"));
  const outputValue = Number(lookup.get("LLM_OUTPUT_TOKEN_PRICE_PER_MILLION"));

  return {
    inputPricePerMillion: Number.isFinite(inputValue) && inputValue > 0 ? inputValue : fallback.inputPricePerMillion,
    outputPricePerMillion: Number.isFinite(outputValue) && outputValue > 0 ? outputValue : fallback.outputPricePerMillion,
  };
}

export function calcTokenCostByRates(
  promptTokens?: number | null,
  completionTokens?: number | null,
  rates: TokenCostRates = DEFAULT_TOKEN_COST_RATES,
): number {
  const prompt = promptTokens ?? 0;
  const completion = completionTokens ?? 0;
  return (prompt / 1_000_000) * rates.inputPricePerMillion + (completion / 1_000_000) * rates.outputPricePerMillion;
}

const QWEN36_PLUS_STANDARD_INPUT_PRICE = 2;
const QWEN36_PLUS_STANDARD_OUTPUT_PRICE = 12;
const QWEN36_PLUS_LONG_INPUT_PRICE = 8;
const QWEN36_PLUS_LONG_OUTPUT_PRICE = 48;
const QWEN36_PLUS_LONG_CONTEXT_THRESHOLD = 256_000;

export function calcTokenCost(promptTokens?: number | null, completionTokens?: number | null): number {
  const prompt = promptTokens ?? 0;
  const completion = completionTokens ?? 0;
  const isLongContext = prompt > QWEN36_PLUS_LONG_CONTEXT_THRESHOLD;
  const inputPrice = isLongContext ? QWEN36_PLUS_LONG_INPUT_PRICE : QWEN36_PLUS_STANDARD_INPUT_PRICE;
  const outputPrice = isLongContext ? QWEN36_PLUS_LONG_OUTPUT_PRICE : QWEN36_PLUS_STANDARD_OUTPUT_PRICE;
  return (prompt / 1_000_000) * inputPrice + (completion / 1_000_000) * outputPrice;
}

export function formatYuan(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "-";
  }
  return `元${value.toFixed(4)}`;
}

export function formatNumber(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat("zh-CN").format(value);
}

export function formatMoney(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(2);
}

export function formatPercent(value?: number | null, digits = 1): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

