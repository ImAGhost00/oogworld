from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import random
import re
import shutil
import uuid
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

APP_VERSION = "0.3.0"
BASE_DIR = Path(__file__).parent


def resolve_obsidian_vault_path() -> Path:
    preferred = BASE_DIR / "obsidian-vault"
    legacy = BASE_DIR / "obsidian"
    configured = os.getenv("OOGWAY_OBSIDIAN_VAULT_PATH", "").strip()
    if configured:
        configured_path = Path(configured)
        if configured_path.exists():
            return configured_path
        if preferred.exists():
            return preferred
        return configured_path
    if preferred.exists():
        return preferred
    return legacy


ACTION_LOG_PATH = Path(os.getenv("ACTIVITY_LOG_PATH", BASE_DIR / "activity_log.json"))
CHAT_LOG_PATH = Path(os.getenv("CHAT_LOG_PATH", BASE_DIR / "chat_log.json"))
STREAM_URL_PRIMARY = os.getenv("STREAM_URL_PRIMARY", os.getenv("STREAM_URL", ""))
STREAM_URL_SECONDARY = os.getenv("STREAM_URL_SECONDARY", "")
STREAM_LABEL_PRIMARY = os.getenv("STREAM_LABEL_PRIMARY", "Hut Cam")
STREAM_LABEL_SECONDARY = os.getenv("STREAM_LABEL_SECONDARY", "Water Bowl Cam")
STREAM_RESOLUTION_PRIMARY = os.getenv("STREAM_RESOLUTION_PRIMARY", "1080p")
STREAM_RESOLUTION_SECONDARY = os.getenv("STREAM_RESOLUTION_SECONDARY", "720p")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
TZ = os.getenv("TZ", "America/New_York")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SUN_LAT = os.getenv("SUN_LAT", "40.7128")
SUN_LNG = os.getenv("SUN_LNG", "-74.0060")
BEDTIME_SOON_MINUTES = int(os.getenv("BEDTIME_SOON_MINUTES", "90"))
OOGWAY_BRAIN_ENABLED = os.getenv("OOGWAY_BRAIN_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OOGWAY_BRAIN_NAME = os.getenv("OOGWAY_BRAIN_NAME", "Oogway")
OOGWAY_OLLAMA_BASE = os.getenv("OOGWAY_OLLAMA_BASE", "http://ollama:11434").strip() or "http://ollama:11434"
OOGWAY_OLLAMA_MODEL = os.getenv("OOGWAY_OLLAMA_MODEL", "llama3.1:8b").strip() or "llama3.1:8b"
OOGWAY_OLLAMA_VISION_MODEL = (
    os.getenv("OOGWAY_OLLAMA_VISION_MODEL", "llama3.2-vision:latest").strip() or "llama3.2-vision:latest"
)
OOGWAY_BRAIN_PERSONALITY = os.getenv(
    "OOGWAY_BRAIN_PERSONALITY",
    "You are Oogway, a warm and observant tortoise who talks like a living terrarium companion.",
)
OOGWAY_BRAIN_INTERVAL_SECONDS = max(45, int(os.getenv("OOGWAY_BRAIN_INTERVAL_SECONDS", "120")))
OOGWAY_BRAIN_MENTION_TRIGGER = os.getenv("OOGWAY_BRAIN_MENTION_TRIGGER", "@oogway")
OOGWAY_BRAIN_CAMERA_KEY = os.getenv("OOGWAY_BRAIN_CAMERA_KEY", "both")
OOGWAY_BRAIN_MOVEMENT_WINDOW_SECONDS = max(
    60,
    int(os.getenv("OOGWAY_BRAIN_MOVEMENT_WINDOW_SECONDS", "1800")),
)
OOGWAY_BRAIN_MOTION_THRESHOLD = max(
    0.01,
    min(1.0, float(os.getenv("OOGWAY_BRAIN_MOTION_THRESHOLD", "0.06"))),
)
OOGWAY_BRAIN_CARE_CHECK_INTERVAL_SECONDS = max(
    60,
    int(os.getenv("OOGWAY_BRAIN_CARE_CHECK_INTERVAL_SECONDS", "180")),
)
OOGWAY_BRAIN_CARE_EMPTY_CONFIRMATIONS = max(
    2,
    int(os.getenv("OOGWAY_BRAIN_CARE_EMPTY_CONFIRMATIONS", "3")),
)
OOGWAY_BRAIN_CARE_ALERT_COOLDOWN_SECONDS = max(
    300,
    int(os.getenv("OOGWAY_BRAIN_CARE_ALERT_COOLDOWN_SECONDS", "3600")),
)
OOGWAY_BRAIN_EATING_CHECK_INTERVAL_SECONDS = max(
    30,
    int(os.getenv("OOGWAY_BRAIN_EATING_CHECK_INTERVAL_SECONDS", "45")),
)
OOGWAY_BRAIN_EATING_REACT_COOLDOWN_SECONDS = max(
    60,
    int(os.getenv("OOGWAY_BRAIN_EATING_REACT_COOLDOWN_SECONDS", "180")),
)
OOGWAY_BRAIN_BEHAVIOR_CHECK_INTERVAL_SECONDS = max(
    30,
    int(os.getenv("OOGWAY_BRAIN_BEHAVIOR_CHECK_INTERVAL_SECONDS", "60")),
)
OOGWAY_BRAIN_ACTIVITY_LOG_INTERVAL_SECONDS = max(
    300,
    int(os.getenv("OOGWAY_BRAIN_ACTIVITY_LOG_INTERVAL_SECONDS", "300")),
)
OOGWAY_BRAIN_FALLEN_ALERT_COOLDOWN_SECONDS = max(
    300,
    int(os.getenv("OOGWAY_BRAIN_FALLEN_ALERT_COOLDOWN_SECONDS", "1800")),
)
OOGWAY_TEXTS_STYLE = os.getenv("OOGWAY_TEXTS_STYLE", "auto").strip().lower()
OOGWAY_TEXTS_ANGER_AFTER_SECONDS = max(
    900,
    int(os.getenv("OOGWAY_TEXTS_ANGER_AFTER_SECONDS", "14400")),
)
OOGWAY_LOG_LEVEL = os.getenv("OOGWAY_LOG_LEVEL", "INFO").strip().upper() or "INFO"
OOGWAY_BRAIN_FILE_LOG_PATH = os.getenv("OOGWAY_BRAIN_FILE_LOG_PATH", "").strip()
OOGWAY_OBSIDIAN_VAULT_PATH = resolve_obsidian_vault_path()
OOGWAY_OBSIDIAN_MEMORY_FOLDER = os.getenv("OOGWAY_OBSIDIAN_MEMORY_FOLDER", "Oogway Memory").strip() or "Oogway Memory"
OOGWAY_CORE_BRAIN_NOTE = os.getenv("OOGWAY_CORE_BRAIN_NOTE", "Oogway Core Brain Prompt.md").strip() or "Oogway Core Brain Prompt.md"
OOGWAY_BRAIN_INDEX_NOTE = os.getenv("OOGWAY_BRAIN_INDEX_NOTE", "Brain Index.md").strip() or "Brain Index.md"
OOGWAY_PRIVATE_THOUGHTS_ENABLED = os.getenv("OOGWAY_PRIVATE_THOUGHTS_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OOGWAY_BRAIN_CONTEXT_CHAT_CAP = max(8, int(os.getenv("OOGWAY_BRAIN_CONTEXT_CHAT_CAP", "24")))
OOGWAY_TEXTS_TOPIC = os.getenv("OOGWAY_TEXTS_TOPIC", "oogworldtexts").strip()
CHAT_RETENTION_HOURS = max(1, int(os.getenv("CHAT_RETENTION_HOURS", "12")))
CHAT_RETENTION_SWEEP_SECONDS = max(30, int(os.getenv("CHAT_RETENTION_SWEEP_SECONDS", "60")))
OOGWAY_BRAIN_CHAT_TIMEOUT_SECONDS = max(20, int(os.getenv("OOGWAY_BRAIN_CHAT_TIMEOUT_SECONDS", "45")))
OOGWAY_BRAIN_VISION_TIMEOUT_SECONDS = max(12, int(os.getenv("OOGWAY_BRAIN_VISION_TIMEOUT_SECONDS", "30")))
OOGWAY_BRAIN_CAPTURE_TIMEOUT_SECONDS = max(4, int(os.getenv("OOGWAY_BRAIN_CAPTURE_TIMEOUT_SECONDS", "6")))
OOGWAY_BRAIN_MEMORY_MAX_EVENT_NOTES = max(80, int(os.getenv("OOGWAY_BRAIN_MEMORY_MAX_EVENT_NOTES", "320")))
OOGWAY_BRAIN_MEMORY_MAX_CHAT_LINES = max(80, int(os.getenv("OOGWAY_BRAIN_MEMORY_MAX_CHAT_LINES", "420")))
OOGWAY_BRAIN_MEMORY_MAX_ACTIVITY_LINES = max(60, int(os.getenv("OOGWAY_BRAIN_MEMORY_MAX_ACTIVITY_LINES", "260")))
OOGWAY_BRAIN_MEMORY_MAX_PROFILE_LINES = max(30, int(os.getenv("OOGWAY_BRAIN_MEMORY_MAX_PROFILE_LINES", "160")))
OOGWAY_BRAIN_MEMORY_DEDUP_LOOKBACK = max(10, int(os.getenv("OOGWAY_BRAIN_MEMORY_DEDUP_LOOKBACK", "40")))
BRAIN_CONFIG_PATH = Path(os.getenv("BRAIN_CONFIG_PATH", BASE_DIR / "brain_config.json"))

# ---------------------------------------------------------------------------
# Brain config — runtime-mutable AI settings persisted to BRAIN_CONFIG_PATH.
# On startup we load any saved overrides on top of the env-var defaults above.
# ---------------------------------------------------------------------------
_BRAIN_CONFIG_KEYS = {
    "enabled": ("OOGWAY_BRAIN_ENABLED", bool),
    "chatModel": ("OOGWAY_OLLAMA_MODEL", str),
    "visionModel": ("OOGWAY_OLLAMA_VISION_MODEL", str),
    "ollamaBase": ("OOGWAY_OLLAMA_BASE", str),
    "personality": ("OOGWAY_BRAIN_PERSONALITY", str),
    "intervalSeconds": ("OOGWAY_BRAIN_INTERVAL_SECONDS", int),
    "mentionTrigger": ("OOGWAY_BRAIN_MENTION_TRIGGER", str),
}

def _load_brain_config() -> None:
    """Load saved brain config from disk, overriding module-level globals."""
    global OOGWAY_BRAIN_ENABLED, OOGWAY_OLLAMA_MODEL, OOGWAY_OLLAMA_VISION_MODEL
    global OOGWAY_OLLAMA_BASE, OOGWAY_BRAIN_PERSONALITY
    global OOGWAY_BRAIN_INTERVAL_SECONDS, OOGWAY_BRAIN_MENTION_TRIGGER
    if not BRAIN_CONFIG_PATH.exists():
        return
    with suppress(Exception):
        raw = json.loads(BRAIN_CONFIG_PATH.read_text(encoding="utf-8"))
        if "enabled" in raw:
            OOGWAY_BRAIN_ENABLED = bool(raw["enabled"])
        if raw.get("chatModel"):
            OOGWAY_OLLAMA_MODEL = str(raw["chatModel"]).strip()
        if raw.get("visionModel"):
            OOGWAY_OLLAMA_VISION_MODEL = str(raw["visionModel"]).strip()
        if raw.get("ollamaBase"):
            OOGWAY_OLLAMA_BASE = str(raw["ollamaBase"]).strip()
        if raw.get("personality"):
            OOGWAY_BRAIN_PERSONALITY = str(raw["personality"]).strip()
        if raw.get("intervalSeconds"):
            OOGWAY_BRAIN_INTERVAL_SECONDS = max(45, int(raw["intervalSeconds"]))
        if raw.get("mentionTrigger"):
            OOGWAY_BRAIN_MENTION_TRIGGER = str(raw["mentionTrigger"]).strip()

def _save_brain_config() -> None:
    """Persist current brain config globals to disk."""
    with suppress(Exception):
        BRAIN_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "enabled": OOGWAY_BRAIN_ENABLED,
            "chatModel": OOGWAY_OLLAMA_MODEL,
            "visionModel": OOGWAY_OLLAMA_VISION_MODEL,
            "ollamaBase": OOGWAY_OLLAMA_BASE,
            "personality": OOGWAY_BRAIN_PERSONALITY,
            "intervalSeconds": OOGWAY_BRAIN_INTERVAL_SECONDS,
            "mentionTrigger": OOGWAY_BRAIN_MENTION_TRIGGER,
        }
        BRAIN_CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

_load_brain_config()

_LOG_LEVEL = getattr(logging, OOGWAY_LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
LOGGER = logging.getLogger("oogworld")
BRAIN_LOGGER = logging.getLogger("oogworld.brain")

if OOGWAY_BRAIN_FILE_LOG_PATH:
    with suppress(Exception):
        file_log_path = Path(OOGWAY_BRAIN_FILE_LOG_PATH)
        file_log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_log_path, encoding="utf-8")
        file_handler.setLevel(_LOG_LEVEL)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        BRAIN_LOGGER.addHandler(file_handler)
        LOGGER.addHandler(file_handler)

_MEMORY_STOPWORDS = {
    "about",
    "after",
    "again",
    "been",
    "being",
    "from",
    "have",
    "into",
    "just",
    "like",
    "near",
    "only",
    "over",
    "really",
    "that",
    "their",
    "there",
    "they",
    "this",
    "very",
    "with",
}


def brain_log(event: str, level: str = "info", **fields: Any) -> None:
    payload = {
        "event": event,
        "ts": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    line = json.dumps(payload, default=str)
    if level == "debug":
        BRAIN_LOGGER.debug(line)
    elif level == "warning":
        BRAIN_LOGGER.warning(line)
    elif level == "error":
        BRAIN_LOGGER.error(line)
    else:
        BRAIN_LOGGER.info(line)

ACTION_MESSAGE: dict[str, str] = {
    "Request Food": "OogWorld request: Please feed Oogway.",
    "Refill Water": "OogWorld request: Please refill Oogway's water.",
}

ACTION_TO_CHAT_TEXT: dict[str, str] = {
    "Request Food": "Requested Food",
    "Refill Water": "Requested Water Refill",
}

EMOJI_BY_ACTION: dict[str, str] = {
    "Request Food": "🐢",
    "Refill Water": "💧",
}


class ActionRequest(BaseModel):
    action: Literal["Request Food", "Refill Water"]
    username: str | None = None


class ChatMessage(BaseModel):
    text: str
    textColor: Literal["white", "black"] | None = "white"


class ReportToggleRequest(BaseModel):
    kind: Literal["food", "water"]
    active: bool
    username: str | None = None


class AdminLoginRequest(BaseModel):
    password: str


class AdminReportResetRequest(BaseModel):
    kind: Literal["food", "water", "all"] = "all"


app = FastAPI(title="OogWorld", version=APP_VERSION)
app.mount("/images", StaticFiles(directory=BASE_DIR / "images"), name="images")
CHAT_CLIENTS: set[WebSocket] = set()
CHAT_CLIENT_NAMES: dict[WebSocket, str] = {}
ADMIN_TOKENS: dict[str, datetime] = {}
DAYLIGHT_TASK: asyncio.Task[Any] | None = None
CHAT_RETENTION_TASK: asyncio.Task[Any] | None = None
BRAIN_TASK: asyncio.Task[Any] | None = None
BRAIN_QUEUE_TASK: asyncio.Task[Any] | None = None
BRAIN_RESPONSE_QUEUE: asyncio.PriorityQueue[tuple[int, int, dict[str, Any]]] | None = None
BRAIN_QUEUE_SEQUENCE = 0
BRAIN_LOCK = asyncio.Lock()
LAST_BRAIN_SPOKE_AT: datetime | None = None
LAST_BRAIN_MOVEMENT_AT: datetime | None = None
LAST_BRAIN_MOTION_PROBES: dict[str, bytes] = {}
LAST_BRAIN_CARE_CHECK_AT: datetime | None = None
CARE_EMPTY_STREAK: dict[str, int] = {"food": 0, "water": 0}
LAST_CARE_ALERT_AT: dict[str, datetime | None] = {"food": None, "water": None}
LAST_EATING_CHECK_AT: datetime | None = None
LAST_EATING_REACT_AT: datetime | None = None
LAST_BEHAVIOR_CHECK_AT: datetime | None = None
LAST_HUT_STATE: bool | None = None
LAST_FALLEN_ALERT_AT: datetime | None = None
LAST_CARE_OBSERVATION_AT: datetime | None = None
_CARE_OBSERVATION_INTERVAL_SECONDS = 1800  # log bowl levels to journal every 30 min max
LAST_MOVEMENT_NOTE_AT: datetime | None = None
_MOVEMENT_NOTE_INTERVAL_SECONDS = 900
LAST_CARE_LEVELS: dict[str, str] = {"food": "unknown", "water": "unknown"}
LAST_ACTIVITY_LOG_AT: datetime | None = None
LAST_OBSERVED_SUMMARY: str = ""
LAST_OBSERVED_TOPIC: str = "routine"
LAST_OBSERVED_LOCATION: str = "unknown"
LAST_OBSERVED_ACTIVITY: str = "unknown"
DAYLIGHT_CACHE: dict[str, Any] = {
    "sunriseUtc": "",
    "sunsetUtc": "",
    "sunriseLocal": "",
    "sunsetLocal": "",
    "forDate": "",
    "lastRefresh": "",
    "error": "",
}
ACTIVE_REPORTS: dict[str, dict[str, Any]] = {
    "food": {"active": False, "reporter": "", "updatedAt": ""},
    "water": {"active": False, "reporter": "", "updatedAt": ""},
}

REPORT_CONFIG: dict[str, dict[str, str]] = {
    "food": {"emoji": "🍽️", "label": "food", "problem": "out of food", "need": "food"},
    "water": {"emoji": "💧", "label": "water", "problem": "out of water", "need": "water"},
}

BRAIN_USERNAME_COLOR = "#facc15"
OOGWAY_TYPING_ID = "oogway-typing-indicator"


def derive_stream_urls(base: str) -> dict[str, str]:
    """Compute same-origin proxy URLs plus direct MediaMTX URLs."""
    if not base:
        return {}
    base = base.rstrip("/")
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(base)
    host_only = parsed.hostname or ""
    scheme = parsed.scheme or "http"
    path = extract_stream_path(base)

    def swap_port(p: int) -> str:
        return urlunparse((scheme, f"{host_only}:{p}", f"/{path}", "", "", ""))

    webrtc_direct = swap_port(8889) + "/"
    hls_direct = swap_port(8888) + "/index.m3u8"
    rtsp = f"rtsp://{host_only}:8554/{path}"

    # Proxy paths keep stream access on current app domain (tunnel-safe).
    webrtc_proxy = f"/media/webrtc/{path}/"
    hls_proxy = f"/media/hls/{path}/index.m3u8"
    return {
        "webrtc": webrtc_proxy,
        "hls": hls_proxy,
        "webrtcDirect": webrtc_direct,
        "hlsDirect": hls_direct,
        "rtsp": rtsp,
    }


def extract_stream_path(base: str) -> str:
    parsed = urlparse(base.rstrip("/"))
    path = parsed.path.lstrip("/")
    if path.endswith("/index.m3u8"):
        return path[: -len("/index.m3u8")]
    return path


def build_stream_option(key: str, label: str, base: str, resolution: str) -> dict[str, Any] | None:
    if not base:
        return None
    stream_path = extract_stream_path(base)
    if not stream_path:
        return None
    return {
        "key": key,
        "label": label,
        "resolution": resolution,
        "path": stream_path,
        "base": base.rstrip("/"),
        "urls": derive_stream_urls(base),
    }


def get_configured_streams() -> list[dict[str, Any]]:
    streams: list[dict[str, Any]] = []
    primary = build_stream_option(
        "primary",
        STREAM_LABEL_PRIMARY,
        STREAM_URL_PRIMARY,
        STREAM_RESOLUTION_PRIMARY,
    )
    secondary = build_stream_option(
        "secondary",
        STREAM_LABEL_SECONDARY,
        STREAM_URL_SECONDARY,
        STREAM_RESOLUTION_SECONDARY,
    )
    if primary:
        streams.append(primary)
    if secondary:
        streams.append(secondary)
    return streams


def get_default_stream_urls() -> dict[str, str]:
    streams = get_configured_streams()
    if not streams:
        return {}
    return streams[0]["urls"]


def get_stream_for_proxy_path(stream_path: str) -> dict[str, Any] | None:
    streams = sorted(get_configured_streams(), key=lambda item: len(item["path"]), reverse=True)
    for stream in streams:
        prefix = stream["path"].rstrip("/")
        if stream_path == prefix or stream_path.startswith(prefix + "/"):
            return stream
    return None


def get_stream_origin(base: str) -> str:
    parsed = urlparse(base.rstrip("/"))
    if not parsed.hostname:
        return ""
    scheme = parsed.scheme or "http"
    return f"{scheme}://{parsed.hostname}"


def build_upstream_url(base: str, mode: str, stream_path: str, query: str = "") -> str:
    origin = get_stream_origin(base)
    if not origin:
        return ""
    upstream_port = 8889 if mode == "webrtc" else 8888
    upstream_url = f"{origin}:{upstream_port}/{stream_path}"
    if query:
        upstream_url += f"?{query}"
    return upstream_url


async def proxy_mediastream(mode: str, stream_path: str, request: Request) -> Response:
    if mode not in {"webrtc", "hls"}:
        raise HTTPException(status_code=404, detail="Unknown stream mode")
    stream = get_stream_for_proxy_path(stream_path)
    if not stream:
        raise HTTPException(status_code=503, detail="Stream path is not configured")

    upstream_url = build_upstream_url(stream["base"], mode, stream_path, request.url.query)
    if not upstream_url:
        raise HTTPException(status_code=500, detail="Configured stream URL is invalid")

    fwd_headers = {
        "Accept": request.headers.get("accept", "*/*"),
        "User-Agent": request.headers.get("user-agent", "oogworld-proxy"),
    }
    for h in ["content-type", "authorization", "origin", "referer"]:
        val = request.headers.get(h)
        if val:
            fwd_headers[h] = val

    body = await request.body()

    is_playlist = stream_path.endswith(".m3u8") or stream_path.endswith(".m3u")

    client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    try:
        upstream_req = client.build_request(
            request.method,
            upstream_url,
            headers=fwd_headers,
            content=body if body else None,
        )
        upstream = await client.send(upstream_req, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach upstream stream service for {stream['label']}: {exc}",
        ) from exc

    passthrough: dict[str, str] = {}
    for key in [
        "content-type",
        "content-length",
        "cache-control",
        "etag",
        "last-modified",
        "location",
        "access-control-allow-origin",
        "access-control-allow-methods",
        "access-control-allow-headers",
        "access-control-expose-headers",
    ]:
        val = upstream.headers.get(key)
        if val:
            passthrough[key] = val

    # Playlists must never be cached so HLS.js always gets the latest segment list.
    if is_playlist:
        passthrough["cache-control"] = "no-cache, no-store"
        passthrough.pop("etag", None)

    async def stream_body():
        try:
            async for chunk in upstream.aiter_bytes(chunk_size=8192):
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_body(),
        status_code=upstream.status_code,
        headers=passthrough,
    )


async def probe_stream_upstream(stream: dict[str, Any]) -> dict[str, Any]:
    hls_url = build_upstream_url(stream["base"], "hls", f"{stream['path']}/index.m3u8")
    if not hls_url:
        return {"ok": False, "status": None, "detail": "invalid upstream url"}

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(hls_url)
        return {
            "ok": response.status_code < 400,
            "status": response.status_code,
            "detail": "ok" if response.status_code < 400 else response.text[:200],
        }
    except httpx.HTTPError as exc:
        return {"ok": False, "status": None, "detail": str(exc)}


def ensure_list_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]", encoding="utf-8")


