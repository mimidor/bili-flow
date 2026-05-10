# Qteasy External API Contract

This document is generated from the current implementation in
`E:/pycharmDevelop/qteasy/qteasy_service/app.py`,
`E:/pycharmDevelop/qteasy/qteasy_service/store.py`,
`E:/pycharmDevelop/qteasy/qteasy_service/tasks.py`, and
`E:/pycharmDevelop/qteasy/qteasy_service/runtime.py`.

It describes the actual external API exposed by the qteasy service today.

## Base

- Default base URL: `http://127.0.0.1:8001`
- Content type:
  - request body: `application/json`
  - response body: `application/json`
- Response style:
  - most endpoints return raw JSON objects or arrays directly
  - there is no global `{ ok, data }` wrapper
- Authentication:
  - no extra API key layer is enabled in the current implementation

## Important compatibility note

`POST /backtests` currently creates jobs with `task_type = "qteasy.run"`.

That means:

- `GET /jobs?task_type=qteasy.run` can find jobs created by `POST /backtests`
- `GET /jobs?task_type=backtest.run` will not find those new jobs

Compatibility still exists in the worker registry for both:

- `qteasy.run`
- `backtest.run`

But the standard creation endpoint now writes `qteasy.run`.

## Job status enum

Possible `status` values:

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

## Shared job objects

### Job summary object

Returned by `GET /jobs` inside `items`.

```json
{
  "job_id": "8a3e3bf452ed4d49b30ca9e4f5f5d8c9",
  "task_type": "qteasy.run",
  "job_name": "backtest_demo",
  "status": "queued",
  "priority": 100,
  "progress": 0,
  "current_step": "queued",
  "worker_id": null,
  "attempts": 0,
  "created_at": "2026-05-03T14:30:00+08:00",
  "updated_at": "2026-05-03T14:30:00+08:00",
  "started_at": null,
  "finished_at": null
}
```

### Full job object

Returned by `GET /jobs/{job_id}`, `POST /jobs`, `POST /backtests`,
`POST /optimizations`, `POST /data/refill`, and `POST /jobs/{job_id}/cancel`.

```json
{
  "job_id": "8a3e3bf452ed4d49b30ca9e4f5f5d8c9",
  "task_type": "qteasy.run",
  "job_name": "backtest_demo",
  "status": "running",
  "priority": 100,
  "progress": 30,
  "current_step": "running qteasy.run",
  "payload": {
    "mode": 1,
    "job_name": "backtest_demo",
    "run_kwargs": {
      "asset_pool": ["000001.SZ"]
    }
  },
  "result": null,
  "error": null,
  "worker_id": "worker-123",
  "attempts": 1,
  "created_at": "2026-05-03T14:30:00+08:00",
  "updated_at": "2026-05-03T14:30:02+08:00",
  "started_at": "2026-05-03T14:30:01+08:00",
  "finished_at": null
}
```

## 1. Health and metadata

### `GET /health`

Purpose:

- health check

Response:

```json
{
  "status": "ok",
  "service": "qteasy-service",
  "version": "2.4.2"
}
```

### `GET /meta`

Purpose:

- service metadata
- runtime settings visible to callers
- supported task types

Response:

```json
{
  "settings": {
    "host": "0.0.0.0",
    "port": 8001,
    "db_path": "E:\\pycharmDevelop\\qteasy\\tmp\\qteasy_service.sqlite3",
    "worker_id": "worker-123",
    "log_level": "info"
  },
  "task_types": [
    "backtest.run",
    "data.refill",
    "optimization.run",
    "qteasy.refill",
    "qteasy.rpc",
    "qteasy.run",
    "rpc.call"
  ]
}
```

## 2. Configuration

### `GET /config/startup`

Purpose:

- return qteasy startup configuration

Query params:

- none

Response:

- raw JSON object from `qt.get_start_up_settings()`

Example:

```json
{
  "local_data_source": "database",
  "local_data_file_type": "feather"
}
```

### `POST /config/startup`

Purpose:

- update qteasy startup configuration

Request body:

- arbitrary JSON object
- each top-level key/value is passed as keyword args to `qt.update_start_up_setting(**payload)`

Example request:

```json
{
  "local_data_source": "database",
  "local_db_host": "127.0.0.1"
}
```

Response:

- raw JSON result from `qt.update_start_up_setting(**payload)`

