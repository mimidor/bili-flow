BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS runtime_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key VARCHAR NOT NULL UNIQUE,
    value TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO runtime_configs (key, value) VALUES
('ADMIN_AUTH_USERNAME', ''),
('ADMIN_AUTH_PASSWORD', ''),
('ADMIN_AUTH_SECRET', ''),
('ALIYUN_BAILIAN_ASR_MODEL', 'qwen3-asr-flash-filetrans'),
('ALIYUN_OSS_ACCESS_KEY_ID', ''),
('ALIYUN_OSS_ACCESS_KEY_SECRET', ''),
('ALIYUN_OSS_BUCKET', ''),
('ALIYUN_OSS_ENDPOINT', ''),
('ALIYUN_OSS_PREFIX', 'bili-flow/asr'),
('ASR_PROVIDER', 'local_whisper'),
('BILIBILI_COOKIE', ''),
('DASHSCOPE_API_KEY', ''),
('DATABASE_URL', 'sqlite:///data/bili.db'),
('DYNAMIC_CHECK_INTERVAL', '-1'),
('FEISHU_APP_ID', ''),
('FEISHU_APP_SECRET', ''),
('FEISHU_DOCS_ENABLED', 'false'),
('FEISHU_DOCS_FOLDER_TOKEN', ''),
('FEISHU_DOCS_SPACE_ID', ''),
('FEISHU_RECEIVE_ID', ''),
('FEISHU_RECEIVE_ID_TYPE', 'chat_id'),
('FEISHU_WEBHOOK', ''),
('LOG_LEVEL', 'INFO'),
('OPENAI_API_KEY', ''),
('OPENAI_BASE_URL', ''),
('OPENAI_MODEL', 'deepseek-chat'),
('SESSDATA', ''),
('USE_WHISPER_CPP', 'false'),
('VIDEO_CHECK_INTERVAL', '10'),
('WHISPER_CPP_CLI', ''),
('WHISPER_CPP_MODEL', ''),
('WHISPER_DEVICE', 'cpu'),
('WHISPER_MODEL', 'medium'),
('XYZ_DEVICE_ID', ''),
('XYZ_ACCESS_TOKEN', ''),
('XYZ_CHECK_INTERVAL', '10'),
('XYZ_REFRESH_TOKEN', ''),
('refresh_token', '')
ON CONFLICT(key) DO UPDATE SET
    value = excluded.value,
    updated_at = CURRENT_TIMESTAMP;

COMMIT;
