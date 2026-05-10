from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx
import requests

from app.utils.logger import get_logger
from config import Config

logger = get_logger("xiaoyuzhou")

JsonDict = dict[str, Any]


class XyzApiError(RuntimeError):
    pass


@dataclass(slots=True)
class PodcastEpisodePayload:
    eid: str
    pid: str
    title: str
    pub_date: datetime | None
    audio_url: str
    audio_mime: str | None
    audio_size: int | None
    raw: JsonDict


@dataclass(slots=True)
class PodcastEpisodePage:
    items: list[PodcastEpisodePayload]
    cursor: JsonDict | None


@dataclass(slots=True)
class AuthTokenPair:
    access_token: str
    refresh_token: str | None = None
    raw: JsonDict | None = None


class XiaoyuzhouClient:
    DEFAULT_API_BASE_URL = "https://api.xiaoyuzhoufm.com"
    DEFAULT_PODCASTER_API_BASE_URL = "https://podcaster-api.xiaoyuzhoufm.com"

    def __init__(
        self,
        base_url: str | None = None,
        access_token: str | None = None,
        device_id: str | None = None,
        client: httpx.Client | None = None,
        podcaster_api_base_url: str | None = None,
        refresh_token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_base_url = (base_url or Config.XYZ_BASE_URL or self.DEFAULT_API_BASE_URL).rstrip("/")
        self._podcaster_api_base_url = (podcaster_api_base_url or self.DEFAULT_PODCASTER_API_BASE_URL).rstrip("/")
        self._access_token = self._normalize_token(access_token or Config.XYZ_ACCESS_TOKEN or "")
        self._refresh_token = self._normalize_token(refresh_token or getattr(Config, "XYZ_REFRESH_TOKEN", "") or "")
        self._device_id = self._normalize_token(
            device_id
            or getattr(Config, "XYZ_DEVICE_ID", "")
            or os.getenv("XIAOYUZHOU_ID", "")
            or os.getenv("XYZ_DEVICE_ID", "")
        )
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "XiaoyuzhouClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def access_token(self) -> str:
        return self._access_token

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    @property
    def device_id(self) -> str:
        return self._device_id

    def set_tokens(self, access_token: str | None = None, refresh_token: str | None = None) -> None:
        if access_token is not None:
            self._access_token = self._normalize_token(access_token)
        if refresh_token is not None:
            self._refresh_token = self._normalize_token(refresh_token)

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        base: str = "api",
        auth: bool = True,
    ) -> JsonDict:
        body = dict(payload or {})
        return self._request_json(
            method=method,
            path=path,
            payload=body if body else None,
            params=dict(params or {}) or None,
            headers=dict(headers or {}) or None,
            base=base,
            auth=auth,
        )

    def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        base: str = "api",
        auth: bool = True,
    ) -> JsonDict:
        return self.request_json("GET", path, params=params, headers=headers, base=base, auth=auth)

    def post_json(
        self,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        base: str = "api",
        auth: bool = True,
    ) -> JsonDict:
        return self.request_json("POST", path, payload=payload, headers=headers, base=base, auth=auth)

    def send_code(self, mobile_phone_number: str, area_code: str = "+86") -> JsonDict:
        if not mobile_phone_number:
            raise ValueError("mobile_phone_number is required")
        return self.post_json(
            "/v1/auth/send-code",
            payload={
                "mobilePhoneNumber": mobile_phone_number,
                "areaCode": area_code or "+86",
            },
            base="podcaster",
            auth=False,
            headers=self._podcaster_auth_headers(),
        )

    def login_with_sms(self, mobile_phone_number: str, verify_code: str, area_code: str = "+86") -> JsonDict:
        if not mobile_phone_number or not verify_code:
            raise ValueError("mobile_phone_number and verify_code are required")
        return self.post_json(
            "/v1/auth/login-with-sms",
            payload={
                "mobilePhoneNumber": mobile_phone_number,
                "verifyCode": verify_code,
                "areaCode": area_code or "+86",
            },
            base="podcaster",
            auth=False,
            headers=self._podcaster_auth_headers(),
        )

    def refresh_tokens(
        self,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> JsonDict:
        token = access_token or self._access_token
        refresh = refresh_token or self._refresh_token
        device_id = self._device_id
        if not token or not refresh:
            raise XyzApiError("both access_token and refresh_token are required")
        if not device_id:
            raise XyzApiError(
                "XYZ device_id is required for Xiaoyuzhou token refresh; set XYZ_DEVICE_ID "
                "(or XIAOYUZHOU_ID) in .env / runtime config"
            )
        response = self.post_json(
            "/app_auth_tokens.refresh",
            payload=None,
            base="api",
            auth=False,
            headers=self._build_headers(
                base="api",
                auth=False,
                extra={
                    "x-jike-access-token": token,
                    "x-jike-refresh-token": refresh,
                    "x-jike-device-id": device_id,
                    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                },
            ),
        )
        updated = self._update_tokens_from_refresh_response(response)
        if updated:
            self._persist_tokens_to_runtime_config()
        else:
            logger.warning("refresh response did not contain usable token fields")
        return response

    def search(
        self,
        *,
        keyword: str,
        search_type: str,
        pid: str | None = None,
        load_more_key: JsonDict | None = None,
    ) -> JsonDict:
        if not keyword or not search_type:
            raise ValueError("keyword and search_type are required")
        payload: JsonDict = {
            "limit": "20",
            "sourcePageName": "4",
            "type": search_type,
            "currentPageName": "4",
            "keyword": keyword,
        }
        if load_more_key:
            payload["loadMoreKey"] = load_more_key
        if pid:
            payload["pid"] = pid
        return self.post_json(
            "/v1/search/create",
            payload=payload,
            headers=self._api_headers(),
        )

    def search_preset(self) -> JsonDict:
        return self.get_json("/v1/search/get-preset", headers=self._api_headers())

    def get_episode_list(self, pid: str, load_more_key: JsonDict | None = None) -> PodcastEpisodePage:
        payload: JsonDict = {"pid": pid, "order": "desc"}
        if load_more_key:
            payload["loadMoreKey"] = load_more_key
        data = self.post_json("/v1/episode/list", payload=payload, headers=self._api_headers())
        inner = self._coerce_episode_list_container(data)
        items: list[PodcastEpisodePayload] = []
        for item in self._extract_episode_items(inner):
            parsed = self._parse_episode_item(item, allow_missing_audio=True)
            if not parsed.audio_url:
                logger.info("episode_list_missing_audio_fallback_detail", extra={"eid": parsed.eid})
                parsed = self.get_episode_detail(parsed.eid)
            items.append(parsed)
        cursor = self._extract_episode_cursor(data, inner)
        return PodcastEpisodePage(items=items, cursor=cursor if isinstance(cursor, dict) else None)

    def get_episode_detail(self, eid: str) -> PodcastEpisodePayload:
        data = self.get_json("/v1/episode/get", params={"eid": eid}, headers=self._api_headers())
        inner = self._coerce_episode_detail_container(data)
        return self._parse_episode_item(inner, allow_missing_audio=False)

    def discover_new_episodes(
        self,
        pid: str,
        *,
        last_seen_eid: str | None,
        bootstrap_recent_episodes: int = 3,
        max_pages: int = 5,
    ) -> tuple[list[PodcastEpisodePayload], bool, PodcastEpisodePayload | None, JsonDict | None]:
        first_page = self.get_episode_list(pid)
        latest = first_page.items[0] if first_page.items else None
        if not last_seen_eid:
            return first_page.items[:bootstrap_recent_episodes], False, latest, first_page.cursor

        collected: list[PodcastEpisodePayload] = []
        current_page = first_page
        found = False
        page_count = 0
        while page_count < max_pages:
            for item in current_page.items:
                if item.eid == last_seen_eid:
                    found = True
                    break
                collected.append(item)
            if found or not current_page.cursor:
                break
            page_count += 1
            current_page = self.get_episode_list(pid, current_page.cursor)
        gap_detected = not found and bool(collected)
        return collected, gap_detected, latest, first_page.cursor

    def get_podcast_detail(self, pid: str) -> JsonDict:
        if not pid:
            raise ValueError("pid is required")
        return self.get_json(
            "/v1/podcast/get",
            params={"pid": pid},
            headers=self._api_headers(),
        )

    def get_podcast_info(self, pid: str) -> JsonDict:
        if not pid:
            raise ValueError("pid is required")
        return self.get_json(
            "/v1/podcast/get-info",
            params={"pid": pid},
            headers=self._api_headers(),
        )

    def get_related_podcasts(self, pid: str, position: str = "BOTTOM") -> JsonDict:
        if not pid:
            raise ValueError("pid is required")
        return self.post_json(
            "/v1/related-podcast/list",
            payload={"pid": pid, "position": position or "BOTTOM"},
            headers=self._api_headers(extra={"Content-Type": "application/json"}),
        )

    def get_owned_podcasts(self, uid: str) -> JsonDict:
        if not uid:
            raise ValueError("uid is required")
        return self.post_json(
            "/v1/podcaster/owned-podcasts",
            payload={"uid": uid},
            headers=self._api_headers(extra={"Content-Type": "application/json"}),
        )

    def get_profile(self) -> JsonDict:
        return self.get_json("/v1/profile/get", headers=self._api_headers())

    def get_profile_by_uid(self, uid: str) -> JsonDict:
        if not uid:
            raise ValueError("uid is required")
        return self.get_json("/v1/profile/get", params={"uid": uid}, headers=self._api_headers())

    def get_user_stats(self, uid: str) -> JsonDict:
        if not uid:
            raise ValueError("uid is required")
        return self.get_json("/v1/user-stats/get", params={"uid": uid}, headers=self._api_headers())

    def list_following(self, uid: str) -> JsonDict:
        if not uid:
            raise ValueError("uid is required")
        return self.post_json("/v1/user-relation/list-following", payload={"uid": uid}, headers=self._api_headers())

    def list_follower(self, uid: str) -> JsonDict:
        if not uid:
            raise ValueError("uid is required")
        return self.post_json("/v1/user-relation/list-follower", payload={"uid": uid}, headers=self._api_headers())

    def list_subscriptions(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/subscription/list", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def list_starred_subscriptions(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/subscription-star/list", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def list_non_starred_subscriptions(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/subscription/list-non-starred", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def update_subscription(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/subscription/update", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def update_subscription_star(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/subscription-star/update", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def list_inbox(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/inbox/list", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def list_categories(self) -> JsonDict:
        return self.get_json("/v1/category/list-all", headers=self._api_headers())

    def list_category_tabs(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/category/podcast/list-tabs", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def list_category_podcasts(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/category/podcast/list-by-tab", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def list_primary_comments(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/comment/list-primary", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def list_thread_comments(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/comment/list-thread", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def create_comment_collect(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/comment/collect/create", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def remove_comment_collect(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/comment/collect/remove", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def list_comment_collect(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/comment/collect/list", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def create_comment(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/comment/create", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def remove_comment(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/comment/remove", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def update_comment_like(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/comment/like/update", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def get_inbox_unread_count(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/inbox/unread-count", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def get_playback_progress(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/playback-progress/list", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def update_playback_progress(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/playback-progress/update", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def get_mileage(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/mileage/get", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def list_mileage(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/mileage/list", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def update_mileage(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/mileage/update", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def list_blocked_users(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/blocked-user/list", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def create_blocked_user(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/blocked-user/create", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def remove_blocked_user(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/blocked-user/remove", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def get_user_preference(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/user-preference/get", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def update_user_preference(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/user-preference/update", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def update_relation(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/user-relation/update", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def discovery(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/discovery/list", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def editor_pick_list_history(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/editor-pick/list-history", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def pilot_discovery_list(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/pilot-discovery/list", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def refresh_episode_recommend(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/discovery/refresh-episode-recommend", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def get_top_list(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/top/list", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def get_episode_list_by_filter(self, payload: Mapping[str, Any] | None = None, **fields: Any) -> JsonDict:
        return self.post_json("/v1/episode/list-by-filter", payload=self._merge_payload(payload, **fields), headers=self._api_headers())

    def request_podcaster_api(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        auth: bool = False,
    ) -> JsonDict:
        return self.request_json(method, path, payload=payload, params=params, headers=headers, base="podcaster", auth=auth)

    def _request_json(
        self,
        *,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        base: str = "api",
        auth: bool = True,
    ) -> JsonDict:
        if auth and not self._access_token:
            raise XyzApiError("XYZ access_token is required")
        url = self._build_url(path, base=base)
        request_kwargs: dict[str, Any] = {
            "method": method,
            "url": url,
            "headers": self._build_headers(base=base, auth=auth, extra=headers),
        }
        if params:
            request_kwargs["params"] = dict(params)
        if payload is not None:
            content_type = str(request_kwargs["headers"].get("Content-Type", "")).lower()
            if "application/x-www-form-urlencoded" in content_type:
                request_kwargs["data"] = dict(payload)
            else:
                request_kwargs["json"] = dict(payload)

        refreshed = False
        while True:
            try:
                response = self._client.request(**request_kwargs)
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                if (
                    not refreshed
                    and auth
                    and base == "api"
                    and path != "/app_auth_tokens.refresh"
                    and exc.response is not None
                    and exc.response.status_code == httpx.codes.UNAUTHORIZED
                    and self._refresh_token
                ):
                    logger.warning("x-jike-access-token 失效，尝试使用 refresh_token 自动续期后重试")
                    self.refresh_tokens()
                    request_kwargs["headers"] = self._build_headers(base=base, auth=auth, extra=headers)
                    refreshed = True
                    continue
                raise

        if not response.content:
            return {}

        payload_data = response.json()
        if isinstance(payload_data, dict):
            code = payload_data.get("code")
            if isinstance(code, int) and code not in {0, 200}:
                raise XyzApiError(
                    payload_data.get("msg")
                    or payload_data.get("message")
                    or f"xyz request failed with code {code}"
                )
        return payload_data

    def _update_tokens_from_refresh_response(self, response: JsonDict) -> bool:
        candidate = self._find_refresh_candidate(response)
        if not candidate:
            return False

        updated = False
        new_access_token = (
            candidate.get("x-jike-access-token")
            or candidate.get("access_token")
            or candidate.get("accessToken")
            or candidate.get("token")
        )
        new_refresh_token = (
            candidate.get("x-jike-refresh-token")
            or candidate.get("refresh_token")
            or candidate.get("refreshToken")
        )
        if isinstance(new_access_token, str) and new_access_token.strip():
            self._access_token = self._normalize_token(new_access_token)
            updated = True
        if isinstance(new_refresh_token, str) and new_refresh_token.strip():
            self._refresh_token = self._normalize_token(new_refresh_token)
            updated = True
        return updated

    def _persist_tokens_to_runtime_config(self) -> None:
        updates: dict[str, str] = {}
        if self._access_token:
            updates["XYZ_ACCESS_TOKEN"] = self._access_token
        if self._refresh_token:
            updates["XYZ_REFRESH_TOKEN"] = self._refresh_token
        if not updates:
            return
        try:
            from app.utils.runtime_config import upsert_runtime_config_values

            upsert_runtime_config_values(updates)
        except Exception as exc:
            logger.warning("failed to persist xiaoyuzhou tokens to runtime config: %s", exc)
        for key, value in updates.items():
            os.environ[key] = value

    def _find_refresh_candidate(self, response: JsonDict) -> Mapping[str, Any] | None:
        candidates: list[Mapping[str, Any]] = []
        if isinstance(response, Mapping):
            candidates.append(response)
            data = response.get("data")
            if isinstance(data, Mapping):
                candidates.append(data)
                nested = data.get("data")
                if isinstance(nested, Mapping):
                    candidates.append(nested)
                for extra_key in ("result", "payload", "tokens", "token"):
                    extra = data.get(extra_key)
                    if isinstance(extra, Mapping):
                        candidates.append(extra)
        for candidate in candidates:
            for field in (
                "x-jike-access-token",
                "access_token",
                "accessToken",
                "token",
                "x-jike-refresh-token",
                "refresh_token",
                "refreshToken",
            ):
                value = candidate.get(field)
                if isinstance(value, str) and value.strip():
                    return candidate
        return None

    def _build_url(self, path: str, *, base: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        root = self._podcaster_api_base_url if base == "podcaster" else self._api_base_url
        return f"{root}{path}"

    def _build_headers(
        self,
        *,
        base: str,
        auth: bool,
        extra: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        headers = self._default_headers(base=base)
        if auth and self._access_token:
            headers["x-jike-access-token"] = self._access_token
        if extra:
            rendered_extra = {str(key): str(value) for key, value in extra.items()}
            if auth:
                # Callers often pass a snapshot built before token refresh.
                # Ignore stale auth headers so retries always use the latest token pair.
                rendered_extra.pop("x-jike-access-token", None)
                rendered_extra.pop("X-Jike-Access-Token", None)
                rendered_extra.pop("x-jike-refresh-token", None)
                rendered_extra.pop("X-Jike-Refresh-Token", None)
                rendered_extra.pop("authorization", None)
                rendered_extra.pop("Authorization", None)
            headers.update(rendered_extra)
        return headers

    def _api_headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        return self._build_headers(base="api", auth=True, extra=extra)

    def _default_headers(self, *, base: str) -> dict[str, str]:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        headers: dict[str, str] = {
            "Host": "api.xiaoyuzhoufm.com",
            "User-Agent": "Xiaoyuzhou/2.57.1 (build:1576; Python SDK)",
            "Market": "AppStore",
            "App-BuildNo": "1576",
            "OS": "ios",
            "Manufacturer": "Apple",
            "BundleID": "app.podcast.cosmos",
            "Connection": "keep-alive",
            "abtest-info": "{\"old_user_discovery_feed\":\"enable\"}",
            "Accept-Language": "zh-Hant-HK;q=1.0, zh-Hans-CN;q=0.9",
            "Model": "iPhone14,2",
            "app-permissions": "4",
            "Accept": "*/*",
            "Content-Type": "application/json",
            "App-Version": "2.57.1",
            "WifiConnected": "true",
            "OS-Version": "17.4.1",
            "x-custom-xiaoyuzhou-app-dev": "",
            "Local-Time": now,
            "Timezone": "Asia/Shanghai",
        }
        if base == "api" and self._device_id:
            headers["x-jike-device-id"] = self._device_id
        if base == "podcaster":
            headers.update(
                {
                    "Host": "podcaster-api.xiaoyuzhoufm.com",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Origin": "https://podcaster.xiaoyuzhoufm.com",
                    "Referer": "https://podcaster.xiaoyuzhoufm.com/",
                    "Content-Type": "application/json;charset=UTF-8",
                }
            )
        return headers

    def _podcaster_auth_headers(self) -> dict[str, str]:
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://podcaster.xiaoyuzhoufm.com",
            "referer": "https://podcaster.xiaoyuzhoufm.com/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }

    @staticmethod
    def _normalize_token(value: str) -> str:
        return str(value or "").strip()

    @staticmethod
    def _coerce_episode_list_container(data: JsonDict) -> Mapping[str, Any] | list[Any]:
        inner = data.get("data", {})
        if isinstance(inner, Mapping):
            return inner
        if isinstance(inner, list):
            return inner
        return []

    @staticmethod
    def _coerce_episode_detail_container(data: JsonDict) -> JsonDict:
        inner = data.get("data", {})
        if isinstance(inner, Mapping):
            nested = inner.get("data")
            if isinstance(nested, Mapping):
                return dict(nested)
            return dict(inner)
        if isinstance(inner, list) and inner and isinstance(inner[0], Mapping):
            return dict(inner[0])
        if isinstance(data, Mapping):
            nested = data.get("data")
            if isinstance(nested, Mapping):
                return dict(nested)
        return {}

    @staticmethod
    def _extract_episode_items(container: Mapping[str, Any] | list[Any]) -> list[JsonDict]:
        if isinstance(container, list):
            return [item for item in container if isinstance(item, Mapping)]  # type: ignore[list-item]
        for key in ("data", "items", "list"):
            value = container.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, Mapping)]  # type: ignore[list-item]
        return []

    @staticmethod
    def _extract_episode_cursor(data: JsonDict, container: Mapping[str, Any] | list[Any]) -> JsonDict | None:
        if isinstance(container, Mapping):
            cursor = container.get("loadMoreKey") or container.get("loadNextKey")
            if isinstance(cursor, Mapping):
                return dict(cursor)
            if cursor is not None:
                return {"value": cursor}
        cursor = data.get("loadMoreKey") or data.get("loadNextKey")
        if isinstance(cursor, Mapping):
            return dict(cursor)
        if cursor is not None:
            return {"value": cursor}
        return None

    def _merge_payload(
        self,
        payload: Mapping[str, Any] | None = None,
        **fields: Any,
    ) -> JsonDict:
        merged: JsonDict = {}
        if payload:
            merged.update(dict(payload))
        for key, value in fields.items():
            if value is not None:
                merged[key] = value
        return merged

    def _parse_episode_item(self, raw: JsonDict, *, allow_missing_audio: bool) -> PodcastEpisodePayload:
        audio_url = self._pick_audio_url(raw)
        if not audio_url and not allow_missing_audio:
            raise XyzApiError(f"episode {raw.get('eid')} missing audio url")
        media = raw.get("media") or {}
        pub_date = self._parse_pub_date(raw.get("pubDate"))
        return PodcastEpisodePayload(
            eid=str(raw.get("eid") or ""),
            pid=str(raw.get("pid") or ""),
            title=str(raw.get("title") or raw.get("eid") or ""),
            pub_date=pub_date,
            audio_url=audio_url or "",
            audio_mime=media.get("mimeType"),
            audio_size=media.get("size"),
            raw=raw,
        )

    def _pick_audio_url(self, raw: JsonDict) -> str | None:
        media = raw.get("media") or {}
        source = media.get("source") or {}
        enclosure = raw.get("enclosure") or {}
        return source.get("url") or enclosure.get("url")

    def _parse_pub_date(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(int(value))
            except Exception:
                return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    return datetime.strptime(text, fmt)
                except ValueError:
                    continue
        return None


def download_episode_audio(
    audio_url: str,
    output_path: str | Path,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        logger.info("audio file already exists, skip download: %s", target)
        return target

    parsed = urlparse(audio_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"invalid audio url: {audio_url}")

    request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.xiaoyuzhoufm.com",
    }
    if headers:
        request_headers.update(headers)

    logger.info("downloading xiaoyuzhou audio: %s", audio_url)
    with requests.get(audio_url, headers=request_headers, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with target.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    logger.info("xiaoyuzhou audio downloaded: %s", target)
    return target


__all__ = [
    "AuthTokenPair",
    "JsonDict",
    "PodcastEpisodePage",
    "PodcastEpisodePayload",
    "XiaoyuzhouClient",
    "XyzApiError",
    "download_episode_audio",
]
