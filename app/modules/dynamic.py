import json
import re
import requests
import time
from datetime import datetime, timedelta
from pathlib import Path
from app.utils.logger import get_logger
from app.utils.runtime_home import get_data_dir
from config import Config
from app.modules.wbi import WBISigner

logger = get_logger("dynamic")


class DynamicFetcher:
    def __init__(self):
        # 使用 Session 复用连接
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
            "Referer": "https://space.bilibili.com",
            "Origin": "https://space.bilibili.com",
        })
        if Config.BILIBILI_COOKIE:
            self.session.headers.update({"Cookie": Config.BILIBILI_COOKIE})

        self.image_dir = get_data_dir() / "dynamic_images"
        self.image_dir.mkdir(parents=True, exist_ok=True)

        # WBI 签名器
        self.wbi_signer = WBISigner()
        self._w_webid: str | None = None

    def close(self):
        """关闭 Session"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def fetch_dynamic(self, mid: str, offset: str = "") -> list:
        """
        获取 UP主动态

        Args:
            mid: UP主 ID
            offset: 分页偏移量（字符串格式）

        Returns:
            动态列表
        """
        data = self._fetch_dynamic_page(mid, offset)
        if data.get("code") == -352:
            logger.warning("动态拉取触发风控，重试一次: mid=%s message=%s", mid, data.get("message"))
            self._w_webid = None
            self.wbi_signer._last_refresh = 0
            time.sleep(0.5)
            data = self._fetch_dynamic_page(mid, offset)

        if data.get("code") != 0:
            logger.error(
                "动态拉取失败：mid=%s code=%s message=%s",
                mid,
                data.get("code"),
                data.get("message") or data.get("msg"),
            )
            return []

        items = data.get("data", {}).get("items", [])
        dynamics = []

        for item in items:
            parsed = self._parse_dynamic(item)
            if parsed:
                dynamics.append(parsed)

        return dynamics

    def _fetch_dynamic_page(self, mid: str, offset: str) -> dict:
        url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
        params = {
            "host_mid": mid,
            "offset": offset,
            "timezone_offset": "-480",
            "platform": "web",
            "features": "itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote,forwardListHidden,decorationCard,commentsNewVersion,onlyfansAssetsV2,ugcDelete,onlyfansQaCard,avatarAutoTheme,sunflowerStyle,cardsEnhance,eva3CardOpus,eva3CardVideo,eva3CardComment,eva3CardUser",
            "web_location": "333.1387",
        }
        w_webid = self._get_w_webid()
        if w_webid:
            params["w_webid"] = w_webid
        params = self.wbi_signer.sign(params)
        resp = self.session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def _get_w_webid(self) -> str | None:
        if self._w_webid:
            return self._w_webid
        if not Config.BILIBILI_COOKIE:
            return None

        uid = self._extract_uid_from_cookie(Config.BILIBILI_COOKIE)
        if not uid:
            return None

        try:
            url = f"https://space.bilibili.com/{uid}/dynamic"
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            match = re.search(r'<script[^>]*id="__RENDER_DATA__"[^>]*>(.*?)</script>', resp.text, re.S)
            if not match:
                return None
            rendered = match.group(1).strip()
            if not rendered:
                return None
            decoded = json.loads(requests.utils.unquote(rendered))
            access_id = decoded.get("access_id")
            if access_id:
                self._w_webid = str(access_id)
                logger.debug("获取到 B 站 w_webid: %s", self._w_webid)
                return self._w_webid
        except Exception as exc:
            logger.warning("获取 B 站 w_webid 失败，继续按无 webid 访问: %s", exc)
        return None

    @staticmethod
    def _extract_uid_from_cookie(cookie: str) -> str | None:
        match = re.search(r"(?:^|;\s*)DedeUserID=([^;]+)", cookie)
        if not match:
            return None
        value = match.group(1).strip()
        return value or None

    def _parse_dynamic(self, item: dict) -> dict:
        """
        解析动态数据

        新 API 返回的动态类型：
        - DYNAMIC_TYPE_AV: 视频动态
        - DYNAMIC_TYPE_WORD: 纯文字动态
        - DYNAMIC_TYPE_DRAW: 图片动态
        - DYNAMIC_TYPE_OPUS: 图文动态（大图）
        """
        dynamic_id = item.get("id_str")
        dynamic_type_str = item.get("type", "")

        # 跳过转发动态
        if item.get("orig"):
            return None

        modules = item.get("modules", {})
        module_author = modules.get("module_author", {})
        module_dynamic = modules.get("module_dynamic", {})

        # 获取文本内容
        text = ""
        image_urls = []

        # 根据 major.type 判断内容类型（而不是 dynamic_type_str）
        major = module_dynamic.get("major") or {}
        major_type = major.get("type", "")

        # MAJOR_TYPE_OPUS - 图文动态或新版带图片的动态
        if major_type == "MAJOR_TYPE_OPUS":
            opus = major.get("opus") or {}
            # summary 可能是一个 dict 或 string
            summary = opus.get("summary", "")
            if isinstance(summary, dict):
                text = summary.get("text", "") or ""
            else:
                text = summary or ""
            # 获取图片 - 从 pics 字段
            for img in opus.get("pics") or []:
                if isinstance(img, dict):
                    src = img.get("url", "")
                    if src:
                        image_urls.append(src)

        # MAJOR_TYPE_ARCHIVE - 视频动态
        elif major_type == "MAJOR_TYPE_ARCHIVE":
            archive = major.get("archive") or {}
            text = archive.get("title", "") or archive.get("desc", "")

        # MAJOR_TYPE_COMMON - 普通内容（文字或图片）
        elif major_type == "MAJOR_TYPE_COMMON":
            common = major.get("common") or {}
            text = common.get("desc", "")
            # 获取图片
            for img in common.get("images") or []:
                if isinstance(img, dict):
                    src = img.get("src", "")
                    if src:
                        image_urls.append(src)

        # MAJOR_TYPE_UGC_SEASON 或其他视频类型
        elif major_type == "MAJOR_TYPE_UGC_SEASON":
            ugc_season = major.get("ugc_season") or {}
            text = ugc_season.get("title", "")

        else:
            # 尝试兼容旧的 dynamic_type_str 方式
            if dynamic_type_str == "DYNAMIC_TYPE_AV":
                archive = major.get("archive") or {}
                text = archive.get("title", "") or archive.get("desc", "")
            elif dynamic_type_str in ["DYNAMIC_TYPE_WORD", "DYNAMIC_TYPE_DRAW", "DYNAMIC_TYPE_OPUS"]:
                opus = major.get("opus") or {}
                if opus:
                    text = opus.get("summary", "") or opus.get("title", "")
                    for img in opus.get("images") or []:
                        if isinstance(img, dict):
                            image_urls.append(img.get("url", ""))
                else:
                    common = major.get("common") or {}
                    text = common.get("desc", "")
                    for img in common.get("images") or []:
                        if isinstance(img, dict):
                            src = img.get("src", "")
                            if src:
                                image_urls.append(src)

        text = text.strip()
        if not text:
            return None

        # 获取发布时间
        pub_ts_str = module_author.get("pub_ts", "0")
        pub_time = module_author.get("pub_time", "")

        # 将时间戳转换为 datetime 对象（pub_ts 可能是字符串）
        pub_datetime = None
        try:
            pub_ts = int(pub_ts_str)
            if pub_ts > 0:
                pub_datetime = datetime.fromtimestamp(pub_ts)
        except (ValueError, TypeError):
            pass

        return {
            "dynamic_id": dynamic_id,
            "type": dynamic_type_str,
            "is_video": dynamic_type_str == "DYNAMIC_TYPE_AV",
            "text": text,
            "uploader_name": module_author.get("name", "") or module_author.get("uname", ""),
            "image_urls": image_urls,
            "pub_time": pub_datetime,
            "pub_ts": pub_ts,
            "images": []
        }

    def download_images(self, dynamic: dict) -> dict:
        images = []
        for idx, url in enumerate(dynamic.get("image_urls", [])):
            try:
                resp = self.session.get(url, timeout=20)
                resp.raise_for_status()
                filename = f"{dynamic['dynamic_id']}_{idx}.jpg"
                path = self.image_dir / filename
                path.write_bytes(resp.content)
                images.append(str(path))
            except Exception as e:
                logger.warning("下载动态图片失败: %s, %s", url, e)

        dynamic["images"] = images
        return dynamic


def should_push_dynamic(dynamic: dict) -> bool:
    text = (dynamic.get("text", "") or "").strip()

    if not text:
        return False

    if text.startswith("转发") or text.startswith("//@"):
        return False

    if text.startswith("http") and len(text) < 120:
        return False

    if len(text) < 10:
        return False

    banned_keywords = ["秒杀", "折扣", "限时"]
    if any(kw in text for kw in banned_keywords):
        return False

    return True


def is_dynamic_recent(pub_time: datetime | int | float | str | None, max_age_hours: int = 12) -> bool:
    """Return True when the dynamic was published within the recent window."""
    if not pub_time:
        return False

    parsed_pub_time = None
    if isinstance(pub_time, datetime):
        parsed_pub_time = pub_time
    elif isinstance(pub_time, (int, float)):
        try:
            parsed_pub_time = datetime.fromtimestamp(int(pub_time))
        except (ValueError, OSError, OverflowError, TypeError):
            return False
    elif isinstance(pub_time, str):
        value = pub_time.strip()
        if not value:
            return False
        try:
            parsed_pub_time = datetime.fromisoformat(value)
        except ValueError:
            try:
                parsed_pub_time = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return False
    else:
        return False

    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    return parsed_pub_time >= cutoff


try:
    # Backward-compatible re-export for callers that still import from app.modules.dynamic.
    from app.modules.dynamic_summary import process_dynamic_text
except Exception as exc:  # pragma: no cover - only used if the optional summary module fails to load
    def process_dynamic_text(*args, **kwargs):
        raise RuntimeError("dynamic summary module failed to load") from exc
