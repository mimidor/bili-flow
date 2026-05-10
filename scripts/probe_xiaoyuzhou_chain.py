#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.modules.xiaoyuzhou_sdk import XiaoyuzhouClient, XyzApiError  # noqa: E402


def _mask(value: str | None, keep: int = 8) -> str:
    if not value:
        return "<empty>"
    text = value.strip()
    if len(text) <= keep * 2:
        return text
    return f"{text[:keep]}...{text[-keep:]}"


def _prompt_if_missing(value: str | None, label: str) -> str:
    if value:
        return value.strip()
    return input(f"{label}: ").strip()


def _extract_tokens(response: dict) -> tuple[str | None, str | None, str | None, dict]:
    data = response.get("data")
    if not isinstance(data, dict):
        return None, None, None, response
    access = data.get("x-jike-access-token") or data.get("access_token") or data.get("accessToken")
    refresh = data.get("x-jike-refresh-token") or data.get("refresh_token") or data.get("refreshToken")
    device_id = (
        data.get("x-jike-device-id")
        or data.get("device_id")
        or data.get("deviceId")
        or data.get("xJikeDeviceId")
    )
    user = data.get("data") if isinstance(data.get("data"), dict) else data
    return (
        access.strip() if isinstance(access, str) else None,
        refresh.strip() if isinstance(refresh, str) else None,
        device_id.strip() if isinstance(device_id, str) else None,
        user if isinstance(user, dict) else response,
    )


def _save_env(access_token: str, refresh_token: str | None, device_id: str | None) -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    def upsert(key: str, value: str) -> None:
        nonlocal lines
        rendered = f'{key}="{value}"'
        for index, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[index] = rendered
                return
        lines.append(rendered)

    if device_id is not None:
        upsert("XYZ_DEVICE_ID", device_id)
    upsert("XYZ_ACCESS_TOKEN", access_token)
    if refresh_token is not None:
        upsert("XYZ_REFRESH_TOKEN", refresh_token)

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe xiaoyuzhou login and episode list chain.")
    parser.add_argument("--mobile", help="mobile number for SMS login")
    parser.add_argument("--area-code", default="+86", help="area code, default: +86")
    parser.add_argument("--code", help="SMS verification code")
    parser.add_argument("--pid", required=True, help="podcast pid to probe")
    parser.add_argument("--access-token", help="reuse an existing access token instead of logging in")
    parser.add_argument("--refresh-token", help="reuse an existing refresh token if available")
    parser.add_argument("--device-id", help="reuse an existing device id if available")
    parser.add_argument("--save-env", action="store_true", help="write tokens back to .env")
    parser.add_argument("--send-code-only", action="store_true", help="only send SMS code and exit")
    args = parser.parse_args()

    client = XiaoyuzhouClient(
        access_token=args.access_token or "",
        refresh_token=args.refresh_token or "",
        device_id=args.device_id or "",
    )
    try:
        if args.access_token:
            print(f"[probe] using provided access token: {_mask(args.access_token)}")
        else:
            mobile = _prompt_if_missing(args.mobile, "mobile")
            if not mobile:
                print("[probe] missing mobile number")
                return 2

            send_resp = client.send_code(mobile, args.area_code)
            print("[probe] send_code response:")
            print(json.dumps(send_resp, ensure_ascii=False, indent=2))
            if args.send_code_only:
                return 0

            code = _prompt_if_missing(args.code, "sms code")
            if not code:
                print("[probe] missing sms code")
                return 2

            login_resp = client.login_with_sms(mobile, code, args.area_code)
            access_token, refresh_token, device_id, user_payload = _extract_tokens(login_resp)
            print("[probe] login user payload:")
            print(json.dumps(user_payload, ensure_ascii=False, indent=2))
            print(f"[probe] access token: {_mask(access_token)}")
            print(f"[probe] refresh token: {_mask(refresh_token)}")
            print(f"[probe] device id: {_mask(device_id)}")

            if not access_token:
                print("[probe] login did not return an access token")
                return 1

            client.set_tokens(access_token=access_token, refresh_token=refresh_token)
            if args.save_env:
                _save_env(access_token, refresh_token, device_id or args.device_id)
                print("[probe] tokens saved to .env")

        print(f"[probe] fetching episode list for pid={args.pid}")
        page = client.get_episode_list(args.pid)
        print(f"[probe] episode count: {len(page.items)}")
        print(f"[probe] cursor: {page.cursor}")
        if page.items:
            first = page.items[0]
            print("[probe] first episode:")
            print(
                json.dumps(
                    {
                        "eid": first.eid,
                        "pid": first.pid,
                        "title": first.title,
                        "pub_date": first.pub_date.isoformat() if first.pub_date else None,
                        "audio_url": first.audio_url,
                        "audio_mime": first.audio_mime,
                        "audio_size": first.audio_size,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        print("[probe] chain ok")
        return 0
    except XyzApiError as exc:
        print(f"[probe] xyz api error: {exc}")
        return 1
    except Exception as exc:
        print(f"[probe] unexpected error: {type(exc).__name__}: {exc}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
