from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.database import QteasyBacktestResult, QteasyJobSnapshot


SERIES_LABEL_CANDIDATES = ("date", "datetime", "time", "timestamp", "index", "x", "label")
SERIES_VALUE_CANDIDATES = ("value", "nav", "equity", "drawdown", "return", "y", "amount")


def _dumps(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return json.dumps(str(value), ensure_ascii=False)


def _loads(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _unwrap_payload(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        if payload.get("data") is not None:
            return payload["data"]
        if payload.get("result") is not None:
            return payload["result"]
    return payload


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip().replace("%", "")
        if not raw:
            return None
        try:
            return float(raw)
        except Exception:
            return None
    return None


def _pick(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _normalize_point(label: Any, value: Any) -> dict[str, Any] | None:
    y = _coerce_float(value)
    if y is None:
        return None
    x = _coerce_str(label) if label is not None else None
    if x is None:
        x = str(label) if label is not None else ""
    return {"label": x, "value": y}


def _normalize_series(series: Any) -> list[dict[str, Any]]:
    if series is None:
        return []

    if isinstance(series, Mapping):
        label_list = None
        value_list = None
        for key in SERIES_LABEL_CANDIDATES:
            candidate = series.get(key)
            if isinstance(candidate, list):
                label_list = candidate
                break
        for key in SERIES_VALUE_CANDIDATES:
            candidate = series.get(key)
            if isinstance(candidate, list):
                value_list = candidate
                break
        if label_list is not None and value_list is not None and len(label_list) == len(value_list):
            normalized = []
            for label, value in zip(label_list, value_list):
                point = _normalize_point(label, value)
                if point:
                    normalized.append(point)
            return normalized

        normalized = []
        for key, value in series.items():
            point = _normalize_point(key, value)
            if point:
                normalized.append(point)
        return normalized

    if isinstance(series, list):
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(series):
            if isinstance(item, Mapping):
                label = _pick(item, *SERIES_LABEL_CANDIDATES)
                value = _pick(item, *SERIES_VALUE_CANDIDATES)
                if value is None:
                    numeric_candidates = [(k, _coerce_float(v)) for k, v in item.items() if _coerce_float(v) is not None]
                    if numeric_candidates:
                        _, numeric_value = numeric_candidates[0]
                        value = numeric_value
                point = _normalize_point(label if label is not None else index + 1, value)
                if point:
                    normalized.append(point)
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                point = _normalize_point(item[0], item[1])
                if point:
                    normalized.append(point)
            else:
                point = _normalize_point(index + 1, item)
                if point:
                    normalized.append(point)
        return normalized

    return []


def _extract_metrics(raw_result: Any) -> dict[str, Any]:
    if not isinstance(raw_result, Mapping):
        return {}
    for key in ("metrics", "metric", "performance", "stats", "statistics", "summary", "indicators"):
        candidate = raw_result.get(key)
        if isinstance(candidate, Mapping):
            return dict(candidate)
    return {
        key: value
        for key, value in raw_result.items()
        if isinstance(value, (int, float, str, bool))
        and key not in {"equity_curve", "benchmark_curve", "drawdown_curve", "returns", "daily_returns"}
    }


def _extract_first_series(raw_result: Any, *keys: str) -> list[dict[str, Any]]:
    if not isinstance(raw_result, Mapping):
        return []
    for key in keys:
        if key in raw_result:
            normalized = _normalize_series(raw_result.get(key))
            if normalized:
                return normalized
    return []


def _extract_dataframe_series(raw_result: Any, table_key: str, value_key: str) -> list[dict[str, Any]]:
    if not isinstance(raw_result, Mapping):
        return []
    table = raw_result.get(table_key)
    if not isinstance(table, Mapping):
        return []

    records = table.get("records")
    index_values = table.get("index")
    if not isinstance(records, list):
        return []

    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            continue
        label = None
        if isinstance(index_values, list) and index < len(index_values):
            label = index_values[index]
        if label is None:
            label = index + 1
        point = _normalize_point(label, record.get(value_key))
        if point:
            normalized.append(point)
    return normalized


def _compute_return_histogram(source_series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not source_series:
        return []
    returns: list[float] = []
    previous: float | None = None
    for point in source_series:
        value = _coerce_float(point.get("value"))
        if value is None:
            continue
        if previous not in (None, 0):
            returns.append((value - previous) / previous)
        previous = value
    if not returns:
        return []

    bucket_count = min(12, max(5, len(returns) // 4))
    min_value = min(returns)
    max_value = max(returns)
    if min_value == max_value:
        return [{"label": f"{min_value:.2%}", "value": len(returns)}]

    step = (max_value - min_value) / bucket_count
    buckets = [0 for _ in range(bucket_count)]
    labels: list[str] = []
    for index in range(bucket_count):
        start = min_value + index * step
        end = max_value if index == bucket_count - 1 else min_value + (index + 1) * step
        labels.append(f"{start:.2%} ~ {end:.2%}")
    for item in returns:
        bucket_index = min(int((item - min_value) / step), bucket_count - 1)
        buckets[bucket_index] += 1
    return [{"label": labels[index], "value": buckets[index]} for index in range(bucket_count)]


def _collect_strategy_metadata(payload: Mapping[str, Any] | None) -> tuple[str | None, str | None]:
    if not isinstance(payload, Mapping):
        return None, None
    strategies = payload.get("strategies")
    if not isinstance(strategies, Mapping):
        return None, None
    strategy_id = _coerce_str(strategies.get("strategy_id"))
    strategy_path = _coerce_str(strategies.get("path"))
    return strategy_id, strategy_path


def _collect_run_kwargs(payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    run_kwargs = payload.get("run_kwargs")
    return run_kwargs if isinstance(run_kwargs, Mapping) else {}


def _build_standardized_result(job: Mapping[str, Any]) -> dict[str, Any]:
    payload = _unwrap_payload(job.get("payload"))
    if not isinstance(payload, Mapping):
        payload = {}

    raw_result = _unwrap_payload(job.get("result"))
    if not isinstance(raw_result, Mapping):
        raw_result = {"raw": raw_result}

    strategy_id, strategy_path = _collect_strategy_metadata(payload)
    run_kwargs = _collect_run_kwargs(payload)
    equity_curve = _extract_first_series(
        raw_result,
        "equity_curve",
        "equity",
        "nav",
        "portfolio_value",
        "asset_value",
        "value_curve",
    )
    benchmark_curve = _extract_first_series(
        raw_result,
        "benchmark_curve",
        "benchmark",
        "benchmark_equity",
        "benchmark_nav",
    )
    drawdown_curve = _extract_first_series(
        raw_result,
        "drawdown_curve",
        "drawdown",
        "max_drawdown_series",
    )
    if not equity_curve:
        equity_curve = _extract_dataframe_series(raw_result, "complete_values", "value")
    if not benchmark_curve:
        benchmark_curve = _extract_dataframe_series(raw_result, "complete_values", "benchmark")
    if not drawdown_curve:
        drawdown_curve = _extract_dataframe_series(raw_result, "complete_values", "underwater")
    if not drawdown_curve and equity_curve:
        peak = None
        computed_drawdown: list[dict[str, Any]] = []
        for point in equity_curve:
            value = _coerce_float(point.get("value"))
            if value is None:
                continue
            peak = value if peak is None else max(peak, value)
            drawdown = 0.0 if not peak else (value - peak) / peak
            computed_drawdown.append({"label": point.get("label"), "value": drawdown})
        drawdown_curve = computed_drawdown

    returns_series = _extract_first_series(raw_result, "returns", "daily_returns", "return_series")
    return_histogram = _compute_return_histogram(returns_series or equity_curve)

    metrics = _extract_metrics(raw_result)
    parse_notes: list[str] = []
    if not equity_curve:
        parse_notes.append("未识别到净值序列")
    if not benchmark_curve:
        parse_notes.append("未识别到基准序列")
    if not drawdown_curve:
        parse_notes.append("未识别到回撤序列")

    return {
        "job_id": _coerce_str(job.get("job_id")) or "",
        "task_type": _coerce_str(job.get("task_type")) or "",
        "job_name": _coerce_str(job.get("job_name")),
        "status": _coerce_str(job.get("status")) or "unknown",
        "strategy_id": strategy_id,
        "strategy_path": strategy_path,
        "symbol_pool": run_kwargs.get("asset_pool") if isinstance(run_kwargs.get("asset_pool"), list) else [],
        "benchmark": _coerce_str(run_kwargs.get("benchmark")) or _coerce_str(raw_result.get("benchmark_name")) or _coerce_str(raw_result.get("benchmark")),
        "invest_start": _coerce_str(run_kwargs.get("invest_start")) or _coerce_str(run_kwargs.get("start_date")),
        "invest_end": _coerce_str(run_kwargs.get("invest_end")) or _coerce_str(run_kwargs.get("end_date")),
        "payload": payload,
        "raw_result": raw_result,
        "metrics": metrics,
        "equity_curve": equity_curve,
        "benchmark_curve": benchmark_curve,
        "drawdown_curve": drawdown_curve,
        "return_histogram": return_histogram,
        "parsed_ok": bool(equity_curve or metrics),
        "parse_message": "；".join(parse_notes) if parse_notes else None,
    }


def upsert_job_snapshot(
    db: Session,
    job: Mapping[str, Any],
    *,
    fallback_task_type: str | None = None,
    fallback_payload: Mapping[str, Any] | None = None,
) -> QteasyJobSnapshot:
    job_id = _coerce_str(job.get("job_id"))
    if not job_id:
        raise ValueError("Qteasy job payload is missing job_id")

    row = db.query(QteasyJobSnapshot).filter(QteasyJobSnapshot.job_id == job_id).first()
    if row is None:
        row = QteasyJobSnapshot(job_id=job_id, task_type=fallback_task_type or _coerce_str(job.get("task_type")) or "unknown")
        db.add(row)

    row.task_type = fallback_task_type or _coerce_str(job.get("task_type")) or row.task_type or "unknown"
    row.job_name = _coerce_str(job.get("job_name")) or row.job_name
    row.status = _coerce_str(job.get("status")) or row.status or "queued"
    row.priority = job.get("priority") if isinstance(job.get("priority"), int) else row.priority
    row.progress = job.get("progress") if isinstance(job.get("progress"), int) else row.progress
    row.current_step = _coerce_str(job.get("current_step"))
    row.error = _coerce_str(job.get("error"))
    row.worker_id = _coerce_str(job.get("worker_id"))
    row.attempts = job.get("attempts") if isinstance(job.get("attempts"), int) else row.attempts
    payload = _unwrap_payload(job.get("payload"))
    row.payload_json = _dumps(payload if payload is not None else fallback_payload)
    row.raw_result_json = _dumps(_unwrap_payload(job.get("result")))
    row.started_at = _parse_datetime(job.get("started_at")) or row.started_at
    row.finished_at = _parse_datetime(job.get("finished_at")) or row.finished_at
    row.last_synced_at = datetime.utcnow()
    return row


def sync_backtest_result(db: Session, job: Mapping[str, Any]) -> QteasyBacktestResult:
    standardized = _build_standardized_result(job)
    job_id = standardized["job_id"]
    if not job_id:
        raise ValueError("Qteasy result payload is missing job_id")

    row = db.query(QteasyBacktestResult).filter(QteasyBacktestResult.job_id == job_id).first()
    if row is None:
        row = QteasyBacktestResult(job_id=job_id, task_type=standardized["task_type"] or "qteasy.run")
        db.add(row)

    row.task_type = standardized["task_type"] or row.task_type
    row.job_name = standardized["job_name"]
    row.strategy_id = standardized["strategy_id"]
    row.strategy_path = standardized["strategy_path"]
    row.symbol_pool_json = _dumps(standardized["symbol_pool"])
    row.benchmark = standardized["benchmark"]
    row.invest_start = standardized["invest_start"]
    row.invest_end = standardized["invest_end"]
    row.status = standardized["status"]
    row.payload_json = _dumps(standardized["payload"])
    row.raw_result_json = _dumps(standardized["raw_result"])
    row.metrics_json = _dumps(standardized["metrics"])
    row.equity_curve_json = _dumps({
        "equity": standardized["equity_curve"],
        "benchmark": standardized["benchmark_curve"],
    })
    row.drawdown_curve_json = _dumps(standardized["drawdown_curve"])
    row.return_histogram_json = _dumps(standardized["return_histogram"])
    row.parsed_ok = bool(standardized["parsed_ok"])
    row.parse_message = standardized["parse_message"]
    row.last_synced_at = datetime.utcnow()
    return row


def serialize_qteasy_job_snapshot(row: QteasyJobSnapshot) -> dict[str, Any]:
    return {
        "id": row.id,
        "job_id": row.job_id,
        "task_type": row.task_type,
        "job_name": row.job_name,
        "status": row.status,
        "priority": row.priority,
        "progress": row.progress,
        "current_step": row.current_step,
        "error": row.error,
        "payload": _loads(row.payload_json),
        "raw_result": _loads(row.raw_result_json),
        "worker_id": row.worker_id,
        "attempts": row.attempts,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_qteasy_backtest_result(row: QteasyBacktestResult) -> dict[str, Any]:
    equity_curve = _loads(row.equity_curve_json) or {}
    return {
        "id": row.id,
        "job_id": row.job_id,
        "task_type": row.task_type,
        "job_name": row.job_name,
        "strategy_id": row.strategy_id,
        "strategy_path": row.strategy_path,
        "symbol_pool": _loads(row.symbol_pool_json) or [],
        "benchmark": row.benchmark,
        "invest_start": row.invest_start,
        "invest_end": row.invest_end,
        "status": row.status,
        "payload": _loads(row.payload_json),
        "raw_result": _loads(row.raw_result_json),
        "metrics": _loads(row.metrics_json) or {},
        "equity_curve": equity_curve.get("equity") if isinstance(equity_curve, Mapping) else [],
        "benchmark_curve": equity_curve.get("benchmark") if isinstance(equity_curve, Mapping) else [],
        "drawdown_curve": _loads(row.drawdown_curve_json) or [],
        "return_histogram": _loads(row.return_histogram_json) or [],
        "parsed_ok": row.parsed_ok,
        "parse_message": row.parse_message,
        "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_backtest_results(
    db: Session,
    *,
    page: int,
    page_size: int,
    job_ids: list[str] | None = None,
    job_name: str | None = None,
    strategy_keyword: str | None = None,
    status: str | None = None,
) -> tuple[int, list[QteasyBacktestResult]]:
    query = db.query(QteasyBacktestResult).order_by(QteasyBacktestResult.updated_at.desc(), QteasyBacktestResult.id.desc())
    if job_ids:
        query = query.filter(QteasyBacktestResult.job_id.in_(job_ids))
    if job_name:
        query = query.filter(QteasyBacktestResult.job_name.ilike(f"%{job_name}%"))
    if strategy_keyword:
        keyword = f"%{strategy_keyword}%"
        query = query.filter(
            (QteasyBacktestResult.strategy_id.ilike(keyword))
            | (QteasyBacktestResult.strategy_path.ilike(keyword))
        )
    if status:
        query = query.filter(QteasyBacktestResult.status == status)
    total = query.order_by(None).count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return total, items


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value))
        except Exception:
            return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            return datetime.fromisoformat(raw)
        except Exception:
            return None
    return None
