from __future__ import annotations

import os
import json

import httpx
import pytest

from app.models.database import PodcastSubscription, PodcastEpisode, PushHistory, get_db
from app.queue_worker import process_single_podcast_episode
from app.scheduler import check_new_podcast_episodes
from app.modules.xiaoyuzhou_sdk import PodcastEpisodePage, XiaoyuzhouClient, XyzApiError


def _make_client(handler):
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, timeout=30)
    return XiaoyuzhouClient(
        base_url="https://api.xiaoyuzhoufm.com",
        podcaster_api_base_url="https://podcaster-api.xiaoyuzhoufm.com",
        access_token="access-token",
        refresh_token="refresh-token",
        device_id="device-id",
        client=client,
    )


def test_get_episode_list_falls_back_to_detail_and_parses_cursor():
    calls: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.host, request.url.path))
        if request.url.path == "/v1/episode/list":
            assert request.method == "POST"
            assert request.headers["x-jike-access-token"] == "access-token"
            assert request.headers["x-jike-device-id"] == "device-id"
            body = json.loads(request.content.decode())
            assert body == {"pid": "pid-1", "order": "desc"}
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "data": [
                            {
                                "eid": "e-1",
                                "pid": "pid-1",
                                "title": "List title",
                                "pubDate": "2026-04-20T08:00:00+08:00",
                                "media": {"source": {"url": ""}, "mimeType": "audio/m4a", "size": 11},
                            },
                            {
                                "eid": "e-2",
                                "pid": "pid-1",
                                "title": "List audio",
                                "pubDate": 1713571200,
                                "media": {
                                    "source": {"url": "https://cdn.example/e2.m4a"},
                                    "mimeType": "audio/m4a",
                                    "size": 22,
                                },
                            },
                        ],
                        "loadMoreKey": {"loadMoreKey": 9, "searchId": "cursor"},
                    },
                },
            )
        if request.url.path == "/v1/episode/get":
            assert request.method == "GET"
            assert request.headers["x-jike-access-token"] == "access-token"
            assert request.headers["x-jike-device-id"] == "device-id"
            assert request.url.params.get("eid") == "e-1"
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "data": {
                            "eid": "e-1",
                            "pid": "pid-1",
                            "title": "Detail title",
                            "pubDate": "2026-04-20T08:00:00+08:00",
                            "media": {
                                "source": {"url": "https://cdn.example/e1.m4a"},
                                "mimeType": "audio/m4a",
                                "size": 33,
                            },
                        }
                    },
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = _make_client(handler)
    page = client.get_episode_list("pid-1")

    assert isinstance(page, PodcastEpisodePage)
    assert page.cursor == {"loadMoreKey": 9, "searchId": "cursor"}
    assert [item.eid for item in page.items] == ["e-1", "e-2"]
    assert page.items[0].title == "Detail title"
    assert page.items[0].audio_url == "https://cdn.example/e1.m4a"
    assert page.items[1].audio_url == "https://cdn.example/e2.m4a"
    assert len(calls) == 2
    client.close()


def test_get_episode_list_handles_flat_list_payload():
    calls: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.host, request.url.path))
        if request.url.path == "/v1/episode/list":
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": [
                        {
                            "eid": "e-10",
                            "pid": "pid-1",
                            "title": "Flat title",
                            "pubDate": "2026-04-20T08:00:00+08:00",
                            "enclosure": {"url": "https://cdn.example/e10.m4a"},
                        }
                    ],
                    "loadMoreKey": {"cursor": "next"},
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = _make_client(handler)
    page = client.get_episode_list("pid-1")

    assert page.cursor == {"cursor": "next"}
    assert [item.eid for item in page.items] == ["e-10"]
    assert page.items[0].audio_url == "https://cdn.example/e10.m4a"
    assert len(calls) == 1
    client.close()


