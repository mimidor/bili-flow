from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response

from app.models.database import QteasyBacktestResult, QteasyJobSnapshot, SessionLocal
from app.services.qteasy_results import (
    list_backtest_results,
    serialize_qteasy_backtest_result,
    serialize_qteasy_job_snapshot,
    sync_backtest_result,
    upsert_job_snapshot,
)
from config import Config

router = APIRouter(prefix="/qteasy", tags=["qteasy"])
_ASYNC_CLIENT_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
_async_clients: dict[bool, httpx.AsyncClient] = {}
_async_client_lock = asyncio.Lock()
_BACKTEST_TASK_TYPES = {"qteasy.run", "backtest.run"}


def _result_list_item(row: QteasyBacktestResult) -> dict[str, Any]:
    payload = serialize_qteasy_backtest_result(row)
    payload.pop("payload", None)
    payload.pop("raw_result", None)
    payload.pop("equity_curve", None)
    payload.pop("benchmark_curve", None)
    payload.pop("drawdown_curve", None)
    payload.pop("return_histogram", None)
    return payload


def _base_url() -> str:
    raw = str(getattr(Config, "QTEASY_API_URL", "") or "").strip().rstrip("/")
    if raw and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        raw = f"http://{raw}"
    return raw


def _should_bypass_env_proxy(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").strip().lower()
    return host in {"127.0.0.1", "localhost", "::1"}


async def _get_async_client(*, trust_env: bool) -> httpx.AsyncClient:
    client = _async_clients.get(trust_env)
    if client is not None:
        return client

    async with _async_client_lock:
        client = _async_clients.get(trust_env)
        if client is None:
            client = httpx.AsyncClient(timeout=_ASYNC_CLIENT_TIMEOUT, trust_env=trust_env)
            _async_clients[trust_env] = client
    return client


async def _request_remote(
    method: str,
    path: str,
    request: Request,
    json_body: Any | None = None,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    base_url = _base_url()
    if not base_url:
        raise HTTPException(status_code=503, detail="Qteasy API is not configured")

    url = f"{base_url}/{path.lstrip('/')}"
    request_kwargs: dict[str, Any] = {
        "params": params if params is not None else dict(request.query_params),
    }
    if json_body is not None:
        request_kwargs["json"] = json_body

    # Local qteasy traffic should never detour through the user's HTTP proxy.
    client = await _get_async_client(trust_env=not _should_bypass_env_proxy(base_url))
    return await client.request(method, url, **request_kwargs)


def _build_passthrough_headers(response: httpx.Response) -> dict[str, str]:
    headers: dict[str, str] = {}
    for header_name in ("content-disposition", "cache-control", "etag", "last-modified"):
        header_value = response.headers.get(header_name)
        if header_value:
            headers[header_name] = header_value
    return headers


def _parse_json_payload(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return {} if not response.text else {"ok": response.is_success, "text": response.text}


def _to_fastapi_response(response: httpx.Response) -> Response:
    content_type = response.headers.get("content-type", "")
    passthrough_headers = _build_passthrough_headers(response)

    if "application/json" in content_type or content_type.endswith("+json"):
        return JSONResponse(
            status_code=response.status_code,
            content=_parse_json_payload(response),
            headers=passthrough_headers or None,
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=content_type or None,
        headers=passthrough_headers or None,
    )


def _unwrap_remote_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        if payload.get("job_id") is not None:
            return payload
        if payload.get("data") is not None:
            return payload["data"]
        if payload.get("result") is not None:
            return payload["result"]
    return payload


def _sanitize_jobs_query_params(request: Request) -> dict[str, Any]:
    params = dict(request.query_params)
    if params.get("task_type") == "backtest.run":
        params["task_type"] = "qteasy.run"
    params.pop("job_name", None)
    return params


def _sync_job_list_to_db(payload: Any) -> None:
    items = _unwrap_remote_payload(payload)
    if isinstance(items, dict) and isinstance(items.get("items"), list):
        items = items["items"]
    if not isinstance(items, list):
        return

    db = SessionLocal()
    try:
        for item in items:
            if isinstance(item, dict):
                upsert_job_snapshot(db, item)
        db.commit()
    finally:
        db.close()


def _sync_job_to_db(job_payload: Any, *, fallback_task_type: str | None = None, fallback_payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    job = _unwrap_remote_payload(job_payload)
    if not isinstance(job, dict):
        return None

    db = SessionLocal()
    try:
        upsert_job_snapshot(db, job, fallback_task_type=fallback_task_type, fallback_payload=fallback_payload)
        stored_result = None
        task_type = str(job.get("task_type") or fallback_task_type or "")
        status = str(job.get("status") or "")
        if task_type in _BACKTEST_TASK_TYPES and status in {"succeeded", "failed", "cancelled"}:
            stored_result = serialize_qteasy_backtest_result(sync_backtest_result(db, job))
        db.commit()
        return stored_result
    finally:
        db.close()


async def _proxy(method: str, path: str, request: Request, json_body: Any | None = None) -> Response:
    try:
        response = await _request_remote(method, path, request, json_body)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})
    return _to_fastapi_response(response)


@router.get("/health")
async def health(request: Request) -> Response:
    return await _proxy("GET", "health", request)


@router.get("/meta")
async def meta(request: Request) -> Response:
    return await _proxy("GET", "meta", request)


@router.get("/config/startup")
async def get_startup_config(request: Request) -> Response:
    return await _proxy("GET", "config/startup", request)


@router.post("/config/startup")
async def update_startup_config(request: Request, payload: dict[str, Any] | None = Body(default=None)) -> Response:
    return await _proxy("POST", "config/startup", request, payload or {})


@router.get("/config/runtime")
async def get_runtime_config(request: Request) -> Response:
    return await _proxy("GET", "config/runtime", request)


@router.post("/config/runtime")
async def update_runtime_config(request: Request, payload: dict[str, Any] | None = Body(default=None)) -> Response:
    return await _proxy("POST", "config/runtime", request, payload or {})


@router.get("/strategies/builtins")
async def list_builtin_strategies(request: Request) -> Response:
    return await _proxy("GET", "strategies/builtins", request)


@router.get("/strategies/builtins/{strategy_id}")
async def get_builtin_strategy(strategy_id: str, request: Request) -> Response:
    return await _proxy("GET", f"strategies/builtins/{strategy_id}", request)


@router.get("/strategies/custom")
async def list_custom_strategies(request: Request) -> Response:
    return await _proxy("GET", "strategies/custom", request)


@router.get("/strategies/custom/{name}")
async def get_custom_strategy(name: str, request: Request) -> Response:
    return await _proxy("GET", f"strategies/custom/{name}", request)


@router.get("/data/overview")
async def data_overview(request: Request) -> Response:
    return await _proxy("GET", "data/overview", request)


@router.get("/data/table-overview")
async def table_overview(request: Request) -> Response:
    return await _proxy("GET", "data/table-overview", request)


@router.get("/data/table-info/{table_name}")
async def table_info(table_name: str, request: Request) -> Response:
    return await _proxy("GET", f"data/table-info/{table_name}", request)


@router.get("/data/basic-info")
async def basic_info(request: Request) -> Response:
    return await _proxy("GET", "data/basic-info", request)


@router.get("/data/stock-info")
async def stock_info(request: Request) -> Response:
    return await _proxy("GET", "data/stock-info", request)


@router.get("/data/filter/stocks")
async def filter_stocks(request: Request) -> Response:
    return await _proxy("GET", "data/filter/stocks", request)


@router.get("/data/filter/stock-codes")
async def filter_stock_codes(request: Request) -> Response:
    return await _proxy("GET", "data/filter/stock-codes", request)


@router.get("/data/history")
async def history(request: Request) -> Response:
    return await _proxy("GET", "data/history", request)


@router.get("/data/kline")
async def kline(request: Request) -> Response:
    return await _proxy("GET", "data/kline", request)


@router.get("/live/accounts")
async def live_accounts(request: Request) -> Response:
    return await _proxy("GET", "live/accounts", request)


@router.post("/data/refill")
async def data_refill(request: Request, payload: dict[str, Any] | None = Body(default=None)) -> Response:
    return await _proxy("POST", "data/refill", request, payload or {})


@router.post("/backtests")
async def create_backtest(request: Request, payload: dict[str, Any] | None = Body(default=None)) -> Response:
    normalized_payload = payload or {}
    try:
        response = await _request_remote("POST", "backtests", request, normalized_payload)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})
    response_payload = _parse_json_payload(response)
    _sync_job_to_db(response_payload, fallback_task_type="qteasy.run", fallback_payload=normalized_payload)
    return _to_fastapi_response(response)


