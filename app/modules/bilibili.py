import json
import requests
import time
from datetime import datetime
from typing import Any, List, Optional
from config import Config
from app.utils.logger import get_logger
from app.modules.wbi import sign_params

logger = get_logger("bilibili")


def _check_cookie() -> None:
    """检查是否配置了 BILIBILI_COOKIE"""
    if not Config.BILIBILI_COOKIE:
        raise RuntimeError(
            "批量获取视频需要配置 BILIBILI_COOKIE 以避免限流。\n"
            "请在 .env 文件中设置 BILIBILI_COOKIE。\n"
            "获取方式：登录 B站 后，在浏览器开发者工具中复制 Cookie 值"
        )


def _get_session() -> requests.Session:
    """
    创建并配置一个 Session 实例

    使用 Session 可以复用 TCP 连接，减少 API 请求限流风险
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com",
        "Origin": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    })
    if Config.BILIBILI_COOKIE:
        session.headers.update({"Cookie": Config.BILIBILI_COOKIE})
    return session


def fetch_channel_videos(mid: str, limit: int = 5) -> List[dict]:
    """
    获取 UP 主最新视频列表

    使用 WBI 签名接口，减少限流风险

    Args:
        mid: UP 主 ID
        limit: 获取数量

    Returns:
        视频列表
    """
    session = _get_session()

    try:
        # 先尝试 WBI 签名接口
        url = "https://api.bilibili.com/x/space/wbi/arc/search"
        params = {
            "mid": str(mid),
            "ps": str(min(limit, 25)),  # WBI 接口最大 25
            "pn": "1",
            "tid": "0",
            "special_type": "",
            "order": "pubdate",
            "index": "0",
            "keyword": "",
            "order_avoided": "true",
        }

        try:
            signed_params = sign_params(params)
            resp = session.get(url, params=signed_params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            # 检查是否是权限问题
            if data.get("code") != 0:
                error_msg = data.get("message", "")
                if "权限" in error_msg or "访问" in error_msg:
                    logger.debug("WBI 接口权限不足，降级到旧接口")
                    raise RuntimeError("WBI permission denied")
                else:
                    logger.error("bilibili API error: %s", error_msg)
                    return []
        except RuntimeError:
            # 降级到旧接口
            url = "https://api.bilibili.com/x/space/arc/search"
            resp = session.get(url, params={"mid": mid, "ps": limit, "pn": 1}, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                logger.error("bilibili API error: %s", data.get("message"))
                return []

        items = data.get("data", {}).get("list", {}).get("vlist", [])
        videos = []

        for item in items:
            videos.append({
                "bvid": item.get("bvid"),
                "title": item.get("title"),
                "pubdate": item.get("created", 0),
                "duration": item.get("length"),
                "pic": item.get("pic"),
            })

        return videos
    finally:
        session.close()


def fetch_video_detail(bvid: str) -> dict[str, Any]:
    """
    Fetch a single video detail by BVID.

    This is used to bootstrap manual tasks without a pre-existing database row.
    """
    session = _get_session()
    url = "https://api.bilibili.com/x/web-interface/view"

    try:
        resp = session.get(url, params={"bvid": bvid}, timeout=20)
        resp.raise_for_status()
        try:
            data = resp.json()
        except Exception as exc:
            raw_text = (resp.text or "").strip()
            preview = raw_text[:300]
            raise RuntimeError(
                f"bilibili video detail invalid json: status={resp.status_code}, body={preview}"
            ) from exc

        if data.get("code") != 0:
            code = data.get("code")
            message = data.get("message") or data.get("msg") or "unknown"
            raise RuntimeError(
                f"bilibili video detail error: code={code}, message={message}, bvid={bvid}"
            )

        detail = data.get("data") or {}
        owner = detail.get("owner") or {}
        mid = str(owner.get("mid") or "")
        if not mid:
            raise RuntimeError(f"bilibili video detail missing uploader mid for {bvid}")
        pub_time = detail.get("pubdate") or detail.get("ctime") or 0
        try:
            pub_time = int(pub_time) if pub_time else None
        except (TypeError, ValueError):
            pub_time = None

        return {
            "bvid": detail.get("bvid") or bvid,
            "aid": detail.get("aid"),
            "cid": detail.get("cid"),
            "title": detail.get("title") or bvid,
            "mid": mid,
            "uploader_name": owner.get("name") or (f"UP主_{mid}" if mid else ""),
            "pub_time": pub_time,
            "desc": detail.get("desc") or "",
            "raw": detail,
        }
    finally:
        session.close()


def _extract_dynamic_text_and_images(card_data: dict[str, Any]) -> tuple[str, list[str]]:
    text_candidates: list[str] = []
    image_urls: list[str] = []

    if not isinstance(card_data, dict):
        return "", []

    item = card_data.get("item") if isinstance(card_data.get("item"), dict) else {}
    for key in ("content", "description", "desc"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            text_candidates.append(value.strip())

    for key in ("summary", "title", "desc", "dynamic"):
        value = card_data.get(key)
        if isinstance(value, str) and value.strip():
            text_candidates.append(value.strip())

    image_sources: list[Any] = []
    for key in ("pictures", "images", "pics"):
        source = item.get(key) if isinstance(item.get(key), list) else None
        if not source:
            source = card_data.get(key) if isinstance(card_data.get(key), list) else None
        if source:
            image_sources.extend(source)

    for image in image_sources:
        if isinstance(image, dict):
            for key in ("img_src", "src", "url", "image_url"):
                value = image.get(key)
                if value:
                    image_urls.append(str(value))
                    break
        elif isinstance(image, str) and image.strip():
            image_urls.append(image.strip())

    seen: set[str] = set()
    deduped_images: list[str] = []
    for url in image_urls:
        if url not in seen:
            seen.add(url)
            deduped_images.append(url)

    text = next((candidate for candidate in text_candidates if candidate), "").strip()
    return text, deduped_images


def _infer_dynamic_type(desc_type: Any, card_data: dict[str, Any]) -> str:
    if desc_type == 8:
        return "DYNAMIC_TYPE_AV"

    if not isinstance(card_data, dict):
        return "DYNAMIC_TYPE_WORD"

    if card_data.get("aid") or card_data.get("cid") or card_data.get("videos"):
        return "DYNAMIC_TYPE_AV"

    item = card_data.get("item") if isinstance(card_data.get("item"), dict) else {}
    pictures = item.get("pictures") or item.get("images") or card_data.get("pictures") or card_data.get("images")
    if pictures:
        return "DYNAMIC_TYPE_DRAW"

    if any((item.get(key) or card_data.get(key)) for key in ("content", "description", "desc", "title", "summary")):
        return "DYNAMIC_TYPE_WORD"

    return "DYNAMIC_TYPE_OPUS"


def fetch_dynamic_detail(dynamic_id: str) -> dict[str, Any]:
    """
    Fetch a single dynamic detail by dynamic_id.

    Uses the legacy detail API which still returns the author, card payload and timestamps.
    """
    session = _get_session()
    url = "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/get_dynamic_detail"

    try:
        resp = session.get(url, params={"dynamic_id": str(dynamic_id)}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"bilibili dynamic detail error: {data.get('message') or data.get('code')}")

        card_wrapper = data.get("data", {}).get("card") or {}
        desc = card_wrapper.get("desc") or {}
        card_raw = card_wrapper.get("card") or "{}"
        try:
            card_data = json.loads(card_raw) if isinstance(card_raw, str) else (card_raw or {})
        except Exception:
            card_data = {}

        owner = card_data.get("owner") or desc.get("user_profile", {}).get("info", {}) or {}
        text, image_urls = _extract_dynamic_text_and_images(card_data)
        dynamic_type = _infer_dynamic_type(desc.get("type"), card_data)

        pub_ts = desc.get("timestamp") or card_data.get("pubdate") or 0
        try:
            pub_ts = int(pub_ts) if pub_ts else None
        except (TypeError, ValueError):
            pub_ts = None

        pub_time = datetime.fromtimestamp(pub_ts) if pub_ts else None
        mid = str(desc.get("uid") or owner.get("mid") or "")
        if not mid:
            raise RuntimeError(f"bilibili dynamic detail missing uploader mid for {dynamic_id}")
        uploader_name = owner.get("name") or desc.get("user_profile", {}).get("info", {}).get("uname", "") or ""
        if not uploader_name and mid:
            uploader_name = f"UP主_{mid}"

        return {
            "dynamic_id": str(dynamic_id),
            "mid": mid,
            "uploader_name": uploader_name,
            "type": dynamic_type,
            "text": text or card_data.get("title") or "",
            "image_urls": image_urls,
            "pub_time": pub_time,
            "pub_ts": pub_ts,
            "is_video": dynamic_type == "DYNAMIC_TYPE_AV",
            "raw": card_wrapper,
        }
    finally:
        session.close()


def fetch_all_videos(mid: str, start_date: Optional[int] = None, end_date: Optional[int] = None) -> List[dict]:
    """
    获取 UP 主所有视频（支持分页和日期范围过滤）

    优先使用 WBI 签名接口，失败时降级到旧接口

    Args:
        mid: UP 主 ID
        start_date: 开始日期时间戳（Unix timestamp），None 表示不限制
        end_date: 结束日期时间戳（Unix timestamp），None 表示不限制

    Returns:
        视频列表，按发布时间倒序
    """
    # 检查 Cookie 配置
    _check_cookie()

    session = _get_session()
    all_videos = []
    page = 1
    use_wbi = True  # 是否使用 WBI 接口

    logger.info("开始获取 UP 主 %s 的所有视频...", mid)

    try:
        while True:
            # 尝试 WBI 接口
            if use_wbi:
                url = "https://api.bilibili.com/x/space/wbi/arc/search"
                page_size = 25
                params = {
                    "mid": str(mid),
                    "ps": str(page_size),
                    "pn": str(page),
                    "tid": "0",
                    "special_type": "",
                    "order": "pubdate",
                    "index": "0",
                    "keyword": "",
                    "order_avoided": "true",
                }
                try:
                    signed_params = sign_params(params)
                    logger.debug("WBI 签名参数: %s", {k: v for k, v in signed_params.items() if k not in ['w_rid', 'wts']})
                    resp = session.get(url, params=signed_params, timeout=15)
                    resp.raise_for_status()
                    data = resp.json()

                    # 检查是否是权限问题
                    if data.get("code") != 0:
                        error_msg = data.get("message", "")
                        if "权限" in error_msg or "访问" in error_msg:
                            logger.warning("WBI 接口权限不足: %s，降级到旧接口", error_msg)
                            use_wbi = False
                            page = 1  # 重置页码
                            all_videos = []  # 清空已获取数据
                            continue
                        else:
                            logger.error("bilibili API error (page %d): %s", page, error_msg)
                            break
                except Exception as e:
                    logger.warning("WBI 接口请求失败: %s，降级到旧接口", e)
                    use_wbi = False
                    page = 1
                    all_videos = []
                    continue

            # 使用旧接口（降级方案）
            if not use_wbi:
                url = "https://api.bilibili.com/x/space/arc/search"
                page_size = 30
                params = {
                    "mid": mid,
                    "ps": page_size,
                    "pn": page
                }
                resp = session.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                if data.get("code") != 0:
                    logger.error("bilibili API error (page %d): %s", page, data.get("message"))
                    break

            items = data.get("data", {}).get("list", {}).get("vlist", [])

            if not items:
                # 没有更多数据
                break

            page_videos = []
            for item in items:
                pubdate = item.get("created", 0)

                # 日期范围过滤
                if start_date and pubdate < start_date:
                    # 视频发布时间早于开始日期，由于是倒序，后面的视频更早，可以停止
                    logger.debug("视频 %s 发布于 %d，早于开始日期 %d，停止获取",
                                item.get("bvid"), pubdate, start_date)
                    return all_videos

                if end_date and pubdate > end_date:
                    # 视频发布时间晚于结束日期，跳过
                    logger.debug("跳过视频 %s，发布于 %d，晚于结束日期 %d",
                                item.get("bvid"), pubdate, end_date)
                    continue

                page_videos.append({
                    "bvid": item.get("bvid"),
                    "title": item.get("title"),
                    "pubdate": pubdate,
                    "duration": item.get("length"),
                    "pic": item.get("pic"),
                    "description": item.get("description", ""),
                    "comment": item.get("comment", 0),
                    "play": item.get("play", 0),
                })

            all_videos.extend(page_videos)
            logger.info("第 %d 页获取到 %d 个视频，累计 %d 个", page, len(page_videos), len(all_videos))

            # 检查是否还有更多页
            page_info = data.get("data", {}).get("page", {})
            total = page_info.get("count", 0)
            if len(all_videos) >= total:
                logger.info("已获取所有视频，共 %d 个", len(all_videos))
                break

            page += 1

            # 每页之间延迟，避免限流
            if page > 1:
                delay = 1.0 if use_wbi else 2.0  # 旧接口延迟更长
                time.sleep(delay)

        return all_videos
    finally:
        session.close()


def get_subtitle_info(bvid: str, cid: str = None) -> dict:
    """查询视频是否有字幕（备用）"""
    session = _get_session()
    url = "https://api.bilibili.com/x/player/v2"

    try:
        params = {"bvid": bvid}
        if cid:
            params["cid"] = cid

        resp = session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    finally:
        session.close()