def test_search_and_send_code_use_expected_hosts_and_payloads():
    seen: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.host, request.url.path))
        if request.url.path == "/v1/auth/send-code":
            assert request.url.host == "podcaster-api.xiaoyuzhoufm.com"
            assert request.method == "POST"
            assert request.headers["content-type"].startswith("application/json")
            assert "x-jike-access-token" not in request.headers
            body = json.loads(request.content.decode())
            assert body == {"mobilePhoneNumber": "13900000000", "areaCode": "+86"}
            return httpx.Response(200, json={"code": 0, "data": {"sent": True}})
        if request.url.path == "/v1/search/create":
            assert request.url.host == "api.xiaoyuzhoufm.com"
            assert request.method == "POST"
            assert request.headers["x-jike-access-token"] == "access-token"
            assert request.headers["x-jike-device-id"] == "device-id"
            body = json.loads(request.content.decode())
            assert body["keyword"] == "python"
            assert body["type"] == "podcast"
            assert body["pid"] == "pid-1"
            assert body["loadMoreKey"] == {"loadMoreKey": 1, "searchId": "abc"}
            return httpx.Response(200, json={"code": 200, "data": {"items": []}})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = _make_client(handler)
    send_code_result = client.send_code("13900000000")
    search_result = client.search(
        keyword="python",
        search_type="podcast",
        pid="pid-1",
        load_more_key={"loadMoreKey": 1, "searchId": "abc"},
    )

    assert send_code_result["code"] == 0
    assert search_result["code"] == 200
    assert [item[2] for item in seen] == ["/v1/auth/send-code", "/v1/search/create"]
    client.close()


def test_refresh_tokens_sends_device_id_and_updates_tokens():
    seen: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.host, request.url.path))
        if request.url.path == "/app_auth_tokens.refresh":
            assert request.url.host == "api.xiaoyuzhoufm.com"
            assert request.method == "POST"
            assert request.headers["x-jike-access-token"] == "access-token"
            assert request.headers["x-jike-refresh-token"] == "refresh-token"
            assert request.headers["x-jike-device-id"] == "device-id"
            assert request.headers["content-type"].startswith("application/x-www-form-urlencoded")
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "x-jike-access-token": "new-access",
                        "x-jike-refresh-token": "new-refresh",
                    },
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = _make_client(handler)
    response = client.refresh_tokens()

    assert response["code"] == 200
    assert client.access_token == "new-access"
    assert client.refresh_token == "new-refresh"
    assert [item[2] for item in seen] == ["/app_auth_tokens.refresh"]
    client.close()


def test_episode_list_requires_access_token():
    client = XiaoyuzhouClient(
        base_url="https://api.xiaoyuzhoufm.com",
        podcaster_api_base_url="https://podcaster-api.xiaoyuzhoufm.com",
        access_token="temporary-token",
        device_id="device-id",
        client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500))),
    )
    client.set_tokens(access_token="")

    with pytest.raises(XyzApiError, match="access_token"):
        client.get_episode_list("pid-1")

    client.close()


@pytest.mark.integration
def test_xiaoyuzhou_real_chain_reaches_feishu():

    db = get_db()
    try:
        subscription = (
            db.query(PodcastSubscription)
            .filter(PodcastSubscription.is_active == True)  # noqa: E712
            .order_by(PodcastSubscription.id.asc())
            .first()
        )
        if not subscription:
            pytest.skip("no active podcast subscription in database")

        pid = subscription.pid
    finally:
        db.close()

    check_new_podcast_episodes()

    db = get_db()
    try:
        subscription = (
            db.query(PodcastSubscription)
            .filter(PodcastSubscription.is_active == True)  # noqa: E712
            .order_by(PodcastSubscription.id.asc())
            .first()
        )
        assert subscription is not None

        episodes = (
            db.query(PodcastEpisode)
            .filter(PodcastEpisode.pid == subscription.pid)
            .order_by(PodcastEpisode.created_at.asc(), PodcastEpisode.id.asc())
            .all()
        )
        if not episodes:
            pytest.skip("scheduler did not discover any podcast episode to process")

        episode = next((row for row in episodes if row.status == "pending"), episodes[0])
        episode_id = episode.eid
        before_history_count = (
            db.query(PushHistory)
            .filter(
                PushHistory.content_type == "podcast",
                PushHistory.content_id == episode_id,
                PushHistory.channel == "feishu",
                PushHistory.status == "success",
            )
            .count()
        )
    finally:
        db.close()

    process_single_podcast_episode(episode_id)

    db = get_db()
    try:
        episode = db.query(PodcastEpisode).filter(PodcastEpisode.eid == episode_id).first()
        assert episode is not None
        assert episode.status == "done"
        assert episode.push_status == "success"
        assert episode.summary_json
        assert episode.pushed_at is not None

        after_history_count = (
            db.query(PushHistory)
            .filter(
                PushHistory.content_type == "podcast",
                PushHistory.content_id == episode_id,
                PushHistory.channel == "feishu",
                PushHistory.status == "success",
            )
            .count()
        )
        assert after_history_count > before_history_count
    finally:
        db.close()