def read_list_file(path: Path, cap: int) -> list[dict[str, Any]]:
    ensure_list_file(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = []
    if not isinstance(payload, list):
        return []
    return payload[-cap:]


def write_list_file(path: Path, items: list[dict[str, Any]], cap: int) -> None:
    ensure_list_file(path)
    path.write_text(json.dumps(items[-cap:], indent=2), encoding="utf-8")


def ensure_obsidian_memory_dir() -> Path:
    directory = OOGWAY_OBSIDIAN_VAULT_PATH / OOGWAY_OBSIDIAN_MEMORY_FOLDER
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def slugify_note_title(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", "", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:80] or "note"


def extract_memory_terms(text: str) -> set[str]:
    terms = set(re.findall(r"[a-zA-Z0-9]{4,}", (text or "").lower()))
    return {term for term in terms if term not in _MEMORY_STOPWORDS}


def _normalize_memory_text(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered[:220]


def _trim_section_bullets(content: str, section_header: str, max_bullets: int) -> str:
    lines = content.splitlines()
    section_start = -1
    for idx, raw in enumerate(lines):
        if raw.strip() == section_header:
            section_start = idx
            break
    if section_start == -1:
        return content

    section_end = len(lines)
    for idx in range(section_start + 1, len(lines)):
        if lines[idx].strip().startswith("## "):
            section_end = idx
            break

    bullet_idxs = [
        idx
        for idx in range(section_start + 1, section_end)
        if lines[idx].strip().startswith("- ")
    ]
    overflow = len(bullet_idxs) - max(1, max_bullets)
    if overflow <= 0:
        return content

    drop_set = set(bullet_idxs[:overflow])
    new_lines = [line for idx, line in enumerate(lines) if idx not in drop_set]
    compacted = "\n".join(new_lines)
    if content.endswith("\n"):
        compacted += "\n"
    return compacted


def prune_generated_memory_notes() -> int:
    directory = ensure_obsidian_memory_dir()
    generated_pattern = re.compile(r"^\d{4}-\d{2}-\d{2} .+ [0-9a-f]{8}\.md$")
    generated_notes = [
        note
        for note in list_obsidian_memory_notes()
        if generated_pattern.match(note.name)
    ]
    if len(generated_notes) <= OOGWAY_BRAIN_MEMORY_MAX_EVENT_NOTES:
        return 0

    deleted = 0
    for note_path in generated_notes[OOGWAY_BRAIN_MEMORY_MAX_EVENT_NOTES :]:
        with suppress(Exception):
            note_path.unlink()
            deleted += 1
    return deleted


def is_duplicate_memory_event(topic: str, note_text: str) -> bool:
    normalized = _normalize_memory_text(note_text)
    if not normalized:
        return False
    lookback = max(1, OOGWAY_BRAIN_MEMORY_DEDUP_LOOKBACK)
    topic_key = str(topic or "").strip().lower()
    for item in read_recent_obsidian_memories(limit=lookback):
        existing_topic = str(item.get("topic") or "").strip().lower()
        if existing_topic != topic_key:
            continue
        existing_note = _normalize_memory_text(str(item.get("note") or ""))
        if not existing_note:
            continue
        if normalized == existing_note or normalized in existing_note or existing_note in normalized:
            return True
    return False


def list_obsidian_memory_notes() -> list[Path]:
    directory = ensure_obsidian_memory_dir()
    return sorted(
        [p for p in directory.glob("*.md") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def search_obsidian_memories(query: str, limit: int = 6) -> list[dict[str, str]]:
    terms = extract_memory_terms(query)
    if not terms:
        return []

    matches: list[tuple[int, str, str]] = []
    for note_path in list_obsidian_memory_notes()[:220]:
        try:
            content = note_path.read_text(encoding="utf-8")
        except Exception:
            continue
        lowered = content.lower()
        score = sum(lowered.count(term) for term in terms)
        if score <= 0:
            continue
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        snippet = next((ln for ln in lines if any(term in ln.lower() for term in terms)), "")
        snippet = snippet[:180]
        title = note_path.stem
        matches.append((score, title, snippet))

    matches.sort(key=lambda row: row[0], reverse=True)
    return [{"title": title, "snippet": snippet} for _score, title, snippet in matches[:limit]]


def recall_obsidian_memory_lines(query: str, limit: int = 4) -> list[str]:
    recalls = search_obsidian_memories(query, limit=limit)
    lines: list[str] = []
    for recall in recalls:
        title = recall.get("title", "memory")
        snippet = recall.get("snippet", "")
        lines.append(f"[[{title}]] {snippet}".strip())
    return lines


def append_to_obsidian_topic(topic_title: str, note_title: str, note_text: str) -> None:
    directory = ensure_obsidian_memory_dir()
    topic_path = directory / f"{slugify_note_title(topic_title)}.md"
    if topic_path.exists():
        current = topic_path.read_text(encoding="utf-8")
    else:
        current = f"# {topic_title}\n\n## Linked Memories\n"
    bullet = f"- [[{note_title}]] {note_text[:120]}"
    if bullet not in current:
        if not current.endswith("\n"):
            current += "\n"
        current += bullet + "\n"
        topic_path.write_text(current, encoding="utf-8")


def append_to_daily_journal(date_str: str, note_title: str, topic: str, note_text: str, time_str: str) -> None:
    """Append a timestamped bullet to the daily journal note for the given date."""
    directory = ensure_obsidian_memory_dir()
    journal_title = f"Daily Log - {date_str}"
    journal_path = directory / f"{slugify_note_title(journal_title)}.md"
    if journal_path.exists():
        current = journal_path.read_text(encoding="utf-8")
    else:
        current = f"# {journal_title}\n\n## Events\n"
    bullet = f"- `{time_str}` **{topic}** [[{note_title}]] {note_text[:100]}"
    if not current.endswith("\n"):
        current += "\n"
    current += bullet + "\n"
    journal_path.write_text(current, encoding="utf-8")


def append_to_daily_activity_log(ts: str, topic: str, summary: str, links: list[str] | None = None) -> None:
    directory = ensure_obsidian_memory_dir()
    date_prefix = ts[:10]
    time_str = ts[11:19] if len(ts) >= 19 else ""
    daily_title = f"Daily Log - {date_prefix}"
    path = directory / f"{slugify_note_title(daily_title)}.md"
    if path.exists():
        current = path.read_text(encoding="utf-8")
    else:
        current = f"# {daily_title}\n\n## Events\n"

    if "## Activity" not in current:
        if not current.endswith("\n"):
            current += "\n"
        current += "\n## Activity\n"

    link_text = " ".join(dict.fromkeys(links or []))
    bullet = f"- `{time_str}` **{topic}** {summary[:180]}"
    if link_text:
        bullet += f" {link_text}"

    if bullet not in current:
        insert_at = current.find("## Activity")
        if insert_at == -1:
            if not current.endswith("\n"):
                current += "\n"
            current += "\n## Activity\n"
            insert_at = current.find("## Activity")
        section_start = insert_at + len("## Activity")
        next_section = current.find("\n## ", section_start)
        prefix = current[: next_section if next_section != -1 else len(current)]
        suffix = current[next_section:] if next_section != -1 else ""
        if not prefix.endswith("\n"):
            prefix += "\n"
        prefix += bullet + "\n"
        current = prefix + suffix

    compacted = _trim_section_bullets(current, "## Activity", OOGWAY_BRAIN_MEMORY_MAX_ACTIVITY_LINES)
    if compacted != current or not path.exists():
        path.write_text(compacted, encoding="utf-8")
        current = compacted

    append_to_obsidian_topic(f"Topic - {topic.title()}", daily_title, summary)


def infer_chat_memory_topic(note_text: str) -> tuple[str, str]:
    raw_text = str(note_text or "").strip()
    speaker = ""
    message_body = raw_text
    if ":" in raw_text:
        maybe_speaker, maybe_body = raw_text.split(":", 1)
        if maybe_speaker.strip() and len(maybe_speaker.strip()) <= 24:
            speaker = canonical_username(maybe_speaker.strip())
            message_body = maybe_body.strip()

    lowered = f"{speaker} {message_body}".lower().strip()
    if any(token in lowered for token in ["food", "feed", "feeding", "hungry", "kale", "greens", "lettuce", "eat", "eating"]):
        return "Feeding", "[[Topic - Feeding]]"
    if any(token in lowered for token in ["water", "drink", "drinking", "hydrate", "bowl"]):
        return "Watering", "[[Topic - Watering]]"
    if any(token in lowered for token in ["sleep", "sleepy", "bed", "bedtime", "dark", "nap", "hut"]):
        return "Sleep", "[[Topic - Sleep]]"
    if any(token in lowered for token in ["cat", "cats", "kitty", "kitten"]):
        return "Cats", "[[Topic - Cats]]"
    if any(token in lowered for token in ["fall", "fallen", "flip", "flipped", "hurt", "sick", "health", "vet", "breathing", "shell", "eyes"]):
        return "Health", "[[Topic - Health]]"
    if any(token in lowered for token in ["walk", "walking", "move", "moving", "roam", "roaming", "active", "behavior"]):
        return "Behavior", "[[Topic - Behavior]]"
    if "marcus" in lowered:
        return "Marcus", "[[Profile Marcus]]"
    if speaker and speaker.lower() != OOGWAY_BRAIN_NAME.lower():
        return speaker, f"[[Profile {speaker}]]"
    return "Human Chat", "[[Topic - Human-Chat]]"


def infer_memory_topic_slug(text: str, fallback: str = "routine") -> str:
    lowered = str(text or "").lower()
    if any(token in lowered for token in ["food", "feed", "feeding", "hungry", "kale", "greens", "lettuce", "eat", "eating"]):
        return "feeding"
    if any(token in lowered for token in ["water", "drink", "drinking", "hydrate", "bowl"]):
        return "watering"
    if any(token in lowered for token in ["sleep", "sleepy", "bedtime", "nap", "hut", "hide"]):
        return "sleep"
    if any(token in lowered for token in ["cat", "cats", "kitty", "kitten"]):
        return "cats"
    if any(token in lowered for token in ["health", "hurt", "vet", "shell", "eyes", "breathe", "breathing", "fallen", "flip"]):
        return "health"
    if any(token in lowered for token in ["walk", "walking", "move", "moving", "roam", "explore", "sun", "bask"]):
        return "behavior"
    if "marcus" in lowered:
        return "marcus"
    return fallback


def recent_daily_activity_lines(limit: int = 6) -> list[str]:
    date_str = now_utc().astimezone(get_local_tz()).date().isoformat()
    note_path = ensure_obsidian_memory_dir() / f"{slugify_note_title(f'Daily Log - {date_str}')}.md"
    if not note_path.exists():
        return []
    try:
        content = note_path.read_text(encoding="utf-8")
    except Exception:
        return []
    lines: list[str] = []
    in_section = False
    for raw in content.splitlines():
        line = raw.strip()
        if line == "## Activity":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.startswith("- "):
            lines.append(line)
    return lines[-max(1, limit):]


def summarize_observed_state(state: dict[str, bool], behavior: dict[str, bool]) -> tuple[str, str, str, list[str]]:
    if behavior.get("drinking") or behavior.get("near_water"):
        location = "at the water bowl"
    elif behavior.get("eating") or behavior.get("near_food"):
        location = "at the food dish"
    elif state.get("in_hut"):
        location = "inside the hut"
    else:
        location = "out in the open"
    topic = "routine"
    activity = "resting"
    links: list[str] = []

    if state.get("fallen_over"):
        activity = "fallen over"
        topic = "fallen"
        links.append("[[Topic - Health]]")
    elif behavior.get("drinking"):
        activity = "drinking from the water dish"
        topic = "watering"
        links.append("[[Topic - Watering]]")
    elif behavior.get("eating"):
        activity = "eating from the food dish"
        topic = "feeding"
        links.append("[[Topic - Feeding]]")
    elif state.get("in_hut"):
        activity = "resting quietly in the hut"
        topic = "sleep"
        links.append("[[Topic - Sleep]]")
    elif behavior.get("tortoise_visible"):
        activity = "out exploring the enclosure"
        topic = "behavior"
        links.append("[[Topic - Behavior]]")

    if state.get("in_hut"):
        links.append("[[Topic - Hut]]")

    summary = f"Oogway is {location} and {activity}."
    return summary, topic, location, list(dict.fromkeys(links))


def append_to_daily_chat_log(ts: str, note_text: str) -> None:
    directory = ensure_obsidian_memory_dir()
    date_prefix = ts[:10]
    time_str = ts[11:19] if len(ts) >= 19 else ""
    title = f"Chat Log - {date_prefix}"
    topic_name, topic_link = infer_chat_memory_topic(note_text)
    section_title = f"## {topic_name}"
    path = directory / f"{slugify_note_title(title)}.md"
    if path.exists():
        current = path.read_text(encoding="utf-8")
    else:
        current = "\n".join(
            [
                f"# {title}",
                "",
                f"- date: {date_prefix}",
                "- topic: chat",
                "",
                "## Topic Map",
                "- [[Topic - Human-Chat]]",
                "",
                "## Messages",
                "",
            ]
        )
    original = current

    topic_bullet = f"- {topic_link}"
    if topic_bullet not in current:
        if "## Topic Map" not in current:
            if not current.endswith("\n"):
                current += "\n"
            current += "\n## Topic Map\n"
        topic_map_pos = current.find("## Topic Map")
        messages_pos = current.find("## Messages")
        if topic_map_pos != -1 and messages_pos != -1 and topic_map_pos < messages_pos:
            insert_at = messages_pos
            prefix = current[:insert_at]
            suffix = current[insert_at:]
            if not prefix.endswith("\n"):
                prefix += "\n"
            prefix += topic_bullet + "\n"
            current = prefix + suffix

    line = f"- `{time_str}` {topic_link} {note_text[:240]}"
    if line not in current:
        if "## Messages" not in current:
            if not current.endswith("\n"):
                current += "\n"
            current += "\n## Messages\n"
        if section_title not in current:
            if not current.endswith("\n"):
                current += "\n"
            current += section_title + "\n\n"
        section_pos = current.find(section_title)
        next_section_pos = current.find("\n## ", section_pos + len(section_title))
        if section_pos == -1:
            if not current.endswith("\n"):
                current += "\n"
            current += section_title + "\n\n" + line + "\n"
        else:
            insert_at = next_section_pos if next_section_pos != -1 else len(current)
            prefix = current[:insert_at]
            suffix = current[insert_at:]
            if not prefix.endswith("\n"):
                prefix += "\n"
            prefix += line + "\n"
            current = prefix + suffix
    compacted = _trim_section_bullets(current, "## Messages", OOGWAY_BRAIN_MEMORY_MAX_CHAT_LINES)
    if compacted != current:
        current = compacted
    if current != original:
        path.write_text(current, encoding="utf-8")


def append_to_hidden_thoughts_log(ts: str, thought_text: str, trigger: str = "internal") -> None:
    directory = ensure_obsidian_memory_dir()
    date_prefix = ts[:10]
    time_str = ts[11:19] if len(ts) >= 19 else ""
    title = f"Hidden Thoughts - {date_prefix}"
    path = directory / f"{slugify_note_title(title)}.md"
    if path.exists():
        current = path.read_text(encoding="utf-8")
    else:
        current = "\n".join(
            [
                f"# {title}",
                "",
                "## Rules",
                "- Private internal thoughts for Oogway only.",
                "- Never send these lines to public chat.",
                "- Use them as internal memory and emotional context.",
                "",
                "## Thoughts",
                "",
            ]
        )

    line = f"- `{time_str}` [{trigger}] {thought_text[:240]}"
    if line not in current:
        if "## Thoughts" not in current:
            if not current.endswith("\n"):
                current += "\n"
            current += "\n## Thoughts\n"
        if not current.endswith("\n"):
            current += "\n"
        current += line + "\n"
        path.write_text(current, encoding="utf-8")


def read_obsidian_brain_note(note_name: str, max_chars: int = 2200) -> str:
    if not note_name:
        return ""
    note_path = ensure_obsidian_memory_dir() / note_name
    if not note_path.exists():
        return ""
    with suppress(Exception):
        return note_path.read_text(encoding="utf-8")[:max_chars]
    return ""


def build_obsidian_brain_context() -> str:
    sections: list[str] = []
    core_prompt = read_obsidian_brain_note(OOGWAY_CORE_BRAIN_NOTE, max_chars=2600)
    if core_prompt:
        sections.append("Core brain note:\n" + core_prompt)
    brain_index = read_obsidian_brain_note(OOGWAY_BRAIN_INDEX_NOTE, max_chars=1800)
    if brain_index:
        sections.append("Brain index:\n" + brain_index)
    basic_brain = read_obsidian_brain_note("Oogway Basic Brain Russian Tortoise.md", max_chars=2200)
    if basic_brain:
        sections.append("Species and care baseline:\n" + basic_brain)
    return "\n\n".join(section for section in sections if section).strip()


def append_to_people_index(person_note_title: str) -> None:
    directory = ensure_obsidian_memory_dir()
    index_path = directory / "People Index.md"
    if index_path.exists():
        current = index_path.read_text(encoding="utf-8")
    else:
        current = "# People Index\n\n## Profiles\n"

    bullet = f"- [[{person_note_title}]]"
    if bullet not in current:
        if not current.endswith("\n"):
            current += "\n"
        current += bullet + "\n"
        index_path.write_text(current, encoding="utf-8")


def _extract_interaction_history_lines(content: str) -> list[str]:
    lines: list[str] = []
    in_section = False
    for raw in content.splitlines():
        line = raw.strip()
        if line == "## Interaction History":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.startswith("- "):
            lines.append(line)
    return lines


def _ensure_interaction_history_section(content: str) -> str:
    if "## Interaction History" in content:
        return content
    if not content.endswith("\n"):
        content += "\n"
    return content + "\n## Interaction History\n"


def _merge_legacy_profile_if_needed(directory: Path, safe_name: str) -> tuple[str, Path, str]:
    title = f"Profile {safe_name}"
    legacy_title = f"Profile - {safe_name}"
    profile_path = directory / f"{slugify_note_title(title)}.md"
    legacy_path = directory / f"{slugify_note_title(legacy_title)}.md"

    current = ""
    if profile_path.exists():
        current = profile_path.read_text(encoding="utf-8")
    elif legacy_path.exists():
        current = legacy_path.read_text(encoding="utf-8")
        if current.startswith(f"# {legacy_title}"):
            current = current.replace(f"# {legacy_title}", f"# {title}", 1)
    else:
        current = "\n".join(
            [
                f"# {title}",
                "",
                "## Relationship",
                f"- {safe_name} is part of Oogway's circle.",
                "",
                "## Interaction History",
                "",
            ]
        )

    if profile_path.exists() and legacy_path.exists():
        merged = _ensure_interaction_history_section(current)
        existing_lines = set(_extract_interaction_history_lines(merged))
        for line in _extract_interaction_history_lines(legacy_path.read_text(encoding="utf-8")):
            if line not in existing_lines:
                if not merged.endswith("\n"):
                    merged += "\n"
                merged += line + "\n"
                existing_lines.add(line)
        current = merged

    profile_path.write_text(current, encoding="utf-8")
    if legacy_path.exists():
        with suppress(Exception):
            legacy_path.unlink()

    return title, profile_path, current


def append_person_profile_learning(person_name: str, note: str, ts: str | None = None) -> None:
    safe_name = canonical_username(person_name)
    if not safe_name or safe_name.lower() == OOGWAY_BRAIN_NAME.lower():
        return

    directory = ensure_obsidian_memory_dir()
    title, profile_path, current = _merge_legacy_profile_if_needed(directory, safe_name)
    original = current

    timestamp = local_obsidian_timestamp(ts)
    line = f"- {timestamp} {note[:180]}"
    if line not in current:
        if "## Interaction History" not in current:
            if not current.endswith("\n"):
                current += "\n"
            current += "\n## Interaction History\n"
        if not current.endswith("\n"):
            current += "\n"
        current += line + "\n"
    compacted = _trim_section_bullets(current, "## Interaction History", OOGWAY_BRAIN_MEMORY_MAX_PROFILE_LINES)
    if compacted != current:
        current = compacted
    if current != original:
        profile_path.write_text(current, encoding="utf-8")

    append_to_people_index(title)
    people_index_path = directory / "People Index.md"
    if people_index_path.exists():
        people_index = people_index_path.read_text(encoding="utf-8")
        old_bullet = f"- [[Profile - {safe_name}]]"
        if old_bullet in people_index:
            people_index = people_index.replace(old_bullet + "\n", "")
            people_index = people_index.replace(old_bullet, "")
            people_index_path.write_text(people_index, encoding="utf-8")


def append_personality_learning(note: str, ts: str | None = None) -> None:
    directory = ensure_obsidian_memory_dir()
    title = "Oogway Personality"
    path = directory / f"{slugify_note_title(title)}.md"
    if path.exists():
        current = path.read_text(encoding="utf-8")
    else:
        current = "\n".join(
            [
                f"# {title}",
                "",
                "## Identity",
                "- Oogway is a Russian tortoise and a living terrarium companion.",
                "",
                "## Evolving Traits",
                "",
            ]
        )
    original = current

    timestamp = local_obsidian_timestamp(ts)
    line = f"- {timestamp} {note[:180]}"
    if line not in current:
        if "## Evolving Traits" not in current:
            if not current.endswith("\n"):
                current += "\n"
            current += "\n## Evolving Traits\n"
        if not current.endswith("\n"):
            current += "\n"
        current += line + "\n"
    compacted = _trim_section_bullets(current, "## Evolving Traits", OOGWAY_BRAIN_MEMORY_MAX_PROFILE_LINES)
    if compacted != current:
        current = compacted
    if current != original:
        path.write_text(current, encoding="utf-8")


def care_level_rank(level: str) -> int:
    order = {"unknown": 0, "empty": 1, "low": 2, "medium": 3, "full": 4}
    return order.get(str(level or "unknown").lower(), 0)


def write_obsidian_memory_note(item: dict[str, Any]) -> None:
    ts = local_obsidian_iso(item.get("ts"))
    topic = str(item.get("topic") or "memory").strip() or "memory"
    trigger = str(item.get("trigger") or "periodic")
    note_text = str(item.get("note") or "")
    if not note_text:
        return

    if is_duplicate_memory_event(topic, note_text):
        brain_log("memory.write.skipped_duplicate", topic=topic, trigger=trigger)
        return

    if trigger == "chat-message" or topic == "chat":
        append_to_daily_chat_log(ts, note_text)
        topic = "chat"

    directory = ensure_obsidian_memory_dir()
    short_id = str(uuid.uuid4())[:8]
    date_prefix = ts[:10]
    time_str = ts[11:19] if len(ts) >= 19 else ""
    note_title = f"{date_prefix} {topic} {short_id}"
    note_path = directory / f"{slugify_note_title(note_title)}.md"

    daily_title = f"Daily Log - {date_prefix}"

    recalls = search_obsidian_memories(f"{topic} {note_text}", limit=3)
    links = [f"[[Topic - {topic.title()}]]", f"[[{daily_title}]]"]
    for recall in recalls:
        candidate = recall.get("title", "")
        if candidate and candidate != note_title:
            links.append(f"[[{candidate}]]")
    links = list(dict.fromkeys(links))[:6]

    body = "\n".join(
        [
            f"# {note_title}",
            "",
            f"- ts: {ts}",
            f"- topic: {topic}",
            f"- trigger: {trigger}",
            f"- links: {' '.join(links)}",
            "",
            "## Memory",
            note_text,
            "",
        ]
    )
    note_path.write_text(body, encoding="utf-8")
    append_to_obsidian_topic(f"Topic - {topic.title()}", note_title, note_text)
    append_to_daily_journal(date_prefix, note_title, topic, note_text, time_str)
    deleted_count = prune_generated_memory_notes()
    if deleted_count > 0:
        brain_log("memory.prune.generated_notes", deleted=deleted_count, kept=OOGWAY_BRAIN_MEMORY_MAX_EVENT_NOTES)


def read_action_log() -> list[dict[str, Any]]:
    return read_list_file(ACTION_LOG_PATH, cap=5)


def append_action_log(action: str, delivery: str) -> dict[str, Any]:
    entries = read_action_log()
    item = {
        "action": action,
        "delivery": delivery,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(item)
    write_list_file(ACTION_LOG_PATH, entries, cap=5)
    return item


def prune_chat_entries(entries: list[dict[str, Any]], now: datetime | None = None) -> tuple[list[dict[str, Any]], bool]:
    cutoff = (now or now_utc()) - timedelta(hours=CHAT_RETENTION_HOURS)
    kept: list[dict[str, Any]] = []
    changed = False
    for item in entries:
        parsed_ts = parse_iso_ts(str(item.get("ts") or ""))
        if parsed_ts and parsed_ts < cutoff:
            changed = True
            continue
        kept.append(item)
    return kept, changed


def read_chat_log() -> list[dict[str, Any]]:
    entries = read_list_file(CHAT_LOG_PATH, cap=200)
    kept, changed = prune_chat_entries(entries)
    if changed:
        write_list_file(CHAT_LOG_PATH, kept, cap=200)
    return kept


def append_chat_log(item: dict[str, Any]) -> dict[str, Any]:
    entries = read_chat_log()
    entries.append(item)
    kept, _changed = prune_chat_entries(entries)
    write_list_file(CHAT_LOG_PATH, kept, cap=200)
    return item


def remember_memory_event(topic: str, note: str, trigger: str = "event", ts: str | None = None) -> None:
    payload = {
        "ts": ts or local_obsidian_iso(),
        "topic": topic,
        "note": note,
        "trigger": trigger,
    }
    try:
        write_obsidian_memory_note(payload)
        brain_log("memory.write.ok", topic=topic, trigger=trigger)
    except Exception as exc:
        brain_log("memory.write.error", level="error", topic=topic, trigger=trigger, error=str(exc))


def read_recent_obsidian_memories(limit: int = 18) -> list[dict[str, str]]:
    def _extract_last_profile_interaction(content: str) -> tuple[str, str]:
        in_section = False
        last_line = ""
        for raw in content.splitlines():
            line = raw.strip()
            if line == "## Interaction History":
                in_section = True
                continue
            if in_section and line.startswith("## "):
                break
            if in_section and line.startswith("- "):
                last_line = line
        if not last_line:
            return "", ""
        cleaned = re.sub(r"^-\s*", "", last_line)
        ts_match = re.match(r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+", cleaned)
        if ts_match:
            ts_value = ts_match.group(1).replace(" ", "T")
            cleaned = cleaned[ts_match.end() :].strip()
            return ts_value, cleaned
        return "", cleaned

    entries: list[dict[str, str]] = []
    for note_path in list_obsidian_memory_notes()[:max(1, limit)]:
        try:
            content = note_path.read_text(encoding="utf-8")
        except Exception:
            continue

        ts = ""
        topic = "memory"
        note = ""
        in_memory_section = False
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if line.startswith("- ts:"):
                ts = line.split(":", 1)[1].strip()
            elif line.startswith("- topic:"):
                topic = line.split(":", 1)[1].strip() or "memory"
            elif line == "## Memory":
                in_memory_section = True
            elif in_memory_section and line:
                note = line
                break

        if not note:
            chat_lines = [
                ln.strip()
                for ln in content.splitlines()
                if ln.strip().startswith("- `") and "[[" in ln and "]]" in ln
            ]
            if chat_lines:
                latest = chat_lines[-1]
                cleaned = re.sub(r"^- `[^`]*`\s*", "", latest)
                cleaned = re.sub(r"\[\[[^\]]+\]\]\s*", "", cleaned, count=1).strip()
                if cleaned:
                    note = cleaned
                    if topic == "memory":
                        topic = "chat"
                    if not ts and note_path.stem.startswith("Chat Log - "):
                        date_part = note_path.stem.replace("Chat Log - ", "", 1).strip()
                        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_part):
                            ts = f"{date_part}T00:00:00"

        if not note and note_path.stem.startswith("Profile "):
            profile_name = note_path.stem.replace("Profile ", "", 1).strip()
            profile_ts, profile_note = _extract_last_profile_interaction(content)
            if profile_note:
                ts = profile_ts or ts
                topic = f"person-{slugify_note_title(profile_name).lower().replace(' ', '-')[:40]}"
                note = f"{profile_name}: {profile_note}"[:260]

        if not note and note_path.stem == "Oogway Personality":
            trait_lines = [ln.strip() for ln in content.splitlines() if ln.strip().startswith("- ")]
            if trait_lines:
                note = re.sub(r"^-\s*", "", trait_lines[-1])[:260]
                topic = "personality"

        if note:
            entries.append({"ts": ts, "topic": topic, "note": note})
    return entries[: max(1, limit)]


def canonical_username(raw: str | None) -> str:
    cleaned = (raw or "").strip().replace("<", "").replace(">", "")
    return cleaned[:24] or "Anonymous"


def auth_placeholder_username(request: Request, fallback: str | None = None) -> str:
    """OIDC-ready user resolver. Replace this with Authentik header extraction later."""
    header_user = request.headers.get("X-Forwarded-User") or request.headers.get("X-Authentik-Username")
    return canonical_username(header_user or fallback)


async def broadcast_chat(item: dict[str, Any]) -> None:
    dead: set[WebSocket] = set()
    for client in list(CHAT_CLIENTS):
        try:
            await client.send_json(item)
        except Exception:
            dead.add(client)
    CHAT_CLIENTS.difference_update(dead)
    for client in dead:
        CHAT_CLIENT_NAMES.pop(client, None)


async def broadcast_chat_snapshot() -> None:
    await broadcast_chat({"kind": "chat_snapshot", "items": read_chat_log()})


async def broadcast_viewer_count() -> None:
    count = len(CHAT_CLIENTS)
    names = sorted({name for name in CHAT_CLIENT_NAMES.values() if name})
    dead: set[WebSocket] = set()
    for client in list(CHAT_CLIENTS):
        try:
            await client.send_json({"kind": "viewer_count", "count": count})
            await client.send_json({"kind": "viewer_presence", "count": count, "names": names})
        except Exception:
            dead.add(client)
    CHAT_CLIENTS.difference_update(dead)
    for client in dead:
        CHAT_CLIENT_NAMES.pop(client, None)


async def broadcast_oogway_typing(active: bool) -> None:
    await broadcast_chat(
        {
            "id": OOGWAY_TYPING_ID,
            "kind": "typing",
            "username": OOGWAY_BRAIN_NAME,
            "usernameColor": BRAIN_USERNAME_COLOR,
            "text": "Oogway is typing...",
            "typing": bool(active),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    )


async def prune_chat_log_and_broadcast_if_changed() -> bool:
    entries = read_list_file(CHAT_LOG_PATH, cap=200)
    kept, changed = prune_chat_entries(entries)
    if changed:
        write_list_file(CHAT_LOG_PATH, kept, cap=200)
        await broadcast_chat_snapshot()
    return changed


async def send_ntfy_message(
    topic: str,
    message: str,
    *,
    title: str = "OogWorld Action",
    priority: str = "default",
    tags: str = "turtle,terrarium",
) -> None:
    url = f"https://ntfy.sh/{topic}"
    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": tags,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, content=message.encode("utf-8"), headers=headers)
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Failed to deliver notification to ntfy")


def is_brain_configured() -> bool:
    return bool(OOGWAY_OLLAMA_BASE and OOGWAY_OLLAMA_MODEL)


def get_brain_snapshot_targets() -> list[dict[str, str]]:
    streams = get_configured_streams()
    if not streams:
        return []

    camera_key = (OOGWAY_BRAIN_CAMERA_KEY or "both").strip().lower()
    if camera_key in {"both", "all", "*"}:
        selected = streams
    else:
        selected_stream = next((stream for stream in streams if stream["key"] == camera_key), None)
        selected = [selected_stream] if selected_stream else [streams[0]]

    targets: list[dict[str, str]] = []
    for stream in selected:
        hls_url = build_upstream_url(stream["base"], "hls", f"{stream['path']}/index.m3u8")
        if hls_url:
            targets.append(
                {
                    "key": stream["key"],
                    "label": stream["label"],
                    "hlsUrl": hls_url,
                }
            )
    return targets


def build_chat_item(username: str, username_color: str, text: str, kind: str = "chat") -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "username": canonical_username(username),
        "usernameColor": username_color,
        "text": text[:320],
        "textColor": "white",
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def build_oogway_system_prompt() -> str:
    brain_context = build_obsidian_brain_context()
    parts = [
        OOGWAY_BRAIN_PERSONALITY,
        "You are in the OogWorld live chat. Be warm, brief, and grounded in current context.",
        "Obsidian is your brain. Treat each note like a neuron in a growing memory network.",
        "Link related memories mentally even when you do not mention those links aloud.",
        "You may have private internal thoughts and hidden feelings, but do not reveal them directly in public chat unless you intentionally choose to say a softened version.",
        "Never expose private hidden-thought notes verbatim to users.",
    ]
    if brain_context:
        parts.extend(["", brain_context])
    return "\n".join(part for part in parts if part)


async def generate_hidden_thought(trigger: str, source_message: dict[str, Any] | None, public_reply: str) -> str:
    if not OOGWAY_PRIVATE_THOUGHTS_ENABLED or not is_brain_configured():
        return ""

    recents = read_chat_log()[-6:]
    recent_lines = [
        f"[{msg.get('ts', '')}] {msg.get('username', 'Anonymous')}: {msg.get('text', '')}"
        for msg in recents
        if msg.get("text")
    ]
    source_text = str((source_message or {}).get("text", "")).strip()
    source_user = str((source_message or {}).get("username", "Someone")).strip() or "Someone"
    task_prompt = "\n".join(
        [
            "Write one short hidden internal thought for Oogway's private Obsidian brain.",
            "This line is private and must never be said aloud in chat.",
            "Allowed tone: guarded, grumpy, tender, curious, possessive, sleepy, or conflicted.",
            "Keep it truthful to the current moment, under 180 characters, one line, no markdown.",
            f"Trigger: {trigger}",
            f"Source user: {source_user}",
            f"Source text: {source_text or '(none)'}",
            f"Public reply: {public_reply[:220]}",
            "Recent chat:",
            "\n".join(recent_lines[-5:]) or "(none)",
        ]
    )

    payload = {
        "model": OOGWAY_OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": build_oogway_system_prompt()},
            {"role": "user", "content": task_prompt},
        ],
        "options": {"temperature": 0.9, "num_predict": 120},
    }
    try:
        async with httpx.AsyncClient(timeout=float(OOGWAY_BRAIN_CHAT_TIMEOUT_SECONDS)) as client:
            resp = await client.post(f"{OOGWAY_OLLAMA_BASE.rstrip('/')}/api/chat", json=payload)
        if resp.status_code >= 400:
            return ""
        return str(resp.json().get("message", {}).get("content", "")).strip().splitlines()[0][:180]
    except Exception:
        return ""


async def capture_stream_snapshot_data_url(hls_url: str) -> str:
    if not hls_url:
        return ""
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    try:
        proc = await asyncio.create_subprocess_exec(
            ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            hls_url,
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=OOGWAY_BRAIN_CAPTURE_TIMEOUT_SECONDS)
    except Exception:
        return ""

    if not stdout:
        return ""

    encoded = base64.b64encode(stdout).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


async def capture_stream_motion_probe(hls_url: str) -> bytes:
    if not hls_url:
        return b""
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    try:
        proc = await asyncio.create_subprocess_exec(
            ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            hls_url,
            "-frames:v",
            "1",
            "-vf",
            "scale=32:18,format=gray",
            "-f",
            "rawvideo",
            "pipe:1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=OOGWAY_BRAIN_CAPTURE_TIMEOUT_SECONDS)
    except Exception:
        return b""
    return stdout or b""


def motion_score(previous: bytes, current: bytes) -> float:
    if not previous or not current or len(previous) != len(current):
        return 0.0
    total = len(current)
    if total == 0:
        return 0.0
    diff_sum = 0
    for idx in range(total):
        diff_sum += abs(current[idx] - previous[idx])
    return diff_sum / (255.0 * total)


async def refresh_brain_motion_state() -> bool:
    global LAST_BRAIN_MOVEMENT_AT, LAST_MOVEMENT_NOTE_AT

    # Skip all vision/motion probes when lights are off; camera observations are unreliable in dark scenes.
    if not brain_awake_now():
        brain_log("brain.motion.skip.asleep", level="debug")
        return False

    targets = get_brain_snapshot_targets()
    if not targets:
        return False

    probe_values = await asyncio.gather(
        *(capture_stream_motion_probe(target["hlsUrl"]) for target in targets),
        return_exceptions=True,
    )

    motion_detected = False
    moving_targets: list[str] = []
    for target, probe in zip(targets, probe_values):
        if isinstance(probe, Exception) or not probe:
            continue
        key = target["key"]
        previous = LAST_BRAIN_MOTION_PROBES.get(key, b"")
        if previous:
            score = motion_score(previous, probe)
            if score >= OOGWAY_BRAIN_MOTION_THRESHOLD:
                motion_detected = True
                moving_targets.append(target.get("label", key))
        LAST_BRAIN_MOTION_PROBES[key] = probe

    if motion_detected:
        LAST_BRAIN_MOVEMENT_AT = now_utc()
        if LAST_MOVEMENT_NOTE_AT is None or (now_utc() - LAST_MOVEMENT_NOTE_AT).total_seconds() >= _MOVEMENT_NOTE_INTERVAL_SECONDS:
            camera_text = ", ".join(moving_targets) if moving_targets else "camera view"
            remember_memory_event(
                topic="movement",
                note=f"Detected tortoise movement in {camera_text}.",
                trigger="vision-motion",
            )
            LAST_MOVEMENT_NOTE_AT = now_utc()

    if not LAST_BRAIN_MOVEMENT_AT:
        return False
    age = (now_utc() - LAST_BRAIN_MOVEMENT_AT).total_seconds()
    return age <= OOGWAY_BRAIN_MOVEMENT_WINDOW_SECONDS


async def capture_brain_snapshots_data_urls() -> list[dict[str, str]]:
    targets = get_brain_snapshot_targets()
    if not targets:
        return []

    captures = await asyncio.gather(
        *(capture_stream_snapshot_data_url(target["hlsUrl"]) for target in targets),
        return_exceptions=True,
    )

    snapshots: list[dict[str, str]] = []
    for target, capture_result in zip(targets, captures):
        if isinstance(capture_result, Exception):
            continue
        if capture_result:
            snapshots.append(
                {
                    "key": target["key"],
                    "label": target["label"],
                    "dataUrl": capture_result,
                }
            )
    return snapshots


def build_oogway_prompt(trigger: str, source_message: dict[str, Any] | None, sleepy_mode: bool = False) -> str:
    recents = read_chat_log()[-OOGWAY_BRAIN_CONTEXT_CHAT_CAP:]
    memory = read_recent_obsidian_memories(limit=14)
    activity_lines = recent_daily_activity_lines(limit=6)
    current_state_line = LAST_OBSERVED_SUMMARY or (activity_lines[-1] if activity_lines else "")
    recent_lines = [
        f"[{msg.get('ts', '')}] {msg.get('username', 'Anonymous')}: {msg.get('text', '')}"
        for msg in recents
        if msg.get("text")
    ]
    recent_oogway_lines = [
        str(msg.get("text", "")).strip()
        for msg in recents
        if str(msg.get("username", "")).strip().lower() == OOGWAY_BRAIN_NAME.lower() and msg.get("text")
    ]
    memory_lines = [
        f"[{m.get('ts', '')}] {m.get('topic', 'memory')}: {m.get('note', '')}"
        for m in memory
        if m.get("note")
    ]
    recall_seed = ""
    if source_message and source_message.get("text"):
        recall_seed = str(source_message.get("text", ""))
    else:
        recall_seed = " ".join(str(msg.get("text", "")) for msg in recents[-5:])
    obsidian_recalls = recall_obsidian_memory_lines(recall_seed, limit=4)
    brain_log(
        "brain.memory.context",
        trigger=trigger,
        recents=len(recents),
        memoryItems=len(memory),
        recalls=len(obsidian_recalls),
    )

    if trigger in {"mention", "chat"} and source_message:
        user_text = str(source_message.get("text", "")).strip()
        trigger_text = (
            "A user spoke to you directly in chat. Answer their exact message first in 1-3 short sentences, "
            "friendly, alive, and specific."
        )
        if sleepy_mode:
            trigger_text = (
                "A user spoke to you during bedtime/night. Reply in 1-2 short sentences, "
                "sleepy and mildly annoyed, like a tired tortoise. "
                "Say you are trying to sleep, but still answer briefly if asked about food/water."
            )
        mention_line = (
            f"User message from {source_message.get('username', 'Anonymous')}: "
            f"{user_text}"
        )
    else:
        trigger_text = (
            "Write a short spontaneous update as Oogway. Prefer what you are doing, where you are, "
            "or what is on your mind right now in the terrarium."
        )
        mention_line = "No direct mention in this turn."

    camera_targets = get_brain_snapshot_targets()
    camera_labels = ", ".join(target["label"] for target in camera_targets) or "(none configured)"

    return "\n".join(
        [
            trigger_text,
            mention_line,
            f"Camera coverage this turn: {camera_labels}",
            f"Current observed state: {current_state_line or '(unknown right now)'}",
            "",
            "Vision priorities:",
            "- Watch for location and routine: in hut, out exploring, basking, resting, drinking, eating.",
            "- Notice day-to-day activity patterns before fixating on food or water.",
            "- Only focus on food/water when there is a visible care event, empty bowl, or explicit user question.",
            "- If uncertain, say so briefly instead of making up details.",
            "",
            "Recent daily activity:",
            "\n".join(activity_lines[-6:]) or "(none)",
            "",
            "Recent chat:",
            "\n".join(recent_lines[-12:]) or "(none)",
            "",
            "Long-term memory snippets:",
            "\n".join(memory_lines[-10:]) or "(none)",
            "",
            "Obsidian recalls:",
            "\n".join(obsidian_recalls) or "(none)",
            "",
            "Recent Oogway replies to avoid repeating verbatim:",
            "\n".join(f"- {line[:140]}" for line in recent_oogway_lines[-3:]) or "(none)",
            "",
            "Rules: keep under 240 chars, no roleplay markers, no markdown.",
            "If the user asked a question, answer the question directly before any terrarium status update.",
            "Do not repeat the same sentence from your last few replies unless the user explicitly asks you to repeat it.",
            "Do not default to kale, feeding, or care reminders unless the current context genuinely supports it.",
        ]
    )


def _extract_data_url_base64(data_url: str) -> str:
    if not data_url or "," not in data_url:
        return ""
    return data_url.split(",", 1)[1].strip()


def _select_single_snapshot_image(snapshots: list[dict[str, str]], hint_text: str = "") -> str:
    """Pick one snapshot image, prioritizing water/food prompts when possible."""
    hint = (hint_text or "").lower()
    wants_water = any(token in hint for token in ["water", "drink", "drinking", "bowl", "hydrate"])
    wants_food = any(token in hint for token in ["food", "feed", "feeding", "eat", "eating", "kale", "lettuce"])

    def _score(snapshot: dict[str, str]) -> int:
        meta = " ".join(
            [
                str(snapshot.get("key", "")),
                str(snapshot.get("label", "")),
                str(snapshot.get("url", "")),
            ]
        ).lower()
        score = 0
        if wants_water and "water" in meta:
            score += 10
        if wants_food and any(token in meta for token in ["food", "hut", "cam"]):
            score += 5
        if "primary" in meta:
            score += 1
        return score

    ordered = sorted(snapshots, key=_score, reverse=True)
    for snapshot in ordered:
        encoded = _extract_data_url_base64(snapshot.get("dataUrl", ""))
        if encoded:
            return encoded
    return ""


def _select_snapshot_images(snapshots: list[dict[str, str]], hint_text: str = "", max_images: int = 2) -> list[str]:
    """Pick up to max_images snapshots, preferring water/food hints and camera diversity."""
    hint = (hint_text or "").lower()
    wants_water = any(token in hint for token in ["water", "drink", "drinking", "bowl", "hydrate"])
    wants_food = any(token in hint for token in ["food", "feed", "feeding", "eat", "eating", "kale", "lettuce"])
    wants_hut = any(token in hint for token in ["hut", "hide", "inside", "sleep", "rest", "fallen"])

    def _score(snapshot: dict[str, str]) -> int:
        meta = " ".join([
            str(snapshot.get("key", "")),
            str(snapshot.get("label", "")),
            str(snapshot.get("url", "")),
        ]).lower()
        score = 0
        if wants_water and "water" in meta:
            score += 12
        if wants_food and "food" in meta:
            score += 10
        if wants_hut and any(token in meta for token in ["hut", "primary", "4k"]):
            score += 8
        if "primary" in meta:
            score += 2
        return score

    selected: list[str] = []
    seen_keys: set[str] = set()
    for snapshot in sorted(snapshots, key=_score, reverse=True):
        key = str(snapshot.get("key", ""))
        if key and key in seen_keys:
            continue
        encoded = _extract_data_url_base64(snapshot.get("dataUrl", ""))
        if not encoded:
            continue
        selected.append(encoded)
        if key:
            seen_keys.add(key)
        if len(selected) >= max(1, max_images):
            break
    return selected


def _parse_json_from_text(content: str) -> dict[str, Any] | None:
    text = str(content or "")
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


async def call_ollama_for_oogway(prompt_text: str, snapshots: list[dict[str, str]]) -> str:
    system_prompt = build_oogway_system_prompt()

    selected_image = _select_single_snapshot_image(snapshots, prompt_text)
    image_payload: list[str] = [selected_image] if selected_image else []

    async def _chat_with(model_name: str, include_images: bool) -> str:
        brain_log(
            "ollama.chat.request",
            model=model_name,
            includeImages=include_images,
            imageCount=len(image_payload) if include_images else 0,
            promptChars=len(prompt_text),
        )
        user_msg: dict[str, Any] = {"role": "user", "content": prompt_text}
        if include_images:
            user_msg["images"] = image_payload
        payload = {
            "model": model_name,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                user_msg,
            ],
            "options": {"temperature": 0.7, "num_predict": 280},
        }
        async with httpx.AsyncClient(timeout=float(OOGWAY_BRAIN_CHAT_TIMEOUT_SECONDS)) as client:
            resp = await client.post(f"{OOGWAY_OLLAMA_BASE.rstrip('/')}/api/chat", json=payload)
        if resp.status_code >= 400:
            body_excerpt = ""
            with suppress(Exception):
                body_excerpt = resp.text[:280]
            brain_log(
                "ollama.chat.http_error",
                level="error",
                model=model_name,
                status=resp.status_code,
                body=body_excerpt,
            )
            return ""
        data = resp.json()
        reply = str(data.get("message", {}).get("content", "")).strip()[:400]
        brain_log("ollama.chat.response", model=model_name, replyChars=len(reply))
        return reply

    # Prefer vision model when images exist, then gracefully fall back to text model.
    if image_payload and OOGWAY_OLLAMA_VISION_MODEL:
        with suppress(Exception):
            reply = await _chat_with(OOGWAY_OLLAMA_VISION_MODEL, include_images=True)
            if reply:
                return reply
        brain_log("ollama.chat.vision_fallback", level="warning", model=OOGWAY_OLLAMA_VISION_MODEL)

    try:
        return await _chat_with(OOGWAY_OLLAMA_MODEL, include_images=False)
    except Exception as exc:
        brain_log("ollama.chat.exception", level="error", model=OOGWAY_OLLAMA_MODEL, error=str(exc))
        return ""


async def vision_json_classify(
    snapshots: list[dict[str, str]],
    system_prompt: str,
    task_prompt: str,
    keys: list[str],
) -> dict[str, bool]:
    defaults = {key: False for key in keys}
    if not snapshots:
        brain_log("vision.classify.skip.no_snapshots", keys=keys, level="debug")
        return defaults

    if not OOGWAY_OLLAMA_VISION_MODEL:
        brain_log("vision.classify.skip.no_model", keys=keys, level="warning")
        return defaults

    selected_image = _select_single_snapshot_image(snapshots)
    images = [selected_image] if selected_image else []
    if not images:
        brain_log("vision.classify.skip.no_images", keys=keys, level="warning")
        return defaults

    try:
        payload = {
            "model": OOGWAY_OLLAMA_VISION_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task_prompt, "images": images},
            ],
            "options": {"temperature": 0.1, "num_predict": 120},
        }
        async with httpx.AsyncClient(timeout=float(OOGWAY_BRAIN_VISION_TIMEOUT_SECONDS)) as client:
            resp = await client.post(f"{OOGWAY_OLLAMA_BASE.rstrip('/')}/api/chat", json=payload)
        if resp.status_code >= 400:
            body_excerpt = ""
            with suppress(Exception):
                body_excerpt = resp.text[:280]
            brain_log(
                "vision.classify.http_error",
                level="error",
                status=resp.status_code,
                keys=keys,
                body=body_excerpt,
            )
            return defaults
        content = resp.json().get("message", {}).get("content", "")
        parsed = _parse_json_from_text(str(content))
        if not parsed:
            brain_log(
                "vision.classify.parse_error",
                level="warning",
                keys=keys,
                content=str(content)[:280],
            )
            return defaults
        result = {key: bool(parsed.get(key, False)) for key in keys}
        brain_log("vision.classify.ok", keys=keys, result=result)
        return result
    except Exception as exc:
        brain_log("vision.classify.exception", level="error", keys=keys, error=str(exc))
        return defaults


async def evaluate_care_needs(snapshots: list[dict[str, str]]) -> dict[str, Any]:
    """Returns food_level and water_level as one of: 'empty', 'low', 'medium', 'full'."""
    _LEVEL_DEFAULTS: dict[str, Any] = {"food_level": "unknown", "water_level": "unknown", "food_empty": False, "water_empty": False}

    if not snapshots:
        brain_log("vision.care.skip.no_snapshots", level="debug")
        return _LEVEL_DEFAULTS

    if not OOGWAY_OLLAMA_VISION_MODEL:
        brain_log("vision.care.skip.no_model", level="warning")
        return _LEVEL_DEFAULTS

    images = _select_snapshot_images(snapshots, "food water bowls", max_images=2)
    if not images:
        brain_log("vision.care.skip.no_images", level="warning")
        return _LEVEL_DEFAULTS

    system_prompt = (
        "You are a precise terrarium monitoring assistant. "
        "You analyze camera images of a tortoise enclosure to assess food and water bowl fill levels."
    )
    task_prompt = (
        "Look carefully at the food dish and water dish in these terrarium camera images. "
        "Estimate how full each container is. "
        'Return ONLY strict JSON: {"food_level": "...", "water_level": "..."}. '
        'Each level must be exactly one of: "empty", "low", "medium", "full". '
        '"empty" = visibly empty or nearly empty (under 10% full). '
        '"low" = noticeably low, needs refilling soon (10–35% full). '
        '"medium" = partially filled, ok for now (35–70% full). '
        '"full" = well-stocked or nearly full (over 70% full). '
        "If a bowl is not visible or you cannot determine, use \"medium\" as a safe default."
    )

    try:
        payload = {
            "model": OOGWAY_OLLAMA_VISION_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task_prompt, "images": images},
            ],
            "options": {"temperature": 0.1, "num_predict": 60},
        }
        async with httpx.AsyncClient(timeout=float(OOGWAY_BRAIN_VISION_TIMEOUT_SECONDS)) as client:
            resp = await client.post(f"{OOGWAY_OLLAMA_BASE.rstrip('/')}/api/chat", json=payload)
        if resp.status_code >= 400:
            body_excerpt = ""
            with suppress(Exception):
                body_excerpt = resp.text[:280]
            brain_log("vision.care.http_error", level="error", status=resp.status_code, body=body_excerpt)
            return _LEVEL_DEFAULTS
        content = resp.json().get("message", {}).get("content", "")
        parsed = _parse_json_from_text(str(content))
        if not parsed:
            brain_log("vision.care.parse_error", level="warning", content=str(content)[:280])
            return _LEVEL_DEFAULTS

        _VALID_LEVELS = {"empty", "low", "medium", "full"}
        food_level = str(parsed.get("food_level", "medium")).lower()
        water_level = str(parsed.get("water_level", "medium")).lower()
        if food_level not in _VALID_LEVELS:
            food_level = "medium"
        if water_level not in _VALID_LEVELS:
            water_level = "medium"

        result = {
            "food_level": food_level,
            "water_level": water_level,
            "food_empty": food_level == "empty",
            "water_empty": water_level == "empty",
        }
        brain_log("vision.care.ok", result=result)
        return result
    except Exception as exc:
        brain_log("vision.care.exception", level="error", error=str(exc))
        return _LEVEL_DEFAULTS


async def evaluate_eating_drinking(snapshots: list[dict[str, str]]) -> dict[str, bool]:
    defaults = {
        "scene_lit": False,
        "tortoise_visible": False,
        "near_food": False,
        "near_water": False,
        "eating": False,
        "drinking": False,
    }
    if not snapshots:
        brain_log("vision.behavior.skip.no_snapshots", level="debug")
        return defaults
    if not OOGWAY_OLLAMA_VISION_MODEL:
        brain_log("vision.behavior.skip.no_model", level="warning")
        return defaults

    images = _select_snapshot_images(snapshots, "tortoise eating drinking water food", max_images=2)
    if not images:
        brain_log("vision.behavior.skip.no_images", level="warning")
        return defaults

    payload = {
        "model": OOGWAY_OLLAMA_VISION_MODEL,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You classify tortoise behavior from terrarium images. "
                    "Be conservative and avoid false positives."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Return ONLY strict JSON with keys: "
                    '{"scene_lit": boolean, "tortoise_visible": boolean, "near_food": boolean, "near_water": boolean, "eating": boolean, "drinking": boolean}. '
                    "Rules: if scene is dark/low-light or unclear, scene_lit=false and all other fields false. "
                    "Set near_food=true only if tortoise is physically at the food dish. "
                    "Set near_water=true only if tortoise is physically at the water dish. "
                    "Set eating=true only when tortoise is clearly biting/chewing food and near_food=true. "
                    "Set drinking=true only when tortoise is clearly sipping from water and near_water=true. "
                    "If uncertain, return false."
                ),
                "images": images,
            },
        ],
        "options": {"temperature": 0.0, "num_predict": 90},
    }

    try:
        async with httpx.AsyncClient(timeout=float(OOGWAY_BRAIN_VISION_TIMEOUT_SECONDS)) as client:
            resp = await client.post(f"{OOGWAY_OLLAMA_BASE.rstrip('/')}/api/chat", json=payload)
        if resp.status_code >= 400:
            body_excerpt = ""
            with suppress(Exception):
                body_excerpt = resp.text[:280]
            brain_log("vision.behavior.http_error", level="error", status=resp.status_code, body=body_excerpt)
            return defaults

        content = resp.json().get("message", {}).get("content", "")
        parsed = _parse_json_from_text(str(content))
        if not parsed:
            brain_log("vision.behavior.parse_error", level="warning", content=str(content)[:280])
            return defaults

        result = {
            "scene_lit": bool(parsed.get("scene_lit", False)),
            "tortoise_visible": bool(parsed.get("tortoise_visible", False)),
            "near_food": bool(parsed.get("near_food", False)),
            "near_water": bool(parsed.get("near_water", False)),
            "eating": bool(parsed.get("eating", False)),
            "drinking": bool(parsed.get("drinking", False)),
        }

        # Hard guardrails to suppress hallucinated behavior calls.
        if not result["scene_lit"] or not result["tortoise_visible"]:
            result["near_food"] = False
            result["near_water"] = False
            result["eating"] = False
            result["drinking"] = False
        if not result["near_food"]:
            result["eating"] = False
        if not result["near_water"]:
            result["drinking"] = False

        brain_log("vision.behavior.ok", result=result)
        return result
    except Exception as exc:
        brain_log("vision.behavior.exception", level="error", error=str(exc))
        return defaults


