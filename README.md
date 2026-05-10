# bili-auto

`bili-auto` 是一个本地优先的内容采集和推送管理系统，当前主要覆盖：

- B 站视频采集、转写、总结、推送
- B 站动态采集与推送
- 小宇宙播客采集、转写、总结、推送
- WeWe RSS 公众号源订阅与全文推送
- LLM 模型、提示词、Token 统计与对话工作台
- Qteasy 量化回测代理与结果展示

当前版本以 Windows 本地部署为主，前端、后端、调度器都可以在一台机器上运行。

## 当前状态

- B 站视频 / 动态：主链路可用
- 小宇宙：主链路可用，但依赖有效的 access token
- WeWe RSS：已接入，但**仍属于未完全实现模块**
- Qteasy：已接入代理与页面，但**仍属于未完全实现模块**
- 飞书推送：主推送渠道
- 本地 ASR：支持 `faster-whisper`、`whisper.cpp`、`Qwen3-ASR-0.6B`

## 环境要求

- Windows 10/11
- Python 3.12
- Node.js 22
- `uv`
- `ffmpeg`

建议先准备好：

- 一个可用的 Python 虚拟环境
- 一个可用的 Node/npm 环境
- B 站 Cookie
- 至少一个可用的推送目标

## 项目结构

- [`admin_backend`](/E:/pycharmDevelop/bili-auto/admin_backend)：FastAPI 管理 API
- [`app`](/E:/pycharmDevelop/bili-auto/app)：调度器、队列、采集、ASR、LLM、推送
- [`web`](/E:/pycharmDevelop/bili-auto/web)：Vue 3 + TypeScript 管理台
- [`entrypoints`](/E:/pycharmDevelop/bili-auto/entrypoints)：后端 / 调度器 / Docker / 开发联启动入口
- [`scripts`](/E:/pycharmDevelop/bili-auto/scripts)：初始化、构建、维护脚本
- [`data`](/E:/pycharmDevelop/bili-auto/data)：SQLite、缓存、下载文件
- [`logs`](/E:/pycharmDevelop/bili-auto/logs)：运行日志

## 快速开始

### 1. 安装依赖

```powershell
uv sync
cd web
npm install
cd ..
```

### 2. 复制环境变量模板

```powershell
Copy-Item .env.example .env
```

### 3. 填写最少配置

至少先填下面这些：

```env
ADMIN_AUTH_SECRET=replace-with-a-random-secret

BILIBILI_COOKIE=
refresh_token=

OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=

FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_RECEIVE_ID=
FEISHU_RECEIVE_ID_TYPE=chat_id
```

### 4. Windows 本地启动

最省事的方式是直接用根目录的批处理：

```bat
run-dev.bat
```

这个命令会前台同时启动三路进程：

- 前端：`npm run dev`
- 后端：`python entrypoints\entrypoint-backend.py`
- 调度器：`python entrypoints\entrypoint-scheduler.py`

日志会直接输出到当前控制台，关闭窗口或按 `Ctrl+C` 会一起停止这三路进程。

如果你习惯 PowerShell，可以用：

```powershell
.\run-dev.ps1
```

### 5. 打开页面

- 前端开发地址：`http://127.0.0.1:5173`
- 后端托管地址：`http://127.0.0.1:8000`

开发时优先访问 `5173`。  
如果你先 build 前端并只跑后端，也可以直接访问 `8000`。

## 运行方式

### 开发模式

适合改页面、调接口、看实时日志：

```bat
run-dev.bat
```

### 轻量本地模式

