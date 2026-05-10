"""
Tests for app.modules.bilibili and dynamic fetching.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.modules import bilibili
from app.modules.dynamic import DynamicFetcher


def test_fetch_channel_videos_success():
    """Fetch the latest videos for one uploader."""
    mid = "123456"

    mock_response = {
        "code": 0,
        "data": {
            "list": {
                "vlist": [
                    {
                        "bvid": "BV111",
                        "title": "test video 1",
                        "created": 1234567890,
                        "length": "10:00",
                        "pic": "https://example.com/1.jpg",
                    },
                    {
                        "bvid": "BV222",
                        "title": "test video 2",
                        "created": 1234567891,
                        "length": "20:00",
                        "pic": "https://example.com/2.jpg",
                    },
                ]
            }
        },
    }

    with patch("app.modules.bilibili.sign_params", side_effect=lambda params: params.copy()), \
        patch("app.modules.bilibili.requests.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.headers = {}
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        result = bilibili.fetch_channel_videos(mid, limit=5)

    mock_session.get.assert_called_once()
    args, kwargs = mock_session.get.call_args
    assert kwargs["params"]["mid"] == mid
    assert kwargs["params"]["ps"] == "5"

    assert len(result) == 2
    assert result[0]["bvid"] == "BV111"
    assert result[0]["title"] == "test video 1"
    assert result[1]["bvid"] == "BV222"


def test_fetch_channel_videos_code_not_zero():
    """Return an empty list when API code is not zero."""
    mid = "123456"

    mock_response = {"code": -1, "message": "API error"}

    with patch("app.modules.bilibili.sign_params", side_effect=lambda params: params.copy()), \
        patch("app.modules.bilibili.requests.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.headers = {}
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        result = bilibili.fetch_channel_videos(mid)

    assert result == []


def test_fetch_channel_videos_missing_vlist():
    """Return an empty list when vlist is missing."""
    mid = "123456"

    mock_response = {
        "code": 0,
        "data": {
            "list": {},
        },
    }

    with patch("app.modules.bilibili.sign_params", side_effect=lambda params: params.copy()), \
        patch("app.modules.bilibili.requests.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.headers = MagicMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        result = bilibili.fetch_channel_videos(mid)

    assert result == []


def test_fetch_channel_videos_request_exception():
    """Network exception should bubble up."""
    mid = "123456"

    with patch("app.modules.bilibili.sign_params", side_effect=lambda params: params.copy()), \
        patch("app.modules.bilibili.requests.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.headers = MagicMock()
        mock_session.get.side_effect = Exception("Network error")
        mock_session_cls.return_value = mock_session

        with pytest.raises(Exception):
            bilibili.fetch_channel_videos(mid)


def test_fetch_channel_videos_with_cookie():
    """Use BILIBILI_COOKIE in request headers."""
    mid = "123456"

    mock_response = {"code": 0, "data": {"list": {"vlist": []}}}

    with patch("app.modules.bilibili.Config") as mock_config:
        mock_config.BILIBILI_COOKIE = "test_cookie_value"

        with patch("app.modules.bilibili.sign_params", side_effect=lambda params: params.copy()), \
            patch("app.modules.bilibili.requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.headers = {}
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = mock_response
            mock_session.get.return_value = mock_resp
            mock_session_cls.return_value = mock_session

            bilibili.fetch_channel_videos(mid)

        assert mock_session.headers["Cookie"] == "test_cookie_value"


def test_get_subtitle_info():
    """Get subtitle metadata."""
    bvid = "BV1234567890"

    mock_response = {
        "code": 0,
        "data": {
            "subtitle": {
                "list": [],
            }
        },
    }

    with patch("app.modules.bilibili.requests.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.headers = MagicMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        result = bilibili.get_subtitle_info(bvid)

    mock_session.get.assert_called_once()
    args, kwargs = mock_session.get.call_args
    assert kwargs["params"]["bvid"] == bvid
    assert result == mock_response


def test_get_subtitle_info_with_cid():
    """Get subtitle metadata with cid."""
    bvid = "BV1234567890"
    cid = "123456"

    mock_response = {"code": 0, "data": {}}

    with patch("app.modules.bilibili.requests.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.headers = MagicMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        bilibili.get_subtitle_info(bvid, cid=cid)

    args, kwargs = mock_session.get.call_args
    assert kwargs["params"]["cid"] == cid


def test_fetch_video_detail_success():
    """Fetch metadata for a single video by bvid."""
    bvid = "BV1rKoLBXEVG"

    mock_response = {
        "code": 0,
        "data": {
            "bvid": bvid,
            "aid": 123,
            "cid": 456,
            "title": "video title",
            "pubdate": 1710000000,
            "desc": "video desc",
            "owner": {
                "mid": 999,
                "name": "uploader",
            },
        },
    }

    with patch("app.modules.bilibili.requests.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.headers = MagicMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        result = bilibili.fetch_video_detail(bvid)

    mock_session.get.assert_called_once()
    args, kwargs = mock_session.get.call_args
    assert args[0] == "https://api.bilibili.com/x/web-interface/view"
    assert kwargs["params"]["bvid"] == bvid
    assert result["bvid"] == bvid
    assert result["title"] == "video title"
    assert result["mid"] == "999"
    assert result["uploader_name"] == "uploader"
    assert result["pub_time"] == 1710000000


def test_fetch_dynamic_detail_success():
    """Fetch metadata for a single dynamic by id."""
    dynamic_id = "1194773285156421652"

    mock_response = {
        "code": 0,
        "data": {
            "card": {
                "desc": {
                    "uid": 625315686,
                    "type": 8,
                    "timestamp": 1777018233,
                    "user_profile": {
                        "info": {
                            "uid": 625315686,
                            "uname": "股市-桃哥复盘",
                        }
                    },
                },
                "card": json.dumps(
                    {
                        "aid": 116458625505302,
                        "cid": 37778031869,
                        "title": "新易盛不及预期，国产芯片大涨",
                        "owner": {
                            "mid": 625315686,
                            "name": "股市-桃哥复盘",
                        },
                        "videos": 1,
                        "pic": "https://example.com/cover.jpg",
                    },
                    ensure_ascii=False,
                ),
            }
        },
    }

    with patch("app.modules.bilibili.requests.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.headers = MagicMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        result = bilibili.fetch_dynamic_detail(dynamic_id)

    mock_session.get.assert_called_once()
    args, kwargs = mock_session.get.call_args
    assert args[0] == "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/get_dynamic_detail"
    assert kwargs["params"]["dynamic_id"] == dynamic_id
    assert result["dynamic_id"] == dynamic_id
    assert result["mid"] == "625315686"
    assert result["uploader_name"] == "股市-桃哥复盘"
    assert result["type"] == "DYNAMIC_TYPE_AV"
    assert result["text"] == "新易盛不及预期，国产芯片大涨"
    assert result["is_video"] is True


def test_fetch_dynamic_list_success():
    """Fetch dynamic list for uid=123456."""
    uid = "123456"

    mock_response = {
        "code": 0,
        "data": {
            "items": [
                {
                    "id_str": "dyn001",
                    "type": "DYNAMIC_TYPE_WORD",
                    "modules": {
                        "module_author": {
                            "pub_ts": "1710000000",
                            "pub_time": "2024-03-09 10:00:00",
                        },
                        "module_dynamic": {
                            "major": {
                                "type": "MAJOR_TYPE_COMMON",
                                "common": {
                                    "desc": "first dynamic",
                                    "images": [],
                                },
                            }
                        },
                    },
                },
                {
                    "id_str": "dyn002",
                    "type": "DYNAMIC_TYPE_DRAW",
                    "modules": {
                        "module_author": {
                            "pub_ts": "1710000100",
                            "pub_time": "2024-03-09 10:01:40",
                        },
                        "module_dynamic": {
                            "major": {
                                "type": "MAJOR_TYPE_OPUS",
                                "opus": {
                                    "summary": {"text": "second dynamic"},
                                    "pics": [
                                        {"url": "https://example.com/a.jpg"},
                                    ],
                                },
                            }
                        },
                    },
                },
            ]
        },
    }

    with patch("app.modules.dynamic.Config") as mock_config:
        mock_config.BILIBILI_COOKIE = ""

        with patch("app.modules.dynamic.WBISigner") as mock_signer_cls:
            mock_signer = MagicMock()
            mock_signer.sign.side_effect = lambda params: params.copy()
            mock_signer_cls.return_value = mock_signer

            with patch("app.modules.dynamic.requests.Session") as mock_session_cls:
                mock_session = MagicMock()
                mock_session.headers = MagicMock()
                mock_resp = MagicMock()
                mock_resp.raise_for_status.return_value = None
                mock_resp.json.return_value = mock_response
                mock_session.get.return_value = mock_resp
                mock_session_cls.return_value = mock_session

                with DynamicFetcher() as fetcher:
                    result = fetcher.fetch_dynamic(uid)

    mock_session.get.assert_called_once()
    args, kwargs = mock_session.get.call_args
    assert args[0] == "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
    assert kwargs["params"]["host_mid"] == uid
    assert kwargs["params"]["offset"] == ""
    assert len(result) == 2
    assert result[0]["dynamic_id"] == "dyn001"
    assert result[0]["text"] == "first dynamic"
    assert result[0]["image_urls"] == []
    assert result[1]["dynamic_id"] == "dyn002"
    assert result[1]["text"] == "second dynamic"
    assert result[1]["image_urls"] == ["https://example.com/a.jpg"]
