from types import SimpleNamespace

import pytest

from app.services.manual_push_tasks import (
    _parse_scan_dirs,
    normalize_bvid,
    serialize_manual_push_task_detail,
)


def test_normalize_bvid_accepts_valid_input():
    assert normalize_bvid("  BV1rKoLBXEVG  ") == "BV1rKoLBXEVG"


def test_normalize_bvid_preserves_mixed_case_body():
    assert normalize_bvid("BV1rKoLbXeVg") == "BV1rKoLbXeVg"


@pytest.mark.parametrize("value", ["", "av123", "BV123", "https://www.bilibili.com/video/BV1rKoLBXEVG"])
def test_normalize_bvid_rejects_invalid_input(value):
    with pytest.raises(ValueError):
        normalize_bvid(value)


def test_serialize_manual_push_task_parses_result_json():
    row = SimpleNamespace(
        id=1,
        bvid="BV1rKoLBXEVG",
        source_type="bilibili",
        source_path=None,
        push_target_id=7,
        title="test video",
        uploader_name="tester",
        source_video_id=99,
        status="success",
        stage="done",
        progress=100,
        message="done",
        error_message=None,
        result_json='{"ok": true, "count": 3}',
        created_at=None,
        updated_at=None,
        started_at=None,
        finished_at=None,
    )

    data = serialize_manual_push_task_detail(row)  # type: ignore[arg-type]

    assert data["bvid"] == "BV1rKoLBXEVG"
    assert data["push_target_id"] == 7
    assert data["push_target_name"] is None
    assert data["result_json"] == {"ok": True, "count": 3}
    assert data["source_url"] == "https://www.bilibili.com/video/BV1rKoLBXEVG"


def test_serialize_manual_push_task_local_source_hides_source_url():
    row = SimpleNamespace(
        id=2,
        bvid="LOCAL-ABC123",
        source_type="local_video",
        source_path=r"E:\videos\demo.flv",
        push_target_id=None,
        title="demo",
        uploader_name="本地视频",
        source_video_id=None,
        status="success",
        stage="done",
        progress=100,
        message="done",
        error_message=None,
        result_json='{"ok": true}',
        created_at=None,
        updated_at=None,
        started_at=None,
        finished_at=None,
    )

    data = serialize_manual_push_task_detail(row)  # type: ignore[arg-type]

    assert data["source_type"] == "local_video"
    assert data["source_path"] == r"E:\videos\demo.flv"
    assert data["source_url"] is None


def test_parse_scan_dirs_supports_multiple_dirs():
    items = _parse_scan_dirs(r" E:\videos;a:\archive\subdir ; ;C:\demo ")

    assert [str(item) for item in items] == [r"E:\videos", r"a:\archive\subdir", r"C:\demo"]