### `GET /config/runtime`

Purpose:

- return qteasy runtime configuration

Response:

- raw JSON object from `qt.get_configurations()`

### `POST /config/runtime`

Purpose:

- update qteasy runtime configuration

Request body:

- arbitrary JSON object
- each top-level key/value is passed to `qt.configure(**payload)`

Example request:

```json
{
  "benchmark_asset": "000300.SH",
  "trade_batch_size": 100
}
```

Response:

- raw JSON result from `qt.configure(**payload)`

## 3. Built-in strategies

### `GET /strategies/builtins`

Purpose:

- list built-in strategies

Response:

- array of strategy summary objects

Example:

```json
[
  {
    "strategy_id": "macd",
    "doc": "MACD strategy documentation...",
    "summary": "MACD strategy documentation..."
  }
]
```

### `GET /strategies/builtins/{strategy_id}`

Purpose:

- fetch one built-in strategy

Path params:

- `strategy_id`: string

Response:

```json
{
  "strategy_id": "macd",
  "class_name": "MACD",
  "repr": "<MACD object>",
  "doc": "MACD strategy documentation..."
}
```

Error:

- `404` if strategy is not found

## 4. Data overview and lookup

### `GET /data/overview`

Purpose:

- return qteasy data source overview

Response:

- raw JSON result from `qt.get_data_overview()`

### `GET /data/table-overview`

Purpose:

- return overview for all tracked tables

Response:

- raw JSON result from `qt.get_table_overview()`

### `GET /data/table-info/{table_name}`

Purpose:

- return one table's metadata and overview

Path params:

- `table_name`: string

Response:

- raw JSON result from `qt.get_table_info(table_name)`

### `GET /data/basic-info`

Purpose:

- fuzzy or exact security lookup by code or name

Query params:

- `code_or_name`: required string
- `asset_types`: optional string
- `match_full_name`: optional bool, default `false`
- `printout`: optional bool, default `false`
- `verbose`: optional bool, default `false`

Response:

- raw JSON result from `qt.get_basic_info(...)`

### `GET /data/stock-info`

Purpose:

- stock-focused lookup by code or name

Query params:

- `code_or_name`: required string
- `asset_types`: optional string
- `match_full_name`: optional bool, default `false`
- `printout`: optional bool, default `false`
- `verbose`: optional bool, default `false`

Response:

- raw JSON result from `qt.get_stock_info(...)`

### `GET /data/filter/stocks`

Purpose:

- filter stock list

Query params:

- `date`: optional string, default `"today"`
- all other query params are passed through as `**kwargs` to `qt.filter_stocks(date=date, **kwargs)`

Common examples:

- `index=000300.SH`
- `industry=银行`
- `area=上海`

Response:

- raw JSON result from `qt.filter_stocks(...)`

### `GET /data/filter/stock-codes`

Purpose:

- return filtered stock code list

Query params:

- `date`: optional string, default `"today"`
- all other query params are passed through as `**kwargs` to `qt.filter_stock_codes(date=date, **kwargs)`

Response:

- raw JSON result from `qt.filter_stock_codes(...)`

### `GET /data/history`

Purpose:

- general historical data query

Query params:

- `htypes`: optional string
- `shares`: optional string
- `start`: optional string
- `end`: optional string
- `rows`: optional integer
- `freq`: optional string, default `"d"`
- `as_panel`: optional bool, default `true`
- `asset_type`: optional string
- `adj`: optional string
- `data_source`: optional string
- `b_days_only`: optional bool
- `trade_time_only`: optional bool
- `max_rows`: optional integer, range `1..5000`

Response:

- raw JSON result from `qt.get_history_data(**kwargs)`
- serialization may truncate table-like data to `max_rows`

### `GET /data/kline`

Purpose:

- K-line convenience query

Query params:

- `shares`: required string
- `start`: optional string
- `end`: optional string
- `rows`: optional integer
- `freq`: optional string, default `"d"`
- `adj`: optional string
- `asset_type`: optional string
- `as_panel`: optional bool, default `true`
- `b_days_only`: optional bool
- `trade_time_only`: optional bool
- `max_rows`: optional integer, range `1..5000`

Response:

- raw JSON result from `qt.get_kline(**kwargs)`
- serialization may truncate table-like data to `max_rows`

### `GET /live/accounts`

Purpose:

- return live trading account list

Response:

