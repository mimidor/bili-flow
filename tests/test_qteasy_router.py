from __future__ import annotations

import asyncio
from types import SimpleNamespace

from admin_backend.routers import qteasy


def test_base_url_normalizes_bare_host_port(monkeypatch):
    monkeypatch.setattr(qteasy, "Config", SimpleNamespace(QTEASY_API_URL="127.0.0.1:8001"), raising=False)

    assert qteasy._base_url() == "http://127.0.0.1:8001"


def test_base_url_keeps_explicit_scheme(monkeypatch):
    monkeypatch.setattr(qteasy, "Config", SimpleNamespace(QTEASY_API_URL="https://example.com:8443"), raising=False)

    assert qteasy._base_url() == "https://example.com:8443"


def test_local_base_url_bypasses_env_proxy():
    assert qteasy._should_bypass_env_proxy("http://127.0.0.1:8001") is True
    assert qteasy._should_bypass_env_proxy("http://localhost:8001") is True
    assert qteasy._should_bypass_env_proxy("http://[::1]:8001") is True


def test_remote_base_url_keeps_env_proxy():
    assert qteasy._should_bypass_env_proxy("https://example.com:8443") is False


def test_request_remote_disables_trust_env_for_local_qteasy(monkeypatch):
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured["kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, **kwargs):
            captured["request"] = {
                "method": method,
                "url": url,
                "kwargs": kwargs,
            }
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr(qteasy, "Config", SimpleNamespace(QTEASY_API_URL="http://127.0.0.1:8001"), raising=False)
    monkeypatch.setattr(qteasy.httpx, "AsyncClient", FakeClient)
    qteasy._async_clients.clear()

    request = SimpleNamespace(query_params={"limit": "20", "offset": "0"})
    asyncio.run(qteasy._request_remote("GET", "jobs", request))

    assert captured["kwargs"]["trust_env"] is False
    assert captured["request"]["url"] == "http://127.0.0.1:8001/jobs"


def test_async_client_is_reused_by_trust_env(monkeypatch):
    created: list[bool] = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            created.append(kwargs["trust_env"])

    monkeypatch.setattr(qteasy.httpx, "AsyncClient", FakeClient)
    qteasy._async_clients.clear()

    client_a = asyncio.run(qteasy._get_async_client(trust_env=False))
    client_b = asyncio.run(qteasy._get_async_client(trust_env=False))
    client_c = asyncio.run(qteasy._get_async_client(trust_env=True))

    assert client_a is client_b
    assert client_a is not client_c
    assert created == [False, True]


def test_sanitize_jobs_query_params_rewrites_legacy_backtest_type_and_drops_job_name():
    request = SimpleNamespace(
        query_params={
            "limit": "20",
            "offset": "0",
            "task_type": "backtest.run",
            "status": "queued",
            "job_name": "demo",
        }
    )

    params = qteasy._sanitize_jobs_query_params(request)

    assert params == {
        "limit": "20",
        "offset": "0",
        "task_type": "qteasy.run",
        "status": "queued",
    }


def test_sanitize_jobs_query_params_keeps_supported_filters():
    request = SimpleNamespace(
        query_params={
            "limit": "10",
            "offset": "5",
            "task_type": "optimization.run",
            "status": "running",
        }
    )

    params = qteasy._sanitize_jobs_query_params(request)

    assert params == {
        "limit": "10",
        "offset": "5",
        "task_type": "optimization.run",
        "status": "running",
    }


def test_request_remote_uses_explicit_params_override(monkeypatch):
    captured: dict[str, object] = {}

    class FakeClient:
        async def request(self, method, url, **kwargs):
            captured["request"] = {
                "method": method,
                "url": url,
                "kwargs": kwargs,
            }
            return SimpleNamespace(status_code=200)

    async def fake_get_async_client(*, trust_env: bool):
        captured["trust_env"] = trust_env
        return FakeClient()

    monkeypatch.setattr(qteasy, "Config", SimpleNamespace(QTEASY_API_URL="http://127.0.0.1:8001"), raising=False)
    monkeypatch.setattr(qteasy, "_get_async_client", fake_get_async_client)

    request = SimpleNamespace(query_params={"task_type": "backtest.run", "job_name": "ignored"})
    asyncio.run(qteasy._request_remote("GET", "jobs", request, params={"task_type": "qteasy.run", "limit": "10"}))

    assert captured["trust_env"] is False
    assert captured["request"]["kwargs"]["params"] == {"task_type": "qteasy.run", "limit": "10"}
