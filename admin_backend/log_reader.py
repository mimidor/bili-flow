from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from app.utils.runtime_home import get_logs_dir

LOG_DIR = get_logs_dir()
BASE_LOG_FILE = "bili.log"
LOG_HEADER_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (?P<module>.+?) - (?P<level>[A-Z]+) - (?P<message>.*)$"
)
ROTATED_LOG_RE = re.compile(r"^bili\.log\.(\d{4}-\d{2}-\d{2})$")
ALERT_LEVELS = {"WARNING", "ERROR", "CRITICAL"}
MAX_WINDOW_DAYS = 30
DEFAULT_WINDOW_DAYS = 7
DEFAULT_CONTEXT_LINES = 12


@dataclass(slots=True)
class LogRecord:
    source_file: str
    line_start: int
    line_end: int
    timestamp: datetime
    module: str
    level: str
    message: str
    raw_lines: list[str]

    @property
    def raw_text(self) -> str:
        return "\n".join(self.raw_lines)

    @property
    def has_multiline(self) -> bool:
        return len(self.raw_lines) > 1

    def to_item(self) -> dict[str, object]:
        return {
            "id": encode_log_id(self.source_file, self.line_start, self.line_end),
            "source_file": self.source_file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "timestamp": self.timestamp.isoformat(timespec="milliseconds"),
            "level": self.level,
            "module": self.module,
            "message": self.message,
            "excerpt": _excerpt(self.raw_text, 220),
            "has_multiline": self.has_multiline,
        }

    def to_alert_item(self) -> dict[str, object]:
        item = self.to_item()
        item["excerpt"] = _excerpt(self.raw_text, 260)
        return item


def encode_log_id(source_file: str, line_start: int, line_end: int) -> str:
    raw = f"{source_file}|{line_start}|{line_end}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def decode_log_id(log_id: str) -> tuple[str, int, int]:
    padding = "=" * (-len(log_id) % 4)
    raw = base64.urlsafe_b64decode((log_id + padding).encode("ascii")).decode("utf-8")
    source_file, start, end = raw.split("|", 2)
    return Path(source_file).name, int(start), int(end)