- raw JSON result from `qt.live_trade_accounts()`

## 5. Reports and files

### `GET /reports/trade-logs`

Purpose:

- list generated trade log CSV files

Response:

```json
{
  "directory": "E:\\pycharmDevelop\\qteasy\\tmp\\trade_logs",
  "files": [
    {
      "name": "trade_log_demo_20260503.csv",
      "path": "E:\\pycharmDevelop\\qteasy\\tmp\\trade_logs\\trade_log_demo_20260503.csv",
      "size": 12345,
      "mtime": 1777790000.123
    }
  ]
}
```

### `GET /reports/trade-logs/{filename}`

Purpose:

- download one trade log CSV file

Path params:

- `filename`: required string

Response:

- file download response

Error:

- `404` if file does not exist

## 6. Job list and job control

### `GET /jobs`

Purpose:

- list jobs

Query params:

- `limit`: optional integer, default `100`, range `1..1000`
- `offset`: optional integer, default `0`, range `0..100000`
- `status`: optional string
- `task_type`: optional string

Response:

```json
{
  "items": [
    {
      "job_id": "8a3e3bf452ed4d49b30ca9e4f5f5d8c9",
      "task_type": "qteasy.run",
      "job_name": "backtest_demo",
      "status": "queued",
      "priority": 100,
      "progress": 0,
      "current_step": "queued",
      "worker_id": null,
      "attempts": 0,
      "created_at": "2026-05-03T14:30:00+08:00",
      "updated_at": "2026-05-03T14:30:00+08:00",
      "started_at": null,
      "finished_at": null
    }
  ],
  "limit": 20,
  "offset": 0
}
```

Important:

- the list response does not include `payload`, `result`, or `error`
- use `GET /jobs/{job_id}` for the full record

### `GET /jobs/{job_id}`

Purpose:

- fetch full job detail

Path params:

- `job_id`: required string

Response:

- full job object

Error:

- `404` if job does not exist

### `POST /jobs`

Purpose:

- create a generic job directly

Request body:

- `task_type`: required string
- `payload`: optional object, default `{}`
- `job_name`: optional string
- `priority`: optional integer, default `100`

Example request:

```json
{
  "task_type": "qteasy.rpc",
  "job_name": "rpc_job_1",
  "priority": 50,
  "payload": {
    "name": "get_configurations",
    "kwargs": {}
  }
}
```

Response:

- full job object

Errors:

- `400` if `task_type` is missing
- `400` if `payload` is not an object

### `POST /jobs/{job_id}/cancel`

Purpose:

- cancel a job

Path params:

- `job_id`: required string

Response:

- full job object after cancel attempt

Behavior:

- if current status is `queued` or `running`, status becomes `cancelled`
- otherwise the existing job is returned unchanged

Error:

- `404` if job does not exist

## 7. Async task creation endpoints

### `POST /data/refill`

Purpose:

- create a data refill job

Creates:

- `task_type = "data.refill"`

Request body:

- accepts any JSON object
- recommended fields:
  - `job_name`: optional string
  - `priority`: optional integer
  - `tables`: required in practice, string or array
  - `table`: accepted alias
- all other fields are forwarded into `qt.refill_data_source(...)`

Example request:

```json
{
  "job_name": "daily_refill",
  "priority": 50,
  "tables": ["trade_calendar", "stock_daily"],
  "channel": "tushare",
  "start_date": "20240101",
  "end_date": "20241231"
}
```

Response:

- full job object

Result payload after success:

```json
{
  "tables": ["trade_calendar", "stock_daily"],
  "count": 2,
  "results": [
    {
      "table": "trade_calendar",
      "result": {}
    }
  ]
}
```

### `POST /backtests`

Purpose:

- create a backtest job

Creates:

- `task_type = "qteasy.run"`

Default behavior:

- `mode` defaults to `1`
- `run_kwargs` defaults to `{}`

Request body:

- accepts a JSON object
- supported top-level strategy/operator fields:
  - `mode`
  - `job_name`
  - `name`
  - `priority`
  - `operator`
  - `strategies`
  - `strategy`
  - `strategy_id`
  - `strategy_path`
  - `strategy_kwargs`
  - `signal_type`
  - `op_type`
  - `group_merge_type`
  - `run_freq`
  - `run_timing`
  - `run_kwargs`
- any other top-level fields not in the reserved set are merged into runtime `run_kwargs`