先构建前端，再只跑后端和调度器：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1 start -RebuildFrontend
```

### 分开启动

如果你需要单独调试某一部分：

```powershell
python entrypoints\entrypoint-backend.py
python entrypoints\entrypoint-scheduler.py
cd web
npm run dev
```

### Docker

仓库带了 [`Dockerfile`](/E:/pycharmDevelop/bili-auto/Dockerfile) 和 [`docker-compose.yml`](/E:/pycharmDevelop/bili-auto/docker-compose.yml)：

```powershell
docker compose up -d --build
```

如果 `QTEASY_API_URL` 指向宿主机服务，Docker 内一般要写：

```env
QTEASY_API_URL=http://host.docker.internal:8001
```

## 配置说明

### 必填

| 变量 | 说明 |
| --- | --- |
| `ADMIN_AUTH_SECRET` | 后台登录态签名密钥 |
| `BILIBILI_COOKIE` | B 站抓取、下载、字幕、动态主凭证 |
| `OPENAI_API_KEY` | LLM API Key |
| `OPENAI_BASE_URL` | 兼容 OpenAI 的 API 地址 |
| `OPENAI_MODEL` | 默认模型名 |
| `FEISHU_APP_ID` | 飞书应用 ID |
| `FEISHU_APP_SECRET` | 飞书应用密钥 |
| `FEISHU_RECEIVE_ID` | 默认飞书接收目标 |
| `FEISHU_RECEIVE_ID_TYPE` | `chat_id` / `open_id` / `user_id` |

### 常见可选

| 变量 | 说明 |
| --- | --- |
| `refresh_token` | B 站 Cookie 自动续期使用，不填也能运行 |
| `DATABASE_SOURCE` | `sqlite` 或 `postgresql` |
| `SQLITE_DATABASE_URL` | SQLite 地址 |
| `POSTGRESQL_DATABASE_URL` | PostgreSQL 地址 |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `FFMPEG_LOCATION` | 手工指定 `ffmpeg` 路径 |

### 本地 ASR

| 变量 | 说明 |
| --- | --- |
| `ASR_PROVIDER` | `local_whisper` 或 `aliyun_bailian` |
| `WHISPER_MODEL` | `faster-whisper` 模型名 |
| `WHISPER_DEVICE` | `cpu` 或 `cuda` |
| `WHISPER_LOG_PROGRESS` | 是否打印识别进度 |
| `USE_WHISPER_CPP` | 是否优先使用 `whisper.cpp` |
| `WHISPER_CPP_CLI` | `whisper-cli` 路径 |
| `WHISPER_CPP_MODEL` | `whisper.cpp` 模型路径 |
| `LOCAL_ASR_ENGINE` | `whisper` 或 `qwen3_asr_0.6b` |
| `QWEN3_ASR_MODEL_SOURCE` | `modelscope` 或 `huggingface` |
| `QWEN3_ASR_MODEL_ID` | Qwen3-ASR 模型 ID |
| `QWEN3_ASR_MODEL_DIR` | 模型本地目录 |
| `QWEN3_ASR_HF_ENDPOINT` | Hugging Face 镜像地址 |

### 阿里云百炼 ASR

| 变量 | 说明 |
| --- | --- |
| `DASHSCOPE_API_KEY` | 百炼 API Key |
| `ALIYUN_OSS_ENDPOINT` | OSS Endpoint |
| `ALIYUN_OSS_BUCKET` | OSS Bucket |
| `ALIYUN_OSS_ACCESS_KEY_ID` | OSS AccessKey ID |
| `ALIYUN_OSS_ACCESS_KEY_SECRET` | OSS AccessKey Secret |
| `ALIYUN_OSS_PREFIX` | 临时音频对象前缀 |

### 小宇宙

| 变量 | 说明 |
| --- | --- |
| `XYZ_BASE_URL` | 小宇宙接口基础地址 |
| `XYZ_DEVICE_ID` | 设备 ID |
| `XYZ_ACCESS_TOKEN` | access token |
| `XYZ_REFRESH_TOKEN` | refresh token |
| `XYZ_CHECK_INTERVAL` | 检测周期 |
| `XYZ_BOOTSTRAP_RECENT_EPISODES` | 首次补抓集数 |
| `XYZ_MAX_PAGES_PER_POLL` | 单次翻页上限 |

### WeWe RSS

> 当前模块未完全实现，适合实验和内部使用，不建议当成稳定主链路。

| 变量 | 说明 |
| --- | --- |
| `WEWE_RSS_BASE_URL` | WeWe RSS 服务地址 |
| `WEWE_RSS_AUTH_CODE` | 管理接口授权码，可选 |
| `WEWE_RSS_CHECK_INTERVAL` | 检测周期 |

### Qteasy

> 当前模块未完全实现，页面和代理接口还在继续收敛。

| 变量 | 说明 |
| --- | --- |
| `QTEASY_API_URL` | Qteasy FastAPI 基础地址 |

### 调度相关

| 变量 | 说明 |
| --- | --- |
| `VIDEO_CHECK_INTERVAL` | 视频检测间隔（分钟） |
| `DYNAMIC_CHECK_INTERVAL` | 动态检测间隔（分钟） |
| `LOCAL_VIDEO_SCAN_DIRS` | 本地 `.flv` 扫描目录，分号分隔 |
| `LOCAL_VIDEO_SCAN_INTERVAL` | 本地视频扫描间隔 |
| `LOCAL_VIDEO_SCAN_PUSH_TARGET_ID` | 本地视频固定推送群 |

## 数据与目录

默认运行态目录：

- [`data`](/E:/pycharmDevelop/bili-auto/data)：数据库、缓存、下载文件
- [`logs`](/E:/pycharmDevelop/bili-auto/logs)：日志
- [`models`](/E:/pycharmDevelop/bili-auto/models)：本地模型目录

这些目录不建议提交到 Git。

## 常见问题

### 1. `refresh_token` 去哪里拿

这是 B 站登录态的 `refresh_token`，用于自动刷新 Cookie。  
没有它也能跑，只是不能自动续期。

### 2. 飞书发群时 `FEISHU_RECEIVE_ID_TYPE` 填什么

发群一般填：

```env
FEISHU_RECEIVE_ID_TYPE=chat_id
```

### 3. Docker 里连不到本机的 Qteasy

如果 Qteasy 跑在宿主机 `8001`，容器内通常要写：

```env
QTEASY_API_URL=http://host.docker.internal:8001
```

### 4. 为什么推送历史里不一定有全部动态

部分动态链路历史上不是统一经过推送历史落库，旧数据可能出现“已推送但无记录”的情况。

## 说明

- 根目录只保留一个 `.ps1` 和一个 `.bat` 作为外部启动入口：
  - [`run-dev.ps1`](/E:/pycharmDevelop/bili-auto/run-dev.ps1)
  - [`run-dev.bat`](/E:/pycharmDevelop/bili-auto/run-dev.bat)
- Python 入口脚本已经归类到 [`entrypoints`](/E:/pycharmDevelop/bili-auto/entrypoints)
- Hermes / OpenClaw 相关集成已从当前开源版本移除
- 企业微信推送已从当前开源版本移除

## 许可证

本仓库沿用 MIT License。详见 [`LICENSE`](/E:/pycharmDevelop/bili-auto/LICENSE)。
