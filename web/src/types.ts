export type Overview = {
  videos: number;
  dynamics: number;
  podcasts: number;
  push_records: number;
  llm_calls: number;
  llm_total_tokens: number;
  llm_prompt_tokens: number;
  llm_completion_tokens: number;
};

export type PageResult<T> = {
  total: number;
  page: number;
  page_size: number;
  items: T[];
};

export type AdminPermissionItem = {
  id: number;
  key: string;
  label: string;
  kind: string;
  group_key: string;
  group_name: string;
  description?: string | null;
};

export type AdminRoleItem = {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  is_system: boolean;
  is_active: boolean;
  permissions: AdminPermissionItem[];
  permission_keys: string[];
  user_count: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AdminUserItem = {
  id: number;
  username: string;
  display_name?: string | null;
  is_active: boolean;
  is_super_admin: boolean;
  roles: Array<{ id: number; code: string; name: string }>;
  permissions: string[];
  menu_keys: string[];
  last_login_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type VideoItem = {
  id: number;
  bvid: string;
  title: string;
  mid: string;
  uploader_name: string;
  pub_time: number | null;
  status: string;
  attempt_count: number;
  last_error?: string | null;
  summary_json?: Record<string, unknown> | string | null;
  doc_url?: string | null;
  transcript_text?: string | null;
  created_at?: string | null;
};

export type TaskAcceptedResponse = {
  accepted: boolean;
  task: string;
  target?: string | null;
  message: string;
};

export type ManualPushTaskCreateResponse = {
  accepted: boolean;
  task_id: number;
  bvid: string;
  push_target_id?: number | null;
  push_target_name?: string | null;
  message: string;
};

export type ManualPushTaskSummary = {
  id: number;
  bvid: string;
  source_type?: string | null;
  source_path?: string | null;
  push_target_id?: number | null;
  push_target_name?: string | null;
  title?: string | null;
  uploader_name?: string | null;
  source_video_id?: number | null;
  status: string;
  stage: string;
  progress: number;
  message?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  source_url?: string | null;
};

export type ManualPushTaskDetail = ManualPushTaskSummary & {
  result_json?: Record<string, unknown> | string | null;
};

export type ManualPushTaskItem = ManualPushTaskSummary;

export type ManualPushTaskCreateRequest = {
  bvid: string;
  push_target_id?: number | null;
};

export type DynamicItem = {
  id: number;
  dynamic_id: string;
  mid: string;
  uploader_name: string;
  type: number | null;
  text: string | null;
  image_count: number;
  image_urls?: string[];
  images_path?: string[];
  summary_json?: Record<string, unknown> | string | null;
  doc_url?: string | null;
  status: string;
  push_status: string;
  pub_time?: string | null;
  pushed_at?: string | null;
  last_error?: string | null;
  created_at?: string | null;
};

export type PushHistorySummary = {
  id: number;
  content_type: string;
  content_id: string;
  content_title?: string | null;
  uploader_name?: string | null;
  channel: string;
  target_id?: number | null;
  target_name?: string | null;
  target_receive_id?: string | null;
  status: string;
  error_message?: string | null;
  response_summary?: string | null;
  created_at?: string | null;
};

export type PushHistoryDetail = PushHistorySummary & {
  request_payload?: unknown;
  response_payload?: unknown;
};

export type PushHistoryItem = PushHistorySummary;

export type LLMUsageSummary = {
  id: number;
  content_type?: string | null;
  content_id?: string | null;
  content_title?: string | null;
  uploader_name?: string | null;
  provider: string;
  model?: string | null;
  web_search_enabled?: boolean;
  web_search_mode?: string | null;
  web_search_used?: boolean;
  web_search_fallback_reason?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  duration_ms?: number | null;
  success: boolean;
  error_message?: string | null;
  created_at?: string | null;
};

export type LLMUsageDetail = LLMUsageSummary & {
  raw_response?: unknown;
};

export type LlmUsageItem = LLMUsageSummary;

export type LLMProfileSummary = {
  id: number;
  name: string;
  provider: string;
  base_url?: string | null;
  model_name: string;
  enable_web_search?: boolean;
  enable_reasoning?: boolean;
  enable_image?: boolean;
  enable_tools?: boolean;
  web_search_mode?: string | null;
  web_search_supported?: boolean;
  is_default: boolean;
  is_active: boolean;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type LLMProfileDetail = LLMProfileSummary & {
  api_key?: string | null;
};

export type LLMModelProfileItem = LLMProfileSummary;

export type LLMChatRole = "system" | "user" | "assistant";

export type LLMChatMessage = {
  role: LLMChatRole;
  content: string;
};

export type LLMChatToolCall = {
  id?: string | null;
  index?: number | null;
  name: string;
  arguments?: string | null;
  partial?: boolean | null;
  status?: string | null;
};

export type LLMChatToolResult = {
  id?: string | null;
  name?: string | null;
  status?: string | null;
  content: string;
};

export type LLMChatStructuredBlock =
  | {
      kind: "thinking";
      key?: string | null;
      text: string;
    }
  | {
      kind: "tool_call";
      key?: string | null;
      id?: string | null;
      index?: number | null;
      name: string;
      arguments?: string | null;
      partial?: boolean | null;
      status?: string | null;
    }
  | {
      kind: "tool_result";
      key?: string | null;
      id?: string | null;
      name?: string | null;
      status?: string | null;
      content: string;
    }
  | {
      kind: "text";
      key?: string | null;
      text: string;
    };

export type LLMChatRequest = {
  messages: LLMChatMessage[];
  system_prompt?: string;
  temperature?: number;
  max_tokens?: number;
  timeout?: number;
};

export type LLMChatStreamEvent = {
  type: "meta" | "delta" | "thinking" | "tool_call" | "tool_result" | "done" | "error";
  profile_id?: number | null;
  profile_name?: string | null;
  provider?: string | null;
  model_name?: string | null;
  web_search_mode?: string | null;
  web_search_enabled?: boolean | null;
  web_search_used?: boolean | null;
  web_search_fallback_reason?: string | null;
  success?: boolean | null;
  fallback?: boolean | null;
  elapsed_seconds?: number | null;
  text?: string | null;
  reasoning?: string | null;
  tool_call?: LLMChatToolCall | null;
  tool_result?: LLMChatToolResult | null;
  blocks?: LLMChatStructuredBlock[] | null;
  message?: string | null;
};

export type LLMChatCompareResult = {
  profileId: number;
  profileName: string;
  provider: string;
  modelName: string;
  status: "streaming" | "done" | "error" | "aborted";
  content: string;
  blocks: LLMChatStructuredBlock[];
  note: string;
  error: string;
  success: boolean | null;
  fallback: boolean | null;
  elapsedSeconds: number | null;
  webSearchMode: string | null;
  webSearchUsed: boolean | null;
  webSearchFallbackReason: string | null;
  hasStructuredStreamParts: boolean;
};

export type LLMChatSessionItem = {
  id: number;
  session_key: string;
  title: string;
  source: string;
  model_ids: number[];
  system_prompt: string;
  temperature: number;
  max_tokens: number;
  turns_count: number;
  last_turn_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type LLMChatSessionTurnItem = {
  id: number;
  session_id: number;
  turn_index: number;
  source: string;
  user_prompt: string;
  model_results: LLMChatCompareResult[];
  created_at?: string | null;
  updated_at?: string | null;
};

export type LLMChatSessionDetail = {
  session: LLMChatSessionItem;
  turns: LLMChatSessionTurnItem[];
};

export type LLMChatSessionCreateRequest = {
  title?: string;
  model_ids?: number[];
  system_prompt?: string;
  temperature?: number;
  max_tokens?: number;
  source?: string;
};

export type LLMChatSessionUpdateRequest = {
  title?: string | null;
  model_ids?: number[] | null;
  system_prompt?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  source?: string | null;
};

export type LLMChatSessionTurnCreateRequest = {
  prompt: string;
  model_results: LLMChatCompareResult[];
  model_ids?: number[];
  system_prompt?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  source?: string;
};

export type SubscriptionItem = {
  id: number;
  mid: string;
  name: string;
  homepage_url?: string | null;
  push_target_id?: number | null;
  push_target_name?: string | null;
  notes?: string | null;
  is_active: boolean;
  last_video_bvid?: string | null;
  last_dynamic_id?: string | null;
  last_check_time?: string | null;
  created_at?: string | null;
};

export type PushTargetItem = {
  id: number;
  channel: string;
  name: string;
  receive_id: string;
  receive_id_type: string;
  is_default: boolean;
  is_active: boolean;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PodcastSubscriptionItem = {
  id: number;
  pid: string;
  name: string;
  homepage_url?: string | null;
  last_episode_eid?: string | null;
  last_episode_pub_time?: string | null;
  bootstrap_recent_episodes: number;
  last_check_time?: string | null;
  last_success_time?: string | null;
  consecutive_failures: number;
  is_active: boolean;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PodcastEpisodeItem = {
  id: number;
  eid: string;
  pid: string;
  title: string;
  uploader_name?: string | null;
  pub_time?: string | null;
  audio_url: string;
  audio_mime?: string | null;
  audio_size?: number | null;
  raw_episode_json?: Record<string, unknown> | string | null;
  local_audio_path?: string | null;
  local_transcript_path?: string | null;
  local_summary_path?: string | null;
  transcript_text?: string | null;
  summary_json?: Record<string, unknown> | string | null;
  doc_url?: string | null;
  status: string;
  push_status: string;
  download_attempts: number;
  asr_attempts: number;
  summary_attempts: number;
  attempt_count: number;
  last_error?: string | null;
  discovered_at?: string | null;
  downloaded_at?: string | null;
  transcribed_at?: string | null;
  summarized_at?: string | null;
  pushed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type WeWeRssFeedItem = {
  feed_id: string;
  title: string;
  homepage_url?: string | null;
  atom_url?: string | null;
  rss_url?: string | null;
  json_url?: string | null;
  raw?: Record<string, unknown> | string | null;
};

export type WeWeRssSubscriptionItem = {
  id: number;
  feed_id: string;
  name: string;
  homepage_url?: string | null;
  feed_format?: string | null;
  push_target_id?: number | null;
  push_target_name?: string | null;
  last_entry_id?: string | null;
  last_entry_pub_time?: string | null;
  last_response_cursor_json?: Record<string, unknown> | string | null;
  bootstrap_recent_items: number;
  last_check_time?: string | null;
  last_success_time?: string | null;
  consecutive_failures: number;
  is_active: boolean;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type WeWeRssArticleItem = {
  id: number;
  entry_id: string;
  feed_id: string;
  feed_name?: string | null;
  title: string;
  author?: string | null;
  link: string;
  pub_time?: string | null;
  content_text?: string | null;
  content_html?: string | null;
  raw_entry_json?: Record<string, unknown> | string | null;
  status: string;
  push_status: string;
  attempt_count: number;
  last_error?: string | null;
  discovered_at?: string | null;
  pushed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  source_url?: string | null;
};

export type RuleItem = {
  id: number;
  uploader_name: string;
  pattern: string;
  target_folder: string;
  priority: number;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

export type FolderMappingItem = {
  id: number;
  uploader_name: string;
  category: string;
  folder_token: string;
  folder_path: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type TokenDailyItem = {
  day: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  calls: number;
};

export type TokenModelItem = {
  provider: string;
  model: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  calls: number;
};

export type TrendDayItem = {
  day: string;
  videos: number;
  dynamics: number;
  pushes: number;
  calls: number;
  tokens: number;
};

export type TrendWindowSummary = {
  push_days: Array<Pick<TrendDayItem, "day" | "videos" | "dynamics" | "pushes">>;
  llm_days: Array<Pick<TrendDayItem, "day" | "calls" | "tokens">>;
};

export type HealthMetricItem = {
  module: "video" | "dynamic" | "push" | "llm";
  label: string;
  total_count: number;
  terminal_total: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  failure_rate: number;
};

export type RecentErrorItem = {
  module: "video" | "dynamic" | "push" | "llm";
  label: string;
  item_label: string;
  item_id: string;
  item_title?: string | null;
  status?: string | null;
  error_message: string;
  occurred_at?: string | null;
};

export type StatsSummary = {
  health_metrics: HealthMetricItem[];
  video_status: Array<{ status: string; count: number }>;
  dynamic_status: Array<{ status: string; count: number }>;
  podcast_status: Array<{ status: string; count: number }>;
  push_channel_status: Array<{ channel: string; status: string; count: number }>;
  llm_provider_status: Array<{ provider: string; success: boolean; count: number }>;
  recent_push_days: Array<{ day: string; videos: number; dynamics: number; pushes: number }>;
  recent_llm_days: Array<{ day: string; calls: number; tokens: number }>;
  trend_7_days: TrendWindowSummary;
  trend_30_days: TrendWindowSummary;
  recent_errors: RecentErrorItem[];
};

export type MonitorOverviewResponse = {
  health_metrics: HealthMetricItem[];
  task_overview: TaskOverview;
  runtime_states: TaskRuntimeItem[];
  recent_errors: RecentErrorItem[];
  recent_push_days: Array<{ day: string; videos: number; dynamics: number; pushes: number }>;
  recent_llm_days: Array<{ day: string; calls: number; tokens: number }>;
};

export type ContentAuditReasonItem = {
  reason: string;
  count: number;
};

export type ContentAuditContentItem = {
  content_type: string;
  count: number;
};

export type ContentAuditUploaderItem = {
  uploader_name: string;
  count: number;
};

export type ContentAuditOverviewResponse = {
  skipped_total: number;
  llm_filter_total: number;
  llm_filter_failed: number;
  reason_rows: ContentAuditReasonItem[];
  content_rows: ContentAuditContentItem[];
  uploader_rows: ContentAuditUploaderItem[];
  recent_skipped: PushHistoryItem[];
};

export type TaskRuntimeItem = {
  component: "scheduler" | "queue_worker" | string;
  label: string;
  is_paused: boolean;
  status: string;
  last_heartbeat_at?: string | null;
  last_run_at?: string | null;
  last_message?: string | null;
  last_error?: string | null;
};

export type TaskOverview = {
  video_pending: number;
  video_processing: number;
  video_failed: number;
  dynamic_pending: number;
  dynamic_processing: number;
  dynamic_failed: number;
  podcast_pending: number;
  podcast_processing: number;
  podcast_failed: number;
  total_pending: number;
  total_processing: number;
  total_failed: number;
  runtime_states: TaskRuntimeItem[];
};

export type TaskItem = {
  id: number;
  content_type: "video" | "dynamic" | "podcast";
  content_id: string;
  title: string;
  uploader_name?: string | null;
  status: string;
  push_status?: string | null;
  attempt_count: number;
  last_error?: string | null;
  pub_time?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  source_url?: string | null;
  doc_url?: string | null;
  summary_excerpt?: string | null;
};

export type TaskListResponse = PageResult<TaskItem>;

export type TaskRetryItem = {
  content_type: "video" | "dynamic" | "podcast";
  id: number;
};

export type TaskRetryRequest = {
  items: TaskRetryItem[];
};

export type TaskRetryResponse = {
  success: boolean;
  requeued: number;
  failed: number;
  message: string;
};

export type TaskRuntimeUpdateRequest = {
  scheduler_paused?: boolean | null;
  queue_paused?: boolean | null;
};

export type TaskRuntimeUpdateResponse = {
  runtime_states: TaskRuntimeItem[];
};

export type LLMConnectionTestResponse = {
  success: boolean;
  message: string;
  elapsed_seconds?: number;
  prompt_text?: string;
  response_text?: string;
  web_search_mode?: string;
  web_search_used?: boolean;
};

export type LLMBatchTestItem = {
  profile_id: number;
  profile_name: string;
  provider: string;
  model_name: string;
  success: boolean;
  message: string;
  elapsed_seconds?: number | null;
  prompt_text?: string | null;
  response_text?: string | null;
  web_search_mode?: string | null;
  web_search_used?: boolean | null;
};

export type LLMBatchTestResponse = {
  prompt: string;
  system_prompt?: string;
  total: number;
  success_count: number;
  failure_count: number;
  items: LLMBatchTestItem[];
};

export type EnvConfigItem = {
  key: string;
  label: string;
  group: string;
  value_type: "string" | "password" | "bool" | "int" | "select" | "push_target_select";
  description?: string;
  editable: boolean;
  secret: boolean;
  restart_required: boolean;
  options?: string[];
  option_items?: Array<{ value: number; label: string; is_default?: boolean }>;
  value: string | number | boolean;
};

export type EnvConfigResponse = {
  items: EnvConfigItem[];
};

export type EnvConfigUpdateRequest = {
  updates: Record<string, string | number | boolean | null>;
};

export type LogItem = {
  id: string;
  source_file: string;
  line_start: number;
  line_end: number;
  timestamp: string;
  level: string;
  module: string;
  message: string;
  excerpt?: string | null;
  has_multiline: boolean;
};

export type LogAlertItem = LogItem;

export type LogContextLine = {
  line_no: number;
  text: string;
  is_target: boolean;
};

export type LogDetail = LogItem & {
  raw_text: string;
  context_lines: LogContextLine[];
};

export type LogListResponse = {
  total: number;
  page: number;
  page_size: number;
  items: LogItem[];
  recent_alerts: LogAlertItem[];
  scanned_files?: string[];
  window_days?: number;
};

export type QteasyJsonRecord = Record<string, unknown>;

export type QteasyHealthResponse = {
  status?: string;
  service?: string;
  version?: string;
  ok?: boolean;
  apiUrl?: string;
  apiKeyConfigured?: boolean;
  [key: string]: unknown;
};

export type QteasyMetaResponse = {
  settings?: Record<string, unknown>;
  task_types?: string[];
  [key: string]: unknown;
};

export type QteasyStrategyItem = {
  strategy_id: string;
  summary?: string | null;
  doc?: string | null;
  class_name?: string | null;
  repr?: string | null;
  [key: string]: unknown;
};

export type QteasyCustomStrategyItem = {
  name: string;
  import_path?: string | null;
  class_name?: string | null;
  module?: string | null;
  summary?: string | null;
  doc?: string | null;
  repr?: string | null;
  [key: string]: unknown;
};

export type QteasyJobItem = {
  job_id: string;
  task_type: string;
  job_name?: string | null;
  status: string;
  priority?: number | null;
  progress?: number | null;
  current_step?: string | null;
  error?: string | null;
  result?: QteasyJsonRecord | string | null;
  payload?: QteasyJsonRecord | string | null;
  worker_id?: string | null;
  attempts?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  [key: string]: unknown;
};

export type QteasyChartPoint = {
  label: string;
  value: number;
};

export type QteasyPerformanceMetrics = Record<string, unknown>;

export type QteasyStoredResultItem = {
  id: number;
  job_id: string;
  task_type: string;
  job_name?: string | null;
  strategy_id?: string | null;
  strategy_path?: string | null;
  symbol_pool?: string[];
  benchmark?: string | null;
  invest_start?: string | null;
  invest_end?: string | null;
  status: string;
  metrics?: QteasyPerformanceMetrics;
  parsed_ok?: boolean;
  parse_message?: string | null;
  last_synced_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type QteasyStoredResultDetail = QteasyStoredResultItem & {
  payload?: QteasyJsonRecord | null;
  raw_result?: QteasyJsonRecord | string | null;
  equity_curve?: QteasyChartPoint[];
  benchmark_curve?: QteasyChartPoint[];
  drawdown_curve?: QteasyChartPoint[];
  return_histogram?: QteasyChartPoint[];
};

export type QteasyChartSeries = {
  job_id: string;
  metrics: QteasyPerformanceMetrics;
  equity_curve: QteasyChartPoint[];
  benchmark_curve: QteasyChartPoint[];
  drawdown_curve: QteasyChartPoint[];
  return_histogram: QteasyChartPoint[];
  parsed_ok?: boolean;
  parse_message?: string | null;
};

export type QteasyStoredResultListResponse = {
  total: number;
  page: number;
  page_size: number;
  items: QteasyStoredResultItem[];
};

export type QteasyJobListResponse = {
  total?: number;
  limit?: number;
  offset?: number;
  items?: QteasyJobItem[];
  [key: string]: unknown;
};

export type QteasyReportFileItem = {
  name: string;
  path?: string | null;
  size?: number | null;
  mtime?: number | null;
  url?: string | null;
  [key: string]: unknown;
};

export type QteasyDataOverviewResponse = {
  [key: string]: unknown;
};

export type QteasyTableInfoResponse = {
  [key: string]: unknown;
};

export type QteasyDataRefillRequest = {
  job_name?: string;
  tables?: string[];
  channel?: string;
  start_date?: string;
  end_date?: string;
  priority?: number;
};

export type QteasyBacktestRequest = {
  job_name?: string;
  mode?: number;
  strategies?: QteasyJsonRecord;
  run_kwargs?: QteasyJsonRecord;
  priority?: number;
};

export type QteasyOptimizationRequest = QteasyBacktestRequest & {
  optim_kwargs?: QteasyJsonRecord;
};

export type QteasyConfigResponse = {
  [key: string]: unknown;
};

export type QteasyRpcResponse = {
  [key: string]: unknown;
};