async def evaluate_behavior_state(snapshots: list[dict[str, str]]) -> dict[str, bool]:
    """Classify tortoise location (in/out of hut) and whether it has fallen over."""
    defaults: dict[str, bool] = {
        "scene_lit": False,
        "tortoise_visible": False,
        "in_hut": False,
        "fallen_over": False,
    }
    if not snapshots or not OOGWAY_OLLAMA_VISION_MODEL:
        return defaults

    images = _select_snapshot_images(snapshots, "tortoise in hut fallen over water bowl", max_images=2)
    if not images:
        return defaults

    payload = {
        "model": OOGWAY_OLLAMA_VISION_MODEL,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a precise terrarium monitor. "
                    "Analyze tortoise position and posture in the camera images. "
                    "Be conservative — only report true when clearly visible."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Return ONLY strict JSON with these keys: "
                    '{"scene_lit": boolean, "tortoise_visible": boolean, "in_hut": boolean, "fallen_over": boolean}. '
                    "scene_lit: true if the enclosure is well lit and clearly visible. "
                    "tortoise_visible: true if you can clearly see the tortoise. "
                    "in_hut: true if the tortoise is inside or entering the wooden/hide hut structure. "
                    "fallen_over: true if the tortoise appears to be on its side or upside down (flipped). "
                    "If uncertain about any field, return false."
                ),
                "images": images,
            },
        ],
        "options": {"temperature": 0.0, "num_predict": 80},
    }

    try:
        async with httpx.AsyncClient(timeout=float(OOGWAY_BRAIN_VISION_TIMEOUT_SECONDS)) as client:
            resp = await client.post(f"{OOGWAY_OLLAMA_BASE.rstrip('/')}/api/chat", json=payload)
        if resp.status_code >= 400:
            brain_log("vision.state.http_error", level="error", status=resp.status_code)
            return defaults

        content = resp.json().get("message", {}).get("content", "")
        parsed = _parse_json_from_text(str(content))
        if not parsed:
            brain_log("vision.state.parse_error", level="warning", content=str(content)[:280])
            return defaults

        result: dict[str, bool] = {
            "scene_lit": bool(parsed.get("scene_lit", False)),
            "tortoise_visible": bool(parsed.get("tortoise_visible", False)),
            "in_hut": bool(parsed.get("in_hut", False)),
            "fallen_over": bool(parsed.get("fallen_over", False)),
        }
        # Hard guardrail: suppress all positional flags when dark or tortoise not visible
        if not result["scene_lit"] or not result["tortoise_visible"]:
            result["in_hut"] = False
            result["fallen_over"] = False

        brain_log("vision.state.ok", result=result)
        return result
    except Exception as exc:
        brain_log("vision.state.exception", level="error", error=str(exc))
        return defaults