Supported strategy forms:

- built-in:

```json
{
  "strategies": {
    "kind": "built_in",
    "strategy_id": "macd"
  }
}
```

- import path:

```json
{
  "strategies": {
    "kind": "import",
    "path": "qteasy.kdj_threshold:JThresholdStg",
    "kwargs": {
      "buy_level": -10,
      "sell_level": 50
    }
  }
}
```

Example request:

```json
{
  "job_name": "kdj_backtest_demo",
  "mode": 1,
  "strategies": {
    "kind": "import",
    "path": "qteasy.kdj_threshold:JThresholdStg",
    "kwargs": {
      "buy_level": -10,
      "sell_level": 50
    }
  },
  "run_kwargs": {
    "asset_type": "E",
    "asset_pool": ["000001.SZ"],
    "invest_start": "20200101",
    "invest_end": "20241231",
    "trade_log": true,
    "visual": false
  }
}
```

Response:

- full job object

Result payload after success:

```json
{
  "mode": 1,
  "operator_name": "kdj_backtest_demo",
  "run_kwargs": {
    "asset_type": "E",
    "asset_pool": ["000001.SZ"],
    "invest_start": "20200101",
    "invest_end": "20241231",
    "trade_log": true,
    "visual": false,
    "mode": 1
  },
  "artifacts": {
    "trade_log": [],
    "trade_summary": [],
    "value_curve": []
  },
  "result": {}
}
```

### `POST /optimizations`

Purpose:

- create an optimization job

Creates:

- `task_type = "optimization.run"`

Default behavior:

- `mode` defaults to `2`
- `run_kwargs` defaults to `{}`

Request body:

- same structure as `POST /backtests`

Example request:

```json
{
  "job_name": "macd_optimization_demo",
  "mode": 2,
  "strategies": {
    "kind": "built_in",
    "strategy_id": "macd"
  },
  "run_kwargs": {
    "asset_type": "E",
    "asset_pool": ["000001.SZ"],
    "invest_start": "20200101",
    "invest_end": "20241231"
  }
}
```

Response:

- full job object

## 8. RPC

### `POST /rpc/{name}`

Purpose:

- call one whitelisted qteasy function synchronously

Path params:

- `name`: required function name

Request body:

- JSON object, used as `kwargs`

Example request:

```json
{
  "verbose": false
}
```

Equivalent internal call:

```python
call_rpc_function(name, kwargs)
```

Response:

- raw JSON-serializable function result

## 9. Service capabilities

### `GET /service/functions`

Purpose:

- return service capability registry

Response shape:

```json
{
  "direct": [
    "health",
    "meta",
    "config/startup",
    "config/runtime",
    "strategies/builtins",
    "data/overview",
    "data/table-overview",
    "data/table-info/{table_name}",
    "data/basic-info",
    "data/stock-info",
    "data/filter/stocks",
    "data/filter/stock-codes",
    "data/history",
    "data/kline",
    "live/accounts",
    "reports/trade-logs"
  ],
  "jobs": [
    "data.refill",
    "qteasy.run",
    "optimization.run",
    "qteasy.rpc"
  ],
  "rpc": [
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
    "rotate_trade_logs"
  ],
  "task_types": [
    "backtest.run",
    "data.refill",
    "optimization.run",
    "qteasy.refill",
    "qteasy.rpc",
    "qteasy.run",
    "rpc.call"
  ]
}
```

## 10. Error behavior

Common HTTP errors:

- `400`
  - invalid request body
  - missing required `task_type`
  - non-object `payload`
- `404`
  - missing strategy
  - missing job
  - missing trade log file
- `500`
  - uncaught internal runtime error

Task-level failure behavior:

- long-running task endpoints still return `200` on creation
- actual execution failures appear later in `GET /jobs/{job_id}`:
  - `status = "failed"`
  - `error = "..."` filled

## 11. Upstream integration checklist

The upstream caller should verify these exact assumptions:

- `POST /backtests` creates `task_type = "qteasy.run"`, not `backtest.run`
- `GET /jobs` returns summary rows only
- `GET /jobs/{job_id}` returns full detail including `payload`, `result`, `error`
- qteasy responses are raw JSON, not wrapped in `{ ok, data }`
- `GET /reports/trade-logs/{filename}` is a file download response, not JSON
- `POST /rpc/{name}` is synchronous and returns the function result directly
