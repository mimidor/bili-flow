"""
Real Feishu push integration tests driven by .env.

These tests intentionally avoid mocks. They will skip when the Feishu
credentials or target receive ID are not configured.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

import app.modules.push_channels.feishu as feishu
from app.modules.push_channels.feishu import FeishuChannel
from app.modules.push_channels import push_content
from config import Config


def _feishu_configured() -> bool:
    return bool(
        Config.FEISHU_APP_ID
        and Config.FEISHU_APP_SECRET
        and Config.FEISHU_RECEIVE_ID
        and Config.FEISHU_RECEIVE_ID_TYPE
    )


def _require_feishu() -> None:
    if not _feishu_configured():
        pytest.skip(
            "Feishu is not fully configured in .env. Need FEISHU_APP_ID, "
            "FEISHU_APP_SECRET, FEISHU_RECEIVE_ID, FEISHU_RECEIVE_ID_TYPE."
        )


class TestFeishuChannel:
    def test_send_video(self):
        _require_feishu()

        channel = FeishuChannel()
        title = f"测试视频 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        result = channel.send(
            {
                "type": "video",
                "title": title,
                "summary": "这是一个真实飞书推送测试。",
                "tags": ["测试", "飞书"],
                "stocks": ["A股"],
                "url": "https://www.bilibili.com/video/BV1234567890",
                "doc_url": "",
            }
        )

        assert result is True

    def test_send_dynamic(self):
        _require_feishu()

        channel = FeishuChannel()
        result = channel.send(
            {
                "type": "dynamic",
                "text": f"这是一个真实动态推送测试，时间：{datetime.now().isoformat(timespec='seconds')}",
                "url": "https://www.bilibili.com/opus/1234567890",
                "pub_time": "2024-03-31 18:00:00",
            }
        )

        assert result is True


class TestPushContent:
    def test_push_to_explicit_feishu_target(self, monkeypatch):
        captured = {}

        monkeypatch.setattr("app.modules.push_channels.resolve_push_target", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("resolve_push_target should not be called")))
        monkeypatch.setattr(feishu, "get_feishu_tenant_access_token", lambda: "token")

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return SimpleNamespace(json=lambda: {"code": 0}, status_code=200, text="{}")

        monkeypatch.setattr(feishu.requests, "post", fake_post)

        result = push_content(
            {
                "type": "video",
                "title": f"push_content explicit target {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "summary": "explicit target test with finance signal",
                "url": "https://www.bilibili.com/video/BV1234567890",
                "push_filter": {"should_push": True, "reason": "explicit target test"},
                "push_target": {
                    "id": 999,
                    "channel": "feishu",
                    "name": "知识群",
                    "receive_id": "chat-999",
                    "receive_id_type": "chat_id",
                    "is_default": True,
                    "is_active": True,
                },
            },
            ["feishu"],
        )

        assert result["success"] is True
        assert captured["json"]["receive_id"] == "chat-999"

    def test_push_to_feishu_video(self):
        _require_feishu()

        result = push_content(
            {
                "type": "video",
                "title": f"push_content 测试 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "summary": "这是一个通过 push_content 发出的真实消息。",
                "url": "https://www.bilibili.com/video/BV1234567890",
            },
            ["feishu"],
        )

        assert result is True

    def test_push_to_multiple_channels(self):
        _require_feishu()

        result = push_content(
            {
                "type": "dynamic",
                "text": f"push_content 动态测试 {datetime.now().isoformat(timespec='seconds')}",
                "url": "https://www.bilibili.com/opus/1234567890",
            },
            ["feishu"],
        )

        assert result is True

    def test_push_to_unknown_channel(self):
        result = push_content(
            {
                "type": "dynamic",
                "text": "测试",
                "url": "https://example.com",
            },
            ["unknown_channel"],
        )

        assert result is False