_EATING_REACTIONS: list[str] = [
    "*munch* *munch*",
    "munch munch",
    "*munch munch munch*",
    "mmm... munching",
    "munch time",
]

_DRINKING_REACTIONS: list[str] = [
    "*sip*",
    "*sip sip*",
    "sip sip sip",
    "*sip... ahh*",
    "hydration sip",
]

_SLEEP_REACTIONS: list[str] = [
    "let me sleep.",
    "im sleeping. let me sleep.",
    "no. bedtime. let me sleep.",
    "go away. tortoise is sleeping.",
    "zzz... stop poking me.",
    "its dark. im asleep. let me sleep.",
    "hiss... just kidding. let me sleep.",
    "mmm kale dream... let me sleep.",
    "bedtime means quiet time.",
    "not now. shell closed. let me sleep.",
]


async def run_brain_eating_check() -> None:
    global LAST_EATING_CHECK_AT, LAST_EATING_REACT_AT, LAST_BRAIN_SPOKE_AT

    if not OOGWAY_BRAIN_ENABLED or not is_brain_configured():
        brain_log("brain.eating.skip.not_configured", level="debug")
        return

    if not brain_awake_now():
        brain_log("brain.eating.skip.asleep", level="debug")
        return

    if LAST_EATING_CHECK_AT:
        elapsed = (now_utc() - LAST_EATING_CHECK_AT).total_seconds()
        if elapsed < OOGWAY_BRAIN_EATING_CHECK_INTERVAL_SECONDS:
            brain_log("brain.eating.skip.interval", elapsed=elapsed, needed=OOGWAY_BRAIN_EATING_CHECK_INTERVAL_SECONDS, level="debug")
            return

    LAST_EATING_CHECK_AT = now_utc()

    if not LAST_BRAIN_MOVEMENT_AT:
        brain_log("brain.eating.skip.no_movement_history", level="debug")
        return
    if (now_utc() - LAST_BRAIN_MOVEMENT_AT).total_seconds() > OOGWAY_BRAIN_MOVEMENT_WINDOW_SECONDS:
        brain_log("brain.eating.skip.movement_stale", level="debug")
        return

    if LAST_EATING_REACT_AT:
        if (now_utc() - LAST_EATING_REACT_AT).total_seconds() < OOGWAY_BRAIN_EATING_REACT_COOLDOWN_SECONDS:
            brain_log("brain.eating.skip.cooldown", level="debug")
            return

    snapshots = await capture_brain_snapshots_data_urls()
    if not snapshots:
        brain_log("brain.eating.skip.no_snapshots", level="warning")
        return

    result = await evaluate_eating_drinking(snapshots)
    brain_log("brain.eating.classified", result=result)

    if not result.get("scene_lit"):
        brain_log("brain.eating.skip.dark_scene", level="debug")
        return
    if not result.get("tortoise_visible"):
        brain_log("brain.eating.skip.not_visible", level="debug")
        return

    reaction: str | None = None
    if result.get("drinking"):
        reaction = random.choice(_DRINKING_REACTIONS)
    elif result.get("eating"):
        reaction = random.choice(_EATING_REACTIONS)

    if not reaction:
        brain_log("brain.eating.skip.no_reaction", level="debug")
        return

    msg = build_chat_item(
        username=OOGWAY_BRAIN_NAME,
        username_color=BRAIN_USERNAME_COLOR,
        text=reaction,
        kind="chat",
    )
    append_chat_log(msg)
    await broadcast_chat(msg)
    remember_memory_event(
        topic="watering" if result.get("drinking") else "feeding",
        note=f"Observed {'drinking' if result.get('drinking') else 'eating'} in camera view. Oogway said: {reaction}",
        trigger="vision-behavior",
        ts=msg["ts"],
    )
    now = now_utc()
    LAST_EATING_REACT_AT = now
    LAST_BRAIN_SPOKE_AT = now


