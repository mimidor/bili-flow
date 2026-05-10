from __future__ import annotations

from types import SimpleNamespace

import app.modules.push_channels.feishu as feishu


def test_feishu_text_is_truncated_before_send(monkeypatch):
    captured = {}

    monkeypatch.setattr(feishu, "get_feishu_tenant_access_token", lambda: "token")
    monkeypatch.setattr(
        feishu,
        "_resolve_target",
        lambda content_data: {
            "receive_id": "chat-123",
            "receive_id_type": "chat_id",
        },
    )

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return SimpleNamespace(json=lambda: {"code": 0}, status_code=200, text="{}")

    monkeypatch.setattr(feishu.requests, "post", fake_post)

    channel = feishu.FeishuChannel()
    long_text = "x" * 5000

    assert channel._send_text(long_text, {"type": "video"}) is True
    sent_content = captured["json"]["content"]
    assert len(sent_content) < len(long_text)
    assert "内容已截断" in sent_content