@router.post("/optimizations")
async def create_optimization(request: Request, payload: dict[str, Any] | None = Body(default=None)) -> Response:
    normalized_payload = payload or {}
    try:
        response = await _request_remote("POST", "optimizations", request, normalized_payload)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})
    response_payload = _parse_json_payload(response)
    _sync_job_to_db(response_payload, fallback_task_type="optimization.run", fallback_payload=normalized_payload)
    return _to_fastapi_response(response)


@router.get("/jobs")
async def list_jobs(request: Request) -> Response:
    try:
        response = await _request_remote("GET", "jobs", request, params=_sanitize_jobs_query_params(request))
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})
    response_payload = _parse_json_payload(response)
    _sync_job_list_to_db(response_payload)
    return _to_fastapi_response(response)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> Response:
    try:
        response = await _request_remote("GET", f"jobs/{job_id}", request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})
    response_payload = _parse_json_payload(response)
    _sync_job_to_db(response_payload)
    return _to_fastapi_response(response)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, request: Request) -> Response:
    return await _proxy("POST", f"jobs/{job_id}/cancel", request, {})


@router.get("/results")
async def list_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    job_ids: str | None = Query(default=None),
    status: str | None = Query(default=None),
    job_name: str | None = Query(default=None),
    strategy_keyword: str | None = Query(default=None),
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        job_id_list = [item.strip() for item in (job_ids or "").split(",") if item.strip()]
        total, rows = list_backtest_results(
            db,
            page=page,
            page_size=page_size,
            job_ids=job_id_list or None,
            status=status,
            job_name=job_name,
            strategy_keyword=strategy_keyword,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_result_list_item(row) for row in rows],
        }
    finally:
        db.close()