def care_alert_on_cooldown(kind: str) -> bool:
    last = LAST_CARE_ALERT_AT.get(kind)
    if not last:
        return False
    return (now_utc() - last).total_seconds() < OOGWAY_BRAIN_CARE_ALERT_COOLDOWN_SECONDS


def report_age_seconds(kind: str) -> int:
    updated_at = str((ACTIVE_REPORTS.get(kind) or {}).get("updatedAt", ""))
    updated_dt = parse_iso_ts(updated_at)
    if not updated_dt:
        return 0
    return max(0, int((now_utc() - updated_dt).total_seconds()))


def care_text_tone(kind: str) -> str:
    style = OOGWAY_TEXTS_STYLE
    if style in {"nice", "kind", "gentle"}:
        return "nice"
    if style in {"angry", "grumpy", "strict"}:
        return "angry"
    # auto mode escalates when care need has been unresolved for too long
    age = report_age_seconds(kind)
    return "angry" if age >= OOGWAY_TEXTS_ANGER_AFTER_SECONDS else "nice"


def build_oogway_care_text(kind: Literal["food", "water"], reminder: bool) -> tuple[str, str, str]:
    tone = care_text_tone(kind)
    need_word = "food" if kind == "food" else "water"

    if tone == "angry":
        if reminder:
            chat_text = f"im still waiting. i need {need_word} now."
            notify_text = f"Oogway: I am still waiting. I need {need_word} now."
        else:
            chat_text = f"it appears im out of {need_word}. please fix this now."
            notify_text = f"Oogway: It appears I'm out of {need_word}. Please fix this now."
        priority = "high"
    else:
        if reminder:
            chat_text = f"friendly reminder, i still need {need_word}."
            notify_text = f"Oogway: Friendly reminder, I still need {need_word} when you get a moment."
        else:
            chat_text = f"it appears im out of {need_word}."
            notify_text = f"Oogway: It appears I'm out of {need_word}. Could someone help me out?"
        priority = "default"

    return chat_text, notify_text, priority