def _excerpt(text: str, length: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= length:
        return compact
    return f"{compact[:length]}..."


def _parse_log_timestamp(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S,%f")
    except Exception:
        return None


def _infer_file_date(path: Path) -> date | None:
    if path.name == BASE_LOG_FILE:
        try:
            return datetime.fromtimestamp(path.stat().st_mtime).date()
        except Exception:
            return None
    match = ROTATED_LOG_RE.match(path.name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except Exception:
            return None
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).date()
    except Exception:
        return None


def _normalize_window_days(window_days: int | None) -> int:
    value = window_days or DEFAULT_WINDOW_DAYS
    return max(1, min(value, MAX_WINDOW_DAYS))


def _discover_log_files(
    *,
    window_days: int | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[Path]:
    if not LOG_DIR.exists():
        return []

    window = _normalize_window_days(window_days)
    today = datetime.now().date()
    start_date = start.date() if start else today - timedelta(days=window - 1)
    end_date = end.date() if end else today

    candidates: list[tuple[date, float, Path]] = []
    for path in LOG_DIR.glob("bili.log*"):
        if not path.is_file():
            continue
        file_date = _infer_file_date(path)
        if file_date is None:
            continue
        if file_date < start_date or file_date > end_date:
            continue
        try:
            mtime = path.stat().st_mtime
        except Exception:
            mtime = 0.0
        candidates.append((file_date, mtime, path))

    candidates.sort(key=lambda item: (item[0], item[1], item[2].name), reverse=True)
    return [path for _, _, path in candidates]


def _matches_filters(
    record: LogRecord,
    *,
    level: str | None = None,
    module: str | None = None,
    q: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> bool:
    if level and record.level.upper() != level.upper():
        return False
    if module and module.lower() not in record.module.lower():
        return False
    if start and record.timestamp < start:
        return False
    if end and record.timestamp > end:
        return False
    if q:
        needle = q.strip().lower()
        haystack = " ".join((record.module, record.level, record.message, record.raw_text, record.source_file)).lower()
        if needle not in haystack:
            return False
    return True


def parse_log_file(path: Path) -> list[LogRecord]:
    records: list[LogRecord] = []
    current: LogRecord | None = None

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_no, raw_line in enumerate(handle, start=1):
                line = raw_line.rstrip("\r\n")
                match = LOG_HEADER_RE.match(line)
                if match:
                    if current is not None:
                        records.append(current)
                    timestamp = _parse_log_timestamp(match.group("timestamp"))
                    if timestamp is None:
                        current = None
                        continue
                    current = LogRecord(
                        source_file=path.name,
                        line_start=line_no,
                        line_end=line_no,
                        timestamp=timestamp,
                        module=match.group("module").strip(),
                        level=match.group("level").strip().upper(),
                        message=match.group("message").strip(),
                        raw_lines=[line],
                    )
                    continue

                if current is not None:
                    current.raw_lines.append(line)
                    current.line_end = line_no
        if current is not None:
            records.append(current)
    except FileNotFoundError:
        return []
    except Exception:
        return []

    return records


def _load_records(
    *,
    window_days: int | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[list[LogRecord], list[str]]:
    files = _discover_log_files(window_days=window_days, start=start, end=end)
    records: list[LogRecord] = []
    scanned_files: list[str] = []
    for path in files:
        scanned_files.append(path.name)
        records.extend(parse_log_file(path))
    records.sort(key=lambda item: (item.timestamp, item.source_file, item.line_start), reverse=True)
    return records, scanned_files


def query_logs(
    *,
    page: int,
    page_size: int,
    level: str | None = None,
    module: str | None = None,
    source_file: str | None = None,
    q: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    window_days: int | None = None,
) -> dict[str, object]:
    records, scanned_files = _load_records(window_days=window_days, start=start, end=end)
    filtered = [
        record
        for record in records
        if _matches_filters(record, level=level, module=module, q=q, start=start, end=end)
        and (not source_file or record.source_file == source_file)
    ]
    total = len(filtered)
    offset = (page - 1) * page_size
    items = [record.to_item() for record in filtered[offset : offset + page_size]]
    recent_alerts = [record.to_alert_item() for record in records if record.level in ALERT_LEVELS][:10]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
        "recent_alerts": recent_alerts,
        "scanned_files": scanned_files,
        "window_days": _normalize_window_days(window_days),
    }


def get_log_detail(log_id: str, context_lines: int | None = None) -> dict[str, object]:
    source_file, line_start, line_end = decode_log_id(log_id)
    path = LOG_DIR / source_file
    if not path.exists():
        raise FileNotFoundError(source_file)

    window = max(0, context_lines or DEFAULT_CONTEXT_LINES)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        raise LookupError(log_id)

    target_index = max(0, line_start - 1)
    begin = max(0, target_index - window)
    end_index = min(len(lines), line_end + window)
    context = []
    for index in range(begin, end_index):
        context.append(
            {
                "line_no": index + 1,
                "text": lines[index],
                "is_target": line_start <= index + 1 <= line_end,
            }
        )

    records = parse_log_file(path)
    record = next((item for item in records if item.line_start == line_start and item.line_end == line_end), None)
    if record is None:
        raise LookupError(log_id)

    return {
        "id": log_id,
        "source_file": record.source_file,
        "line_start": record.line_start,
        "line_end": record.line_end,
        "timestamp": record.timestamp.isoformat(timespec="milliseconds"),
        "level": record.level,
        "module": record.module,
        "message": record.message,
        "raw_text": record.raw_text,
        "has_multiline": record.has_multiline,
        "context_lines": context,
    }