@router.get("/results/{job_id}")
async def get_result(job_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        row = db.query(QteasyBacktestResult).filter_by(job_id=job_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Stored backtest result not found")
        return serialize_qteasy_backtest_result(row)
    finally:
        db.close()


@router.get("/results/{job_id}/charts")
async def get_result_charts(job_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        row = db.query(QteasyBacktestResult).filter_by(job_id=job_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Stored backtest result not found")
        payload = serialize_qteasy_backtest_result(row)
        return {
            "job_id": job_id,
            "metrics": payload.get("metrics") or {},
            "equity_curve": payload.get("equity_curve") or [],
            "benchmark_curve": payload.get("benchmark_curve") or [],
            "drawdown_curve": payload.get("drawdown_curve") or [],
            "return_histogram": payload.get("return_histogram") or [],
            "parsed_ok": payload.get("parsed_ok"),
            "parse_message": payload.get("parse_message"),
        }
    finally:
        db.close()


@router.post("/results/{job_id}/sync")
async def sync_result(job_id: str, request: Request) -> dict[str, Any]:
    try:
        response = await _request_remote("GET", f"jobs/{job_id}", request)
    except HTTPException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    payload = _parse_json_payload(response)
    stored_result = _sync_job_to_db(payload)

    db = SessionLocal()
    try:
        snapshot_row = db.query(QteasyJobSnapshot).filter_by(job_id=job_id).first()
        return {
            "job": serialize_qteasy_job_snapshot(snapshot_row) if snapshot_row else None,
            "result": stored_result,
        }
    finally:
        db.close()


@router.get("/reports/trade-logs")
async def list_trade_logs(request: Request) -> Response:
    return await _proxy("GET", "reports/trade-logs", request)


@router.get("/reports/trade-logs/{filename:path}")
async def get_trade_log(filename: str, request: Request) -> Response:
    return await _proxy("GET", f"reports/trade-logs/{filename}", request)


@router.post("/rpc/{name}")
async def call_rpc(name: str, request: Request, payload: dict[str, Any] | None = Body(default=None)) -> Response:
    return await _proxy("POST", f"rpc/{name}", request, payload or {})


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_any(path: str, request: Request) -> Response:
    body: Any | None = None
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        try:
            body = await request.json()
        except Exception:
            body = None
    return await _proxy(request.method, path, request, body)