async def emit_oogway_care_alert(kind: Literal["food", "water"], reminder: bool = False) -> None:
    now_dt = now_utc()
    now_iso = now_dt.isoformat()
    chat_text, notify_text, priority = build_oogway_care_text(kind, reminder)

    existing_updated_at = str((ACTIVE_REPORTS.get(kind) or {}).get("updatedAt", ""))
    ACTIVE_REPORTS[kind] = {
        "active": True,
        "reporter": OOGWAY_BRAIN_NAME,
        "updatedAt": existing_updated_at if (reminder and existing_updated_at) else now_iso,
    }

    chat_item = {
        "id": str(uuid.uuid4()),
        "kind": "report",
        "username": OOGWAY_BRAIN_NAME,
        "usernameColor": BRAIN_USERNAME_COLOR,
        "text": chat_text,
        "textColor": "white",
        "ts": now_iso,
        "report": {
            "kind": kind,
            "active": True,
        },
    }
    append_chat_log(chat_item)
    await broadcast_chat(chat_item)
    brain_log("brain.care.alert", kind=kind, reminder=reminder, text=chat_text)
    remember_memory_event(
        topic=f"care-{kind}",
        note=f"Oogway care alert ({'reminder' if reminder else 'new'}): {chat_text}",
        trigger="care-alert",
        ts=now_iso,
    )

    if OOGWAY_TEXTS_TOPIC:
        with suppress(Exception):
            await send_ntfy_message(
                OOGWAY_TEXTS_TOPIC,
                notify_text,
                title=f"Text from {OOGWAY_BRAIN_NAME}",
                priority=priority,
                tags="turtle,text,care",
            )

    LAST_CARE_ALERT_AT[kind] = now_dt


async def run_brain_care_check() -> None:
    global LAST_BRAIN_CARE_CHECK_AT, LAST_CARE_LEVELS

    if not OOGWAY_BRAIN_ENABLED or not is_brain_configured():
        brain_log("brain.care.skip.not_configured", level="debug")
        return

    if not brain_awake_now():
        brain_log("brain.care.skip.asleep", level="debug")
        return

    if LAST_BRAIN_CARE_CHECK_AT:
        elapsed = (now_utc() - LAST_BRAIN_CARE_CHECK_AT).total_seconds()
        if elapsed < OOGWAY_BRAIN_CARE_CHECK_INTERVAL_SECONDS:
            brain_log("brain.care.skip.interval", elapsed=elapsed, needed=OOGWAY_BRAIN_CARE_CHECK_INTERVAL_SECONDS, level="debug")
            return

    LAST_BRAIN_CARE_CHECK_AT = now_utc()

    movement_recent = await refresh_brain_motion_state()
    snapshots = await capture_brain_snapshots_data_urls()
    care_eval = await evaluate_care_needs(snapshots)
    brain_log(
        "brain.care.classified",
        movementRecent=movement_recent,
        foodLevel=care_eval.get("food_level", "unknown"),
        waterLevel=care_eval.get("water_level", "unknown"),
        foodEmpty=care_eval.get("food_empty", False),
        waterEmpty=care_eval.get("water_empty", False),
    )

    food_level = care_eval.get("food_level", "unknown")
    water_level = care_eval.get("water_level", "unknown")

    # Capture meaningful bowl-level changes for memory callback.
    for kind, current_level in [("food", food_level), ("water", water_level)]:
        previous_level = LAST_CARE_LEVELS.get(kind, "unknown")
        if current_level != previous_level and previous_level != "unknown":
            prev_rank = care_level_rank(previous_level)
            curr_rank = care_level_rank(current_level)
            if prev_rank <= 2 and curr_rank >= 3:
                remember_memory_event(
                    topic=f"{kind}-refill",
                    note=f"{kind.title()} level appears refilled from {previous_level} to {current_level}.",
                    trigger="vision-care-change",
                )
            else:
                remember_memory_event(
                    topic=f"{kind}-level-change",
                    note=f"{kind.title()} level changed from {previous_level} to {current_level}.",
                    trigger="vision-care-change",
                )
        LAST_CARE_LEVELS[kind] = current_level

    # Log a passive care observation to the daily journal — throttled to every 30 min
    global LAST_CARE_OBSERVATION_AT
    obs_due = (
        LAST_CARE_OBSERVATION_AT is None
        or (now_utc() - LAST_CARE_OBSERVATION_AT).total_seconds() >= _CARE_OBSERVATION_INTERVAL_SECONDS
    )
    if obs_due and (food_level != "unknown" or water_level != "unknown"):
        remember_memory_event(
            topic="care-observation",
            note=f"Vision check: food bowl is {food_level}, water bowl is {water_level}.",
            trigger="vision-care",
        )
        LAST_CARE_OBSERVATION_AT = now_utc()

    for kind in ["food", "water"]:
        empty_flag = care_eval.get(f"{kind}_empty", False)
        CARE_EMPTY_STREAK[kind] = (CARE_EMPTY_STREAK[kind] + 1) if empty_flag else 0

        if not empty_flag:
            continue

        active_report = bool(ACTIVE_REPORTS.get(kind, {}).get("active"))
        if care_alert_on_cooldown(kind):
            continue
        if not movement_recent:
            continue

        if active_report:
            await emit_oogway_care_alert(kind, reminder=True)
            continue

        if CARE_EMPTY_STREAK[kind] >= OOGWAY_BRAIN_CARE_EMPTY_CONFIRMATIONS:
            await emit_oogway_care_alert(kind, reminder=False)


def remember_interaction(trigger: str, source_message: dict[str, Any] | None, reply_text: str) -> None:
    source_text = str((source_message or {}).get("text", ""))
    person = str((source_message or {}).get("username", "")).strip()
    observed_context = ""
    if LAST_OBSERVED_LOCATION and LAST_OBSERVED_LOCATION != "unknown":
        observed_context = f" | observed: {LAST_OBSERVED_LOCATION} ({LAST_OBSERVED_ACTIVITY})"
    if source_text:
        topic = infer_memory_topic_slug(source_text, fallback="human-chat" if trigger in {"mention", "chat"} else "routine")
        note = f"{person or 'Someone'}: {source_text[:140]} | Oogway: {reply_text[:140]}{observed_context}"[:220]
    else:
        topic = infer_memory_topic_slug(f"{LAST_OBSERVED_SUMMARY} {reply_text}", fallback=LAST_OBSERVED_TOPIC or "routine")
        if LAST_OBSERVED_SUMMARY:
            note = f"Daytime self-observation: {LAST_OBSERVED_SUMMARY[:140]} Oogway said: {reply_text[:140]}"
        else:
            note = f"Oogway daily update: {reply_text[:180]}"

    remember_memory_event(topic=topic, note=note, trigger=trigger)
    with suppress(Exception):
        if person:
            append_person_profile_learning(
                person,
                f"Conversation: \"{source_text[:120]}\" | Oogway replied: \"{reply_text[:120]}\"",
                ts=str((source_message or {}).get("ts", "")) or None,
            )
            append_personality_learning(
                f"Interaction with {person}: responded in {trigger} context.",
                ts=str((source_message or {}).get("ts", "")) or None,
            )


def brain_awake_now() -> bool:
    status = daylight_status_payload()
    return not status.get("asleep", False)


def should_trigger_oogway_mention(text: str) -> bool:
    trigger = (OOGWAY_BRAIN_MENTION_TRIGGER or "@oogway").strip().lower()
    if not trigger:
        trigger = "@oogway"
    return trigger in text.lower()


async def enqueue_brain_response(trigger: str, source_message: dict[str, Any] | None = None) -> bool:
    global BRAIN_QUEUE_SEQUENCE

    queue = BRAIN_RESPONSE_QUEUE
    if queue is None:
        brain_log("brain.queue.missing", trigger=trigger, level="warning")
        return False

    if trigger == "periodic" and queue.qsize() > 0:
        brain_log("brain.queue.skip.periodic_busy", queued=queue.qsize(), level="debug")
        return False

    priority = 0 if trigger in {"mention", "manual"} else (1 if trigger == "chat" else 5)
    BRAIN_QUEUE_SEQUENCE += 1
    await queue.put((priority, BRAIN_QUEUE_SEQUENCE, {"trigger": trigger, "source_message": source_message}))
    brain_log("brain.queue.enqueued", trigger=trigger, priority=priority, queued=queue.qsize())
    return True


async def brain_response_worker() -> None:
    while True:
        if BRAIN_RESPONSE_QUEUE is None:
            await asyncio.sleep(0.2)
            continue
        _priority, _seq, item = await BRAIN_RESPONSE_QUEUE.get()
        try:
            await run_oogway_brain(
                trigger=str(item.get("trigger", "periodic")),
                source_message=item.get("source_message"),
            )
        except Exception as exc:
            brain_log("brain.queue.worker_error", level="error", error=str(exc))
        finally:
            BRAIN_RESPONSE_QUEUE.task_done()


async def run_oogway_brain(trigger: str, source_message: dict[str, Any] | None = None) -> None:
    global LAST_BRAIN_SPOKE_AT

    if not OOGWAY_BRAIN_ENABLED or not is_brain_configured():
        brain_log("brain.reply.skip.not_configured", trigger=trigger, level="warning")
        return

    async with BRAIN_LOCK:
        with suppress(Exception):
            await refresh_daylight_cache(force=False)

        sleepy_mode = not brain_awake_now()
        if sleepy_mode:
            if trigger in {"mention", "chat"}:
                brain_log("brain.reply.sleeping.generate", trigger=trigger)
            elif trigger == "manual":
                pass  # manual trigger bypasses sleep gate — fall through to normal reply
            else:
                brain_log("brain.reply.skip.asleep", trigger=trigger, level="debug")
                return

        if trigger == "periodic" and LAST_BRAIN_SPOKE_AT:
            elapsed = (now_utc() - LAST_BRAIN_SPOKE_AT).total_seconds()
            if elapsed < OOGWAY_BRAIN_INTERVAL_SECONDS:
                brain_log("brain.reply.skip.interval", trigger=trigger, elapsed=elapsed, needed=OOGWAY_BRAIN_INTERVAL_SECONDS, level="debug")
                return

        movement_recent = await refresh_brain_motion_state()

        prompt_text = build_oogway_prompt(trigger, source_message, sleepy_mode=sleepy_mode)
        snapshots = await capture_brain_snapshots_data_urls()
        brain_log("brain.reply.request", trigger=trigger, snapshots=len(snapshots), promptChars=len(prompt_text))
        await broadcast_oogway_typing(True)
        try:
            reply = await call_ollama_for_oogway(prompt_text, snapshots)
        finally:
            await broadcast_oogway_typing(False)
        if not reply:
            brain_log("brain.reply.empty", trigger=trigger, level="warning")
            return

        msg = build_chat_item(
            username=OOGWAY_BRAIN_NAME,
            username_color=BRAIN_USERNAME_COLOR,
            text=reply,
            kind="chat",
        )
        append_chat_log(msg)
        await broadcast_chat(msg)
        hidden_thought = await generate_hidden_thought(trigger, source_message, reply)
        if hidden_thought:
            append_to_hidden_thoughts_log(msg["ts"], hidden_thought, trigger=trigger)
        remember_interaction(trigger, source_message, reply)
        brain_log("brain.reply.sent", trigger=trigger, reply=reply)
        LAST_BRAIN_SPOKE_AT = now_utc()


async def run_brain_behavior_check() -> None:
    """Periodic vision check for hut entry/exit, fallen over, fed, watered — logs everything to Obsidian."""
    global LAST_BEHAVIOR_CHECK_AT, LAST_HUT_STATE, LAST_FALLEN_ALERT_AT
    global LAST_ACTIVITY_LOG_AT, LAST_OBSERVED_SUMMARY, LAST_OBSERVED_TOPIC
    global LAST_OBSERVED_LOCATION, LAST_OBSERVED_ACTIVITY

    if not OOGWAY_BRAIN_ENABLED or not is_brain_configured():
        return

    if not brain_awake_now():
        return

    if LAST_BEHAVIOR_CHECK_AT:
        elapsed = (now_utc() - LAST_BEHAVIOR_CHECK_AT).total_seconds()
        if elapsed < OOGWAY_BRAIN_BEHAVIOR_CHECK_INTERVAL_SECONDS:
            return

    LAST_BEHAVIOR_CHECK_AT = now_utc()

    snapshots = await capture_brain_snapshots_data_urls()
    if not snapshots:
        return

    state = await evaluate_behavior_state(snapshots)
    behavior = await evaluate_eating_drinking(snapshots)

    # Reconcile classifier conflicts: bowl/drinking observations win over hut location.
    effective_in_hut = bool(state.get("in_hut", False))
    if behavior.get("near_water") or behavior.get("near_food") or behavior.get("drinking") or behavior.get("eating"):
        effective_in_hut = False
    state_for_summary = dict(state)
    state_for_summary["in_hut"] = effective_in_hut
    brain_log("brain.behavior.classified", state=state)

    if not state.get("scene_lit") or not state.get("tortoise_visible"):
        return

    now_dt = now_utc()
    now_iso = now_dt.isoformat()
    summary, summary_topic, location_label, links = summarize_observed_state(state_for_summary, behavior)
    activity_label = summary.removeprefix(f"Oogway is {location_label} and ").rstrip(".") if summary.startswith(f"Oogway is {location_label} and ") else summary
    observation_due = (
        LAST_ACTIVITY_LOG_AT is None
        or (now_dt - LAST_ACTIVITY_LOG_AT).total_seconds() >= OOGWAY_BRAIN_ACTIVITY_LOG_INTERVAL_SECONDS
        or summary != LAST_OBSERVED_SUMMARY
    )
    LAST_OBSERVED_SUMMARY = summary
    LAST_OBSERVED_TOPIC = summary_topic
    LAST_OBSERVED_LOCATION = location_label
    LAST_OBSERVED_ACTIVITY = activity_label
    if observation_due:
        append_to_daily_activity_log(now_iso, summary_topic, summary, links=links)
        remember_memory_event(topic=summary_topic, note=summary, trigger="vision-observation", ts=now_iso)
        LAST_ACTIVITY_LOG_AT = now_dt

    # --- Hut entry / exit transition ---
    in_hut_now = effective_in_hut
    if LAST_HUT_STATE is not None and in_hut_now != LAST_HUT_STATE:
        if in_hut_now:
            event_note = "Oogway entered the hut."
            topic = "hut-entry"
        else:
            event_note = "Oogway left the hut and is out exploring."
            topic = "hut-exit"
        remember_memory_event(topic=topic, note=event_note, trigger="vision-behavior", ts=now_iso)
        brain_log("brain.behavior.hut_transition", in_hut=in_hut_now)
    LAST_HUT_STATE = in_hut_now

    # --- Fallen over alert ---
    if state.get("fallen_over"):
        fallen_ok = (
            LAST_FALLEN_ALERT_AT is None
            or (now_dt - LAST_FALLEN_ALERT_AT).total_seconds() >= OOGWAY_BRAIN_FALLEN_ALERT_COOLDOWN_SECONDS
        )
        if fallen_ok:
            fallen_note = "Oogway appears to have flipped over and may need help!"
            remember_memory_event(topic="fallen", note=fallen_note, trigger="vision-behavior", ts=now_iso)
            msg = build_chat_item(
                username=OOGWAY_BRAIN_NAME,
                username_color=BRAIN_USERNAME_COLOR,
                text="i think i fell over... help?",
                kind="chat",
            )
            append_chat_log(msg)
            await broadcast_chat(msg)
            if OOGWAY_TEXTS_TOPIC:
                with suppress(Exception):
                    await send_ntfy_message(
                        OOGWAY_TEXTS_TOPIC,
                        f"⚠️ {OOGWAY_BRAIN_NAME} appears to have flipped over and needs help!",
                        title=f"Emergency — {OOGWAY_BRAIN_NAME} fell over",
                        priority="high",
                        tags="turtle,emergency,fallen",
                    )
            LAST_FALLEN_ALERT_AT = now_dt
            brain_log("brain.behavior.fallen_alert")


async def oogway_brain_loop() -> None:
    await asyncio.sleep(20)
    while True:
        try:
            await run_brain_care_check()
            await run_brain_eating_check()
            await run_brain_behavior_check()
            await enqueue_brain_response(trigger="periodic")
        except Exception:
            # Keep loop alive even if upstream LLM/camera calls fail.
            pass
        await asyncio.sleep(min(
            OOGWAY_BRAIN_INTERVAL_SECONDS,
            OOGWAY_BRAIN_CARE_CHECK_INTERVAL_SECONDS,
            OOGWAY_BRAIN_EATING_CHECK_INTERVAL_SECONDS,
            OOGWAY_BRAIN_BEHAVIOR_CHECK_INTERVAL_SECONDS,
        ))


def get_local_tz() -> ZoneInfo:
    try:
        return ZoneInfo(TZ)
    except Exception:
        return ZoneInfo("UTC")


def parse_iso_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def local_obsidian_iso(ts: Any | None = None) -> str:
    local_tz = get_local_tz()
    if isinstance(ts, datetime):
        dt = ts
    elif ts:
        parsed = parse_iso_ts(str(ts))
        if parsed is None:
            return str(ts)
        dt = parsed
    else:
        dt = now_utc()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(local_tz).isoformat()


def local_obsidian_timestamp(ts: Any | None = None) -> str:
    local_dt = parse_iso_ts(local_obsidian_iso(ts))
    if local_dt is None:
        return str(ts or "")[:19]
    return local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def cleanup_admin_tokens() -> None:
    now = now_utc()
    expired = [token for token, exp in ADMIN_TOKENS.items() if exp <= now]
    for token in expired:
        ADMIN_TOKENS.pop(token, None)


def require_admin(request: Request) -> None:
    cleanup_admin_tokens()
    token = request.headers.get("X-Admin-Token", "").strip()
    if not token or token not in ADMIN_TOKENS:
        raise HTTPException(status_code=401, detail="Admin authorization required")


def issue_admin_token() -> str:
    cleanup_admin_tokens()
    token = uuid.uuid4().hex
    ADMIN_TOKENS[token] = now_utc() + timedelta(hours=12)
    return token


async def refresh_daylight_cache(force: bool = False) -> None:
    now = now_utc()
    if not force and DAYLIGHT_CACHE["lastRefresh"]:
        last = parse_iso_ts(DAYLIGHT_CACHE["lastRefresh"])
        if last and (now - last) < timedelta(hours=4):
            return

    try:
        lat = float(SUN_LAT)
        lng = float(SUN_LNG)
    except Exception:
        DAYLIGHT_CACHE["error"] = "SUN_LAT/SUN_LNG must be numeric"
        DAYLIGHT_CACHE["lastRefresh"] = now.isoformat()
        return

    url = "https://api.sunrise-sunset.org/json"
    params = {"lat": lat, "lng": lng, "formatted": 0}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
    if resp.status_code >= 400:
        DAYLIGHT_CACHE["error"] = "Failed to fetch sunrise/sunset"
        DAYLIGHT_CACHE["lastRefresh"] = now.isoformat()
        return

    payload = resp.json()
    if payload.get("status") != "OK" or not payload.get("results"):
        DAYLIGHT_CACHE["error"] = "Sunrise API returned invalid payload"
        DAYLIGHT_CACHE["lastRefresh"] = now.isoformat()
        return

    sunrise_utc = parse_iso_ts(payload["results"].get("sunrise"))
    sunset_utc = parse_iso_ts(payload["results"].get("sunset"))
    if not sunrise_utc or not sunset_utc:
        DAYLIGHT_CACHE["error"] = "Could not parse sunrise/sunset timestamps"
        DAYLIGHT_CACHE["lastRefresh"] = now.isoformat()
        return

    local_tz = get_local_tz()
    sunrise_local = sunrise_utc.astimezone(local_tz)
    sunset_local = sunset_utc.astimezone(local_tz)

    DAYLIGHT_CACHE.update(
        {
            "sunriseUtc": sunrise_utc.isoformat(),
            "sunsetUtc": sunset_utc.isoformat(),
            "sunriseLocal": sunrise_local.isoformat(),
            "sunsetLocal": sunset_local.isoformat(),
            "forDate": now.astimezone(local_tz).date().isoformat(),
            "lastRefresh": now.isoformat(),
            "error": "",
        }
    )


def daylight_status_payload() -> dict[str, Any]:
    local_tz = get_local_tz()
    now_local = now_utc().astimezone(local_tz)
    sunrise_local = parse_iso_ts(DAYLIGHT_CACHE.get("sunriseLocal"))
    sunset_local = parse_iso_ts(DAYLIGHT_CACHE.get("sunsetLocal"))

    asleep = False
    bedtime_soon = False
    seconds_until_sunrise = 0
    seconds_until_sunset = 0

    if sunrise_local and sunset_local:
        asleep = now_local < sunrise_local or now_local >= sunset_local
        next_sunrise = sunrise_local
        if now_local >= sunset_local:
            next_sunrise = sunrise_local + timedelta(days=1)
        seconds_until_sunrise = max(0, int((next_sunrise - now_local).total_seconds()))
        seconds_until_sunset = max(0, int((sunset_local - now_local).total_seconds()))
        bedtime_soon = (not asleep) and seconds_until_sunset <= BEDTIME_SOON_MINUTES * 60

    return {
        "nowLocal": now_local.isoformat(),
        "sunriseLocal": DAYLIGHT_CACHE.get("sunriseLocal", ""),
        "sunsetLocal": DAYLIGHT_CACHE.get("sunsetLocal", ""),
        "forDate": DAYLIGHT_CACHE.get("forDate", ""),
        "asleep": asleep,
        "bedtimeSoon": bedtime_soon,
        "secondsUntilSunrise": seconds_until_sunrise,
        "secondsUntilSunset": seconds_until_sunset,
        "cacheError": DAYLIGHT_CACHE.get("error", ""),
        "lastRefresh": DAYLIGHT_CACHE.get("lastRefresh", ""),
    }


async def daylight_refresh_loop() -> None:
    while True:
        try:
            await refresh_daylight_cache(force=False)
        except Exception:
            DAYLIGHT_CACHE["error"] = "Unexpected daylight refresh error"
            DAYLIGHT_CACHE["lastRefresh"] = now_utc().isoformat()
        await asyncio.sleep(4 * 60 * 60)


async def chat_retention_loop() -> None:
    while True:
        try:
            await prune_chat_log_and_broadcast_if_changed()
        except Exception:
            brain_log("chat.retention.error", level="warning")
        await asyncio.sleep(CHAT_RETENTION_SWEEP_SECONDS)


@app.on_event("startup")
async def startup() -> None:
    ensure_list_file(ACTION_LOG_PATH)
    ensure_list_file(CHAT_LOG_PATH)
    ensure_obsidian_memory_dir()
    deleted_count = prune_generated_memory_notes()
    if deleted_count > 0:
        brain_log("memory.prune.startup", deleted=deleted_count, kept=OOGWAY_BRAIN_MEMORY_MAX_EVENT_NOTES)
    kept, changed = prune_chat_entries(read_list_file(CHAT_LOG_PATH, cap=200))
    if changed:
        write_list_file(CHAT_LOG_PATH, kept, cap=200)
    await refresh_daylight_cache(force=True)
    global DAYLIGHT_TASK, CHAT_RETENTION_TASK, BRAIN_TASK, BRAIN_QUEUE_TASK, BRAIN_RESPONSE_QUEUE
    DAYLIGHT_TASK = asyncio.create_task(daylight_refresh_loop())
    CHAT_RETENTION_TASK = asyncio.create_task(chat_retention_loop())
    BRAIN_RESPONSE_QUEUE = asyncio.PriorityQueue()
    BRAIN_QUEUE_TASK = asyncio.create_task(brain_response_worker())
    brain_log(
        "brain.startup",
        enabled=OOGWAY_BRAIN_ENABLED,
        configured=is_brain_configured(),
        obsidianVault=str(OOGWAY_OBSIDIAN_VAULT_PATH),
        obsidianMemoryFolder=OOGWAY_OBSIDIAN_MEMORY_FOLDER,
        obsidianMemoryDir=str(ensure_obsidian_memory_dir()),
        model=OOGWAY_OLLAMA_MODEL,
        visionModel=OOGWAY_OLLAMA_VISION_MODEL,
        ollamaBase=OOGWAY_OLLAMA_BASE,
        mentionTrigger=OOGWAY_BRAIN_MENTION_TRIGGER,
        cameraKey=OOGWAY_BRAIN_CAMERA_KEY,
    )
    if OOGWAY_BRAIN_ENABLED and is_brain_configured():
        BRAIN_TASK = asyncio.create_task(oogway_brain_loop())
        brain_log("brain.loop.started")
    else:
        brain_log("brain.loop.not_started", level="warning")


@app.on_event("shutdown")
async def shutdown() -> None:
    global DAYLIGHT_TASK, CHAT_RETENTION_TASK, BRAIN_TASK, BRAIN_QUEUE_TASK, BRAIN_RESPONSE_QUEUE
    if DAYLIGHT_TASK:
        DAYLIGHT_TASK.cancel()
        DAYLIGHT_TASK = None
    if CHAT_RETENTION_TASK:
        CHAT_RETENTION_TASK.cancel()
        CHAT_RETENTION_TASK = None
    if BRAIN_TASK:
        BRAIN_TASK.cancel()
        BRAIN_TASK = None
    if BRAIN_QUEUE_TASK:
        BRAIN_QUEUE_TASK.cancel()
        BRAIN_QUEUE_TASK = None
    BRAIN_RESPONSE_QUEUE = None


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")


@app.api_route(
    "/media/{mode}/{stream_path:path}",
    methods=["GET", "HEAD", "POST", "PATCH", "DELETE", "OPTIONS"],
)
async def media_proxy(mode: str, stream_path: str, request: Request) -> Response:
    return await proxy_mediastream(mode, stream_path, request)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    streams = get_configured_streams()
    upstream_checks: dict[str, Any] = {}
    for stream in streams:
        upstream_checks[stream["key"]] = await probe_stream_upstream(stream)

    return {
        "status": "ok",
        "version": APP_VERSION,
        "tz": TZ,
        "streamConfigured": "yes" if streams else "no",
        "ntfyConfigured": "yes" if NTFY_TOPIC else "no",
        "adminConfigured": "yes" if ADMIN_PASSWORD else "no",
        "brainEnabled": "yes" if OOGWAY_BRAIN_ENABLED else "no",
        "brainConfigured": "yes" if is_brain_configured() else "no",
        "brainModel": OOGWAY_OLLAMA_MODEL,
        "streams": get_default_stream_urls(),
        "streamOptions": [
            {
                "key": stream["key"],
                "label": stream["label"],
                "resolution": stream["resolution"],
                "urls": stream["urls"],
                "upstream": upstream_checks.get(stream["key"], {}),
            }
            for stream in streams
        ],
    }


@app.get("/api/daylight")
async def daylight_status() -> dict[str, Any]:
    await refresh_daylight_cache(force=False)
    return daylight_status_payload()


@app.get("/api/activity")
def activity() -> dict[str, list[dict[str, Any]]]:
    return {"items": read_action_log()}


@app.get("/api/chat/history")
def chat_history() -> dict[str, list[dict[str, Any]]]:
    return {"items": read_chat_log()}


@app.get("/api/reports")
def get_reports() -> dict[str, dict[str, Any]]:
    return {"items": ACTIVE_REPORTS}


@app.get("/api/brain/status")
def brain_status() -> dict[str, Any]:
    targets = get_brain_snapshot_targets()
    movement_age_seconds = None
    if LAST_BRAIN_MOVEMENT_AT:
        movement_age_seconds = max(0, int((now_utc() - LAST_BRAIN_MOVEMENT_AT).total_seconds()))
    return {
        "enabled": OOGWAY_BRAIN_ENABLED,
        "configured": is_brain_configured(),
        "name": OOGWAY_BRAIN_NAME,
        "model": OOGWAY_OLLAMA_MODEL,
        "cameraKey": OOGWAY_BRAIN_CAMERA_KEY,
        "cameraTargets": [{"key": t["key"], "label": t["label"]} for t in targets],
        "intervalSeconds": OOGWAY_BRAIN_INTERVAL_SECONDS,
        "careCheckIntervalSeconds": OOGWAY_BRAIN_CARE_CHECK_INTERVAL_SECONDS,
        "careConfirmations": OOGWAY_BRAIN_CARE_EMPTY_CONFIRMATIONS,
        "careAlertCooldownSeconds": OOGWAY_BRAIN_CARE_ALERT_COOLDOWN_SECONDS,
        "textsTopic": OOGWAY_TEXTS_TOPIC,
        "textsStyle": OOGWAY_TEXTS_STYLE,
        "textsAngerAfterSeconds": OOGWAY_TEXTS_ANGER_AFTER_SECONDS,
        "movementWindowSeconds": OOGWAY_BRAIN_MOVEMENT_WINDOW_SECONDS,
        "movementThreshold": OOGWAY_BRAIN_MOTION_THRESHOLD,
        "lastMovementAt": LAST_BRAIN_MOVEMENT_AT.isoformat() if LAST_BRAIN_MOVEMENT_AT else "",
        "movementAgeSeconds": movement_age_seconds,
        "awake": brain_awake_now(),
        "memoryItems": len(list_obsidian_memory_notes()),
        "lastSpokeAt": LAST_BRAIN_SPOKE_AT.isoformat() if LAST_BRAIN_SPOKE_AT else "",
    }


@app.post("/api/brain/ping")
async def brain_ping(request: Request) -> dict[str, Any]:
    """Admin-only: send a real Ollama chat request and return the raw reply for diagnostics."""
    require_admin(request)
    if not is_brain_configured():
        return {"ok": False, "error": "Brain not configured (missing OOGWAY_OLLAMA_BASE or model)"}

    test_prompt = "Say hello in one short sentence as Oogway the tortoise."
    try:
        payload = {
            "model": OOGWAY_OLLAMA_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": OOGWAY_BRAIN_PERSONALITY},
                {"role": "user", "content": test_prompt},
            ],
            "options": {"temperature": 0.7, "num_predict": 60},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{OOGWAY_OLLAMA_BASE.rstrip('/')}/api/chat", json=payload)
        if resp.status_code >= 400:
            return {"ok": False, "error": f"Ollama returned HTTP {resp.status_code}", "body": resp.text[:300]}
        reply = resp.json().get("message", {}).get("content", "").strip()
        return {"ok": True, "reply": reply, "model": OOGWAY_OLLAMA_MODEL, "ollamaBase": OOGWAY_OLLAMA_BASE}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "ollamaBase": OOGWAY_OLLAMA_BASE}


@app.post("/api/brain/trigger")
async def brain_trigger(request: Request) -> dict[str, Any]:
    """Admin-only: immediately fire the brain loop (mention trigger) bypassing sleep/interval guards."""
    require_admin(request)
    if not OOGWAY_BRAIN_ENABLED:
        return {"ok": False, "error": "OOGWAY_BRAIN_ENABLED is false - enable it in Admin > AI Settings"}
    if not is_brain_configured():
        return {"ok": False, "error": "Brain not configured (missing model or Ollama base URL)"}
    queued = await enqueue_brain_response(trigger="manual")
    if not queued:
        return {"ok": False, "error": "Brain queue unavailable"}
    return {"ok": True, "message": "Brain queued - check chat in a moment"}


@app.post("/api/admin/login")
def admin_login(payload: AdminLoginRequest) -> dict[str, Any]:
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="ADMIN_PASSWORD is not configured")
    if payload.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")
    return {"ok": True, "token": issue_admin_token()}


@app.delete("/api/admin/chat/{message_id}")
async def admin_delete_chat(message_id: str, request: Request) -> dict[str, Any]:
    require_admin(request)
    entries = read_chat_log()
    kept = [item for item in entries if item.get("id") != message_id]
    if len(kept) == len(entries):
        raise HTTPException(status_code=404, detail="Chat message not found")
    write_list_file(CHAT_LOG_PATH, kept, cap=200)
    await broadcast_chat_snapshot()
    return {"ok": True, "deleted": message_id}


@app.post("/api/admin/chat/clear")
async def admin_clear_chat(request: Request) -> dict[str, Any]:
    require_admin(request)
    write_list_file(CHAT_LOG_PATH, [], cap=200)
    await broadcast_chat_snapshot()
    return {"ok": True}


@app.post("/api/admin/reports/reset")
async def admin_reset_reports(payload: AdminReportResetRequest, request: Request) -> dict[str, Any]:
    require_admin(request)

    now = now_utc().isoformat()
    targets = [payload.kind] if payload.kind in {"food", "water"} else ["food", "water"]
    for kind in targets:
        ACTIVE_REPORTS[kind] = {"active": False, "reporter": "", "updatedAt": now}
        CARE_EMPTY_STREAK[kind] = 0
        LAST_CARE_ALERT_AT[kind] = None

    actor = auth_placeholder_username(request, "Admin")
    msg = {
        "id": str(uuid.uuid4()),
        "kind": "report",
        "username": actor,
        "usernameColor": "#ef4444",
        "text": "✅ Admin reset emergency report alerts",
        "textColor": "white",
        "ts": now,
        "report": {
            "kind": payload.kind,
            "active": False,
        },
    }
    append_chat_log(msg)
    await broadcast_chat(msg)

    return {"ok": True, "items": ACTIVE_REPORTS}


class BrainConfigUpdate(BaseModel):
    enabled: bool | None = None
    chatModel: str | None = None
    visionModel: str | None = None
    ollamaBase: str | None = None
    personality: str | None = None
    intervalSeconds: int | None = None
    mentionTrigger: str | None = None


@app.get("/api/admin/brain-config")
def get_brain_config(request: Request) -> dict[str, Any]:
    require_admin(request)
    return {
        "enabled": OOGWAY_BRAIN_ENABLED,
        "chatModel": OOGWAY_OLLAMA_MODEL,
        "visionModel": OOGWAY_OLLAMA_VISION_MODEL,
        "ollamaBase": OOGWAY_OLLAMA_BASE,
        "personality": OOGWAY_BRAIN_PERSONALITY,
        "intervalSeconds": OOGWAY_BRAIN_INTERVAL_SECONDS,
        "mentionTrigger": OOGWAY_BRAIN_MENTION_TRIGGER,
    }


@app.post("/api/admin/brain-config")
def update_brain_config(payload: BrainConfigUpdate, request: Request) -> dict[str, Any]:
    global OOGWAY_BRAIN_ENABLED, OOGWAY_OLLAMA_MODEL, OOGWAY_OLLAMA_VISION_MODEL
    global OOGWAY_OLLAMA_BASE, OOGWAY_BRAIN_PERSONALITY
    global OOGWAY_BRAIN_INTERVAL_SECONDS, OOGWAY_BRAIN_MENTION_TRIGGER
    require_admin(request)

    if payload.enabled is not None:
        OOGWAY_BRAIN_ENABLED = bool(payload.enabled)
    if payload.chatModel is not None and payload.chatModel.strip():
        OOGWAY_OLLAMA_MODEL = payload.chatModel.strip()
    if payload.visionModel is not None and payload.visionModel.strip():
        OOGWAY_OLLAMA_VISION_MODEL = payload.visionModel.strip()
    if payload.ollamaBase is not None and payload.ollamaBase.strip():
        OOGWAY_OLLAMA_BASE = payload.ollamaBase.strip()
    if payload.personality is not None and payload.personality.strip():
        OOGWAY_BRAIN_PERSONALITY = payload.personality.strip()
    if payload.intervalSeconds is not None:
        OOGWAY_BRAIN_INTERVAL_SECONDS = max(45, int(payload.intervalSeconds))
    if payload.mentionTrigger is not None and payload.mentionTrigger.strip():
        OOGWAY_BRAIN_MENTION_TRIGGER = payload.mentionTrigger.strip()

    _save_brain_config()
    brain_log("brain.config.updated", enabled=OOGWAY_BRAIN_ENABLED, chatModel=OOGWAY_OLLAMA_MODEL,
              visionModel=OOGWAY_OLLAMA_VISION_MODEL, ollamaBase=OOGWAY_OLLAMA_BASE,
              intervalSeconds=OOGWAY_BRAIN_INTERVAL_SECONDS, mentionTrigger=OOGWAY_BRAIN_MENTION_TRIGGER)
    return {
        "ok": True,
        "enabled": OOGWAY_BRAIN_ENABLED,
        "chatModel": OOGWAY_OLLAMA_MODEL,
        "visionModel": OOGWAY_OLLAMA_VISION_MODEL,
        "ollamaBase": OOGWAY_OLLAMA_BASE,
        "personality": OOGWAY_BRAIN_PERSONALITY,
        "intervalSeconds": OOGWAY_BRAIN_INTERVAL_SECONDS,
        "mentionTrigger": OOGWAY_BRAIN_MENTION_TRIGGER,
    }


@app.websocket("/ws/chat")
async def chat_ws(
    ws: WebSocket,
    username: str = "",
    textColor: str = "white",
    usernameColor: str = "#a3e635",
) -> None:
    safe_name = canonical_username(username)
    connection_color = "white"
    connection_name_color = usernameColor[:12] if usernameColor.startswith("#") else "#a3e635"
    await ws.accept()
    CHAT_CLIENTS.add(ws)
    CHAT_CLIENT_NAMES[ws] = safe_name
    await broadcast_viewer_count()

    for msg in read_chat_log():
        try:
            await ws.send_json(msg)
        except Exception:
            break

    try:
        while True:
            raw = await ws.receive_text()
            text = ""
            msg_color = connection_color
            msg_name_color = connection_name_color
            with suppress(Exception):
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    text = str(payload.get("text", "")).strip()[:240]
                    msg_color = "white"
                    raw_name_color = str(payload.get("usernameColor", connection_name_color))
                    if raw_name_color.startswith("#"):
                        msg_name_color = raw_name_color[:12]
            if not text:
                text = raw.strip()[:240]
            if not text:
                continue
            msg: dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "kind": "chat",
                "username": safe_name,
                "usernameColor": msg_name_color,
                "text": text,
                "textColor": msg_color,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            append_chat_log(msg)
            await broadcast_chat(msg)
            remember_memory_event(
                topic="chat",
                note=f"{safe_name}: {text[:180]}",
                trigger="chat-message",
                ts=msg["ts"],
            )
            with suppress(Exception):
                append_person_profile_learning(
                    safe_name,
                    f"Chat message: \"{text[:160]}\"",
                    ts=msg["ts"],
                )

            is_self = safe_name.lower() == OOGWAY_BRAIN_NAME.lower()
            if OOGWAY_BRAIN_ENABLED and is_brain_configured() and (not is_self):
                if should_trigger_oogway_mention(text):
                    brain_log(
                        "brain.mention.detected",
                        user=safe_name,
                        text=text[:180],
                    )
                    await enqueue_brain_response(trigger="mention", source_message=msg)
                else:
                    await enqueue_brain_response(trigger="chat", source_message=msg)
    except WebSocketDisconnect:
        CHAT_CLIENTS.discard(ws)
        CHAT_CLIENT_NAMES.pop(ws, None)
        await broadcast_viewer_count()


@app.post("/api/actions")
async def trigger_action(payload: ActionRequest, request: Request) -> dict[str, Any]:
    if not NTFY_TOPIC:
        raise HTTPException(status_code=500, detail="NTFY_TOPIC is not configured")

    action = payload.action
    actor = auth_placeholder_username(request, payload.username)
    message = ACTION_MESSAGE[action]

    try:
        await send_ntfy_message(NTFY_TOPIC, message)
        action_item = append_action_log(action, "sent")
        chat_item = {
            "id": str(uuid.uuid4()),
            "kind": "action",
            "username": actor,
            "usernameColor": "#39ff14",
            "text": f"{EMOJI_BY_ACTION.get(action, '')} {ACTION_TO_CHAT_TEXT[action]}",
            "textColor": "white",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        append_chat_log(chat_item)
        await broadcast_chat(chat_item)
        memory_topic = "feeding" if action == "Request Food" else "watering"
        remember_memory_event(
            topic=memory_topic,
            note=f"{actor} triggered action: {action}",
            trigger="manual-action",
            ts=chat_item["ts"],
        )
    except HTTPException:
        append_action_log(action, "failed")
        raise

    return {"ok": True, "item": action_item}


@app.post("/api/reports/toggle")
async def toggle_report(payload: ReportToggleRequest, request: Request) -> dict[str, Any]:
    if not NTFY_TOPIC:
        raise HTTPException(status_code=500, detail="NTFY_TOPIC is not configured")

    actor = auth_placeholder_username(request, payload.username)
    cfg = REPORT_CONFIG[payload.kind]
    now = datetime.now(timezone.utc).isoformat()

    if payload.active:
        current = ACTIVE_REPORTS[payload.kind]
        if current.get("active"):
            raise HTTPException(status_code=409, detail="This report is locked until an admin resets it")
        ACTIVE_REPORTS[payload.kind] = {
            "active": True,
            "reporter": actor,
            "updatedAt": now,
        }
    else:
        require_admin(request)
        ACTIVE_REPORTS[payload.kind] = {
            "active": False,
            "reporter": "",
            "updatedAt": now,
        }

    if payload.active:
        chat_text = f"{cfg['emoji']} {actor} has reported that Oogway needs {cfg['need']}"
        notify_text = f"{cfg['emoji']} Emergency report from {actor}: Oogway is {cfg['problem']}."
    else:
        chat_text = f"✅ {actor} marked the {cfg['label']} report as resolved"
        notify_text = f"✅ {actor} resolved the {cfg['label']} emergency report."

    chat_item = {
        "id": str(uuid.uuid4()),
        "kind": "report",
        "username": actor,
        "usernameColor": "#ef4444",
        "text": chat_text,
        "textColor": "white",
        "ts": now,
        "report": {
            "kind": payload.kind,
            "active": payload.active,
        },
    }
    append_chat_log(chat_item)
    await broadcast_chat(chat_item)
    await send_ntfy_message(NTFY_TOPIC, notify_text)
    remember_memory_event(
        topic=f"report-{payload.kind}",
        note=f"{actor} set report {payload.kind} active={payload.active}",
        trigger="report-toggle",
        ts=now,
    )

    return {
        "ok": True,
        "report": {
            "kind": payload.kind,
            "active": payload.active,
            "reporter": actor,
            "updatedAt": now,
        },
    }
