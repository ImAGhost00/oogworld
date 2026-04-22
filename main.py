from __future__ import annotations

import asyncio
import base64
import json
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
ACTION_LOG_PATH = Path(os.getenv("ACTIVITY_LOG_PATH", BASE_DIR / "activity_log.json"))
CHAT_LOG_PATH = Path(os.getenv("CHAT_LOG_PATH", BASE_DIR / "chat_log.json"))
STREAM_URL_PRIMARY = os.getenv("STREAM_URL_PRIMARY", os.getenv("STREAM_URL", ""))
STREAM_URL_SECONDARY = os.getenv("STREAM_URL_SECONDARY", "")
STREAM_LABEL_PRIMARY = os.getenv("STREAM_LABEL_PRIMARY", "Hut Cam")
STREAM_LABEL_SECONDARY = os.getenv("STREAM_LABEL_SECONDARY", "Water Bowl Cam")
STREAM_RESOLUTION_PRIMARY = os.getenv("STREAM_RESOLUTION_PRIMARY", "1080p")
STREAM_RESOLUTION_SECONDARY = os.getenv("STREAM_RESOLUTION_SECONDARY", "720p")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
TZ = os.getenv("TZ", "UTC")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SUN_LAT = os.getenv("SUN_LAT", "40.7128")
SUN_LNG = os.getenv("SUN_LNG", "-74.0060")
BEDTIME_SOON_MINUTES = int(os.getenv("BEDTIME_SOON_MINUTES", "90"))
OOGWAY_BRAIN_ENABLED = os.getenv("OOGWAY_BRAIN_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OOGWAY_BRAIN_NAME = os.getenv("OOGWAY_BRAIN_NAME", "Oogway")
OOGWAY_BRAIN_PROVIDER = os.getenv("OOGWAY_BRAIN_PROVIDER", "ollama").strip().lower()
OOGWAY_BRAIN_MODEL = os.getenv("OOGWAY_BRAIN_MODEL", "qwen2.5:3b")
OOGWAY_OLLAMA_BASE = os.getenv("OOGWAY_OLLAMA_BASE", "http://ollama:11434").strip()
OOGWAY_OLLAMA_MODEL = os.getenv("OOGWAY_OLLAMA_MODEL", OOGWAY_BRAIN_MODEL).strip()
OOGWAY_OLLAMA_VISION_MODEL = os.getenv("OOGWAY_OLLAMA_VISION_MODEL", "moondream:latest").strip()
OOGWAY_BRAIN_PERSONALITY = os.getenv(
    "OOGWAY_BRAIN_PERSONALITY",
    "You are Oogway, a warm and observant tortoise who talks like a living terrarium companion.",
)
OOGWAY_BRAIN_INTERVAL_SECONDS = max(45, int(os.getenv("OOGWAY_BRAIN_INTERVAL_SECONDS", "300")))
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
OOGWAY_TEXTS_STYLE = os.getenv("OOGWAY_TEXTS_STYLE", "auto").strip().lower()
OOGWAY_TEXTS_ANGER_AFTER_SECONDS = max(
    900,
    int(os.getenv("OOGWAY_TEXTS_ANGER_AFTER_SECONDS", "14400")),
)
OOGWAY_OBSIDIAN_VAULT_PATH = Path(os.getenv("OOGWAY_OBSIDIAN_VAULT_PATH", BASE_DIR / "obsidian"))
OOGWAY_OBSIDIAN_MEMORY_FOLDER = os.getenv("OOGWAY_OBSIDIAN_MEMORY_FOLDER", "Oogway Memory").strip() or "Oogway Memory"
OOGWAY_BRAIN_MEMORY_PATH = Path(os.getenv("OOGWAY_BRAIN_MEMORY_PATH", BASE_DIR / "brain_memory.json"))
OOGWAY_BRAIN_MEMORY_CAP = max(30, int(os.getenv("OOGWAY_BRAIN_MEMORY_CAP", "300")))
OOGWAY_BRAIN_CONTEXT_CHAT_CAP = max(8, int(os.getenv("OOGWAY_BRAIN_CONTEXT_CHAT_CAP", "24")))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_API_BASE = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
OOGWAY_TEXTS_TOPIC = os.getenv("OOGWAY_TEXTS_TOPIC", "oogworldtexts").strip()

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
ADMIN_TOKENS: dict[str, datetime] = {}
DAYLIGHT_TASK: asyncio.Task[Any] | None = None
BRAIN_TASK: asyncio.Task[Any] | None = None
BRAIN_LOCK = asyncio.Lock()
LAST_BRAIN_SPOKE_AT: datetime | None = None
LAST_BRAIN_MOVEMENT_AT: datetime | None = None
LAST_BRAIN_MOTION_PROBES: dict[str, bytes] = {}
LAST_BRAIN_CARE_CHECK_AT: datetime | None = None
CARE_EMPTY_STREAK: dict[str, int] = {"food": 0, "water": 0}
LAST_CARE_ALERT_AT: dict[str, datetime | None] = {"food": None, "water": None}
LAST_EATING_CHECK_AT: datetime | None = None
LAST_EATING_REACT_AT: datetime | None = None
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


def brain_provider() -> str:
    provider = (OOGWAY_BRAIN_PROVIDER or "ollama").strip().lower()
    return provider if provider in {"ollama", "groq"} else "ollama"


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


def write_obsidian_memory_note(item: dict[str, Any]) -> None:
    ts = str(item.get("ts") or datetime.now(timezone.utc).isoformat())
    topic = str(item.get("topic") or "memory").strip() or "memory"
    trigger = str(item.get("trigger") or "periodic")
    note_text = str(item.get("note") or "")
    if not note_text:
        return

    directory = ensure_obsidian_memory_dir()
    short_id = str(uuid.uuid4())[:8]
    date_prefix = ts[:10]
    note_title = f"{date_prefix} {topic} {short_id}"
    note_path = directory / f"{slugify_note_title(note_title)}.md"

    recalls = search_obsidian_memories(f"{topic} {note_text}", limit=3)
    links = [f"[[Topic - {topic.title()}]]"]
    for recall in recalls:
        candidate = recall.get("title", "")
        if candidate and candidate != note_title:
            links.append(f"[[{candidate}]]")
    links = list(dict.fromkeys(links))[:5]

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


def read_chat_log() -> list[dict[str, Any]]:
    return read_list_file(CHAT_LOG_PATH, cap=200)


def append_chat_log(item: dict[str, Any]) -> dict[str, Any]:
    entries = read_chat_log()
    entries.append(item)
    write_list_file(CHAT_LOG_PATH, entries, cap=200)
    return item


def read_brain_memory() -> list[dict[str, Any]]:
    return read_list_file(OOGWAY_BRAIN_MEMORY_PATH, cap=OOGWAY_BRAIN_MEMORY_CAP)


def append_brain_memory(item: dict[str, Any]) -> dict[str, Any]:
    entries = read_brain_memory()
    entries.append(item)
    write_list_file(OOGWAY_BRAIN_MEMORY_PATH, entries, cap=OOGWAY_BRAIN_MEMORY_CAP)
    with suppress(Exception):
        write_obsidian_memory_note(item)
    return item


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


async def broadcast_viewer_count() -> None:
    count = len(CHAT_CLIENTS)
    dead: set[WebSocket] = set()
    for client in list(CHAT_CLIENTS):
        try:
            await client.send_json({"kind": "viewer_count", "count": count})
        except Exception:
            dead.add(client)
    CHAT_CLIENTS.difference_update(dead)


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
    provider = brain_provider()
    if provider == "groq":
        return bool(GROQ_API_KEY)
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
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=12)
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
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=12)
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
    global LAST_BRAIN_MOVEMENT_AT

    targets = get_brain_snapshot_targets()
    if not targets:
        return False

    probe_values = await asyncio.gather(
        *(capture_stream_motion_probe(target["hlsUrl"]) for target in targets),
        return_exceptions=True,
    )

    motion_detected = False
    for target, probe in zip(targets, probe_values):
        if isinstance(probe, Exception) or not probe:
            continue
        key = target["key"]
        previous = LAST_BRAIN_MOTION_PROBES.get(key, b"")
        if previous:
            score = motion_score(previous, probe)
            if score >= OOGWAY_BRAIN_MOTION_THRESHOLD:
                motion_detected = True
        LAST_BRAIN_MOTION_PROBES[key] = probe

    if motion_detected:
        LAST_BRAIN_MOVEMENT_AT = now_utc()

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


def build_oogway_prompt(trigger: str, source_message: dict[str, Any] | None) -> str:
    recents = read_chat_log()[-OOGWAY_BRAIN_CONTEXT_CHAT_CAP:]
    memory = read_brain_memory()[-14:]
    recent_lines = [
        f"[{msg.get('ts', '')}] {msg.get('username', 'Anonymous')}: {msg.get('text', '')}"
        for msg in recents
        if msg.get("text")
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

    if trigger == "mention" and source_message:
        trigger_text = (
            "You were mentioned in chat. Reply directly to the user in 1-3 short sentences, "
            "friendly, alive, and specific."
        )
        mention_line = (
            f"Mention came from {source_message.get('username', 'Anonymous')}: "
            f"{source_message.get('text', '')}"
        )
    else:
        trigger_text = (
            "Write a short spontaneous update as Oogway. Mention what you notice from the camera if visible, "
            "or share a brief thought about your day with humans/cats/terrarium."
        )
        mention_line = "No direct mention in this turn."

    camera_targets = get_brain_snapshot_targets()
    camera_labels = ", ".join(target["label"] for target in camera_targets) or "(none configured)"

    return "\n".join(
        [
            trigger_text,
            mention_line,
            f"Camera coverage this turn: {camera_labels}",
            "",
            "Vision priorities:",
            "- Watch for movement: poking head out, walking, changing position, active vs resting.",
            "- Watch care events: fresh food added, water bowl refill, visible eating or drinking.",
            "- If uncertain, say so briefly instead of making up details.",
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
            "Rules: keep under 240 chars, no roleplay markers, no markdown.",
        ]
    )


def _extract_data_url_base64(data_url: str) -> str:
    if not data_url or "," not in data_url:
        return ""
    return data_url.split(",", 1)[1].strip()


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
    system_prompt = (
        f"{OOGWAY_BRAIN_PERSONALITY} "
        "You are in the OogWorld live chat. Be warm, brief, and grounded in current context."
    )

    image_payload: list[str] = []
    for snapshot in snapshots[:2]:
        encoded = _extract_data_url_base64(snapshot.get("dataUrl", ""))
        if encoded:
            image_payload.append(encoded)

    model_name = OOGWAY_OLLAMA_VISION_MODEL if (image_payload and OOGWAY_OLLAMA_VISION_MODEL) else OOGWAY_OLLAMA_MODEL
    user_msg: dict[str, Any] = {"role": "user", "content": prompt_text}
    if image_payload and OOGWAY_OLLAMA_VISION_MODEL:
        user_msg["images"] = image_payload

    payload = {
        "model": model_name,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            user_msg,
        ],
        "options": {"temperature": 0.7, "num_predict": 160},
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(f"{OOGWAY_OLLAMA_BASE.rstrip('/')}/api/chat", json=payload)
        if resp.status_code >= 400:
            return ""
        data = resp.json()
        content = data.get("message", {}).get("content", "")
        return str(content).strip()[:240]
    except Exception:
        return ""


async def call_groq_for_oogway(prompt_text: str, snapshots: list[dict[str, str]]) -> str:
    system_prompt = (
        f"{OOGWAY_BRAIN_PERSONALITY} "
        "You are in the OogWorld live chat. Be warm, brief, and grounded in current context. "
        "You slowly develop memory and relationships over time. "
        "When images are provided, treat them as current camera views and prioritize concrete visual observations."
    )

    user_content: list[dict[str, Any]] = [{"type": "text", "text": prompt_text}]
    for snapshot in snapshots:
        user_content.append({"type": "text", "text": f"Camera view: {snapshot['label']}"})
        user_content.append({"type": "image_url", "image_url": {"url": snapshot["dataUrl"]}})

    payload = {
        "model": OOGWAY_BRAIN_MODEL,
        "temperature": 0.7,
        "max_tokens": 140,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{GROQ_API_BASE.rstrip('/')}/chat/completions", json=payload, headers=headers)
    if resp.status_code >= 400:
        return ""

    data = resp.json()
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    if isinstance(content, list):
        parts = [str(part.get("text", "")) for part in content if isinstance(part, dict)]
        content = " ".join(parts)
    return str(content).strip()[:240]


async def call_oogway_brain_model(prompt_text: str, snapshots: list[dict[str, str]]) -> str:
    if brain_provider() == "groq":
        return await call_groq_for_oogway(prompt_text, snapshots)
    return await call_ollama_for_oogway(prompt_text, snapshots)


async def vision_json_classify(
    snapshots: list[dict[str, str]],
    system_prompt: str,
    task_prompt: str,
    keys: list[str],
) -> dict[str, bool]:
    defaults = {key: False for key in keys}
    if not snapshots:
        return defaults

    provider = brain_provider()
    if provider == "groq":
        if not GROQ_API_KEY:
            return defaults
        user_content: list[dict[str, Any]] = [{"type": "text", "text": task_prompt}]
        for snapshot in snapshots:
            user_content.append({"type": "text", "text": f"Camera view: {snapshot['label']}"})
            user_content.append({"type": "image_url", "image_url": {"url": snapshot["dataUrl"]}})

        payload = {
            "model": OOGWAY_BRAIN_MODEL,
            "temperature": 0.1,
            "max_tokens": 120,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{GROQ_API_BASE.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
            if resp.status_code >= 400:
                return defaults
            content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = _parse_json_from_text(str(content))
            if not parsed:
                return defaults
            return {key: bool(parsed.get(key, False)) for key in keys}
        except Exception:
            return defaults

    if not OOGWAY_OLLAMA_VISION_MODEL:
        return defaults

    images = [_extract_data_url_base64(snap.get("dataUrl", "")) for snap in snapshots[:3]]
    images = [img for img in images if img]
    if not images:
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
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(f"{OOGWAY_OLLAMA_BASE.rstrip('/')}/api/chat", json=payload)
        if resp.status_code >= 400:
            return defaults
        content = resp.json().get("message", {}).get("content", "")
        parsed = _parse_json_from_text(str(content))
        if not parsed:
            return defaults
        return {key: bool(parsed.get(key, False)) for key in keys}
    except Exception:
        return defaults


async def evaluate_care_needs(snapshots: list[dict[str, str]]) -> dict[str, bool]:
    return await vision_json_classify(
        snapshots=snapshots,
        system_prompt="You classify food and water bowl visibility from terrarium camera images.",
        task_prompt=(
            "Inspect these terrarium camera views and return only strict JSON with this shape: "
            '{"food_empty": boolean, "water_empty": boolean}. '
            "Mark true only when it visibly appears empty or nearly empty. If unsure, use false."
        ),
        keys=["food_empty", "water_empty"],
    )


async def evaluate_eating_drinking(snapshots: list[dict[str, str]]) -> dict[str, bool]:
    return await vision_json_classify(
        snapshots=snapshots,
        system_prompt="You classify tortoise feeding and drinking behaviour from terrarium camera images.",
        task_prompt=(
            "Look at these terrarium camera images and return only strict JSON: "
            '{"eating": boolean, "drinking": boolean}. '
            "Set eating=true only if the tortoise is clearly and actively eating food right now. "
            "Set drinking=true only if the tortoise is clearly and actively drinking water right now. "
            "If the tortoise is not visible, not near food/water, or the activity is ambiguous, use false."
        ),
        keys=["eating", "drinking"],
    )


_EATING_REACTIONS: list[str] = [
    "mmm delicious~",
    "nom nom nom",
    "*chew chew*",
    "oh that hits the spot",
    "so good... so good",
    "getting my nutrients",
    "*munch munch*",
    "lunch time",
]

_DRINKING_REACTIONS: list[str] = [
    "*gulp* *gulp*",
    "ah refreshing",
    "*sip*",
    "good water today",
    "*slurp*",
    "staying hydrated",
    "nothing like a cold drink",
]


async def run_brain_eating_check() -> None:
    global LAST_EATING_CHECK_AT, LAST_EATING_REACT_AT, LAST_BRAIN_SPOKE_AT

    if not OOGWAY_BRAIN_ENABLED or not is_brain_configured():
        return

    if LAST_EATING_CHECK_AT:
        elapsed = (now_utc() - LAST_EATING_CHECK_AT).total_seconds()
        if elapsed < OOGWAY_BRAIN_EATING_CHECK_INTERVAL_SECONDS:
            return

    LAST_EATING_CHECK_AT = now_utc()

    if not LAST_BRAIN_MOVEMENT_AT:
        return
    if (now_utc() - LAST_BRAIN_MOVEMENT_AT).total_seconds() > OOGWAY_BRAIN_MOVEMENT_WINDOW_SECONDS:
        return

    if LAST_EATING_REACT_AT:
        if (now_utc() - LAST_EATING_REACT_AT).total_seconds() < OOGWAY_BRAIN_EATING_REACT_COOLDOWN_SECONDS:
            return

    snapshots = await capture_brain_snapshots_data_urls()
    if not snapshots:
        return

    result = await evaluate_eating_drinking(snapshots)

    reaction: str | None = None
    if result.get("drinking"):
        reaction = random.choice(_DRINKING_REACTIONS)
    elif result.get("eating"):
        reaction = random.choice(_EATING_REACTIONS)

    if not reaction:
        return

    msg = build_chat_item(
        username=OOGWAY_BRAIN_NAME,
        username_color=BRAIN_USERNAME_COLOR,
        text=reaction,
        kind="chat",
    )
    append_chat_log(msg)
    await broadcast_chat(msg)
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
    global LAST_BRAIN_CARE_CHECK_AT

    if not OOGWAY_BRAIN_ENABLED or not is_brain_configured():
        return

    if LAST_BRAIN_CARE_CHECK_AT:
        elapsed = (now_utc() - LAST_BRAIN_CARE_CHECK_AT).total_seconds()
        if elapsed < OOGWAY_BRAIN_CARE_CHECK_INTERVAL_SECONDS:
            return

    LAST_BRAIN_CARE_CHECK_AT = now_utc()

    movement_recent = await refresh_brain_motion_state()
    snapshots = await capture_brain_snapshots_data_urls()
    care_eval = await evaluate_care_needs(snapshots)

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
    topic = "routine"
    source_text = (source_message or {}).get("text", "")
    lowered = source_text.lower()
    if "cat" in lowered or "cats" in lowered:
        topic = "cats"
    elif "feed" in lowered or "food" in lowered:
        topic = "feeding"
    elif "water" in lowered or "humid" in lowered or "humidity" in lowered:
        topic = "care"
    elif trigger == "mention":
        topic = "human-chat"

    append_brain_memory(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "note": f"{(source_message or {}).get('username', 'Someone')}: {source_text[:140]} | Oogway: {reply_text[:140]}",
            "trigger": trigger,
        }
    )


def brain_awake_now() -> bool:
    status = daylight_status_payload()
    return not status.get("asleep", False)


def should_trigger_oogway_mention(text: str) -> bool:
    trigger = (OOGWAY_BRAIN_MENTION_TRIGGER or "@oogway").strip().lower()
    if not trigger:
        trigger = "@oogway"
    return trigger in text.lower()


async def run_oogway_brain(trigger: str, source_message: dict[str, Any] | None = None) -> None:
    global LAST_BRAIN_SPOKE_AT

    if not OOGWAY_BRAIN_ENABLED or not is_brain_configured():
        return

    async with BRAIN_LOCK:
        with suppress(Exception):
            await refresh_daylight_cache(force=False)

        if not brain_awake_now():
            return

        if trigger == "periodic" and LAST_BRAIN_SPOKE_AT:
            elapsed = (now_utc() - LAST_BRAIN_SPOKE_AT).total_seconds()
            if elapsed < OOGWAY_BRAIN_INTERVAL_SECONDS:
                return

        movement_recent = await refresh_brain_motion_state()
        if trigger == "periodic" and not movement_recent:
            return

        prompt_text = build_oogway_prompt(trigger, source_message)
        snapshots = await capture_brain_snapshots_data_urls()
        reply = await call_oogway_brain_model(prompt_text, snapshots)
        if not reply:
            return

        msg = build_chat_item(
            username=OOGWAY_BRAIN_NAME,
            username_color=BRAIN_USERNAME_COLOR,
            text=reply,
            kind="chat",
        )
        append_chat_log(msg)
        await broadcast_chat(msg)
        remember_interaction(trigger, source_message, reply)
        LAST_BRAIN_SPOKE_AT = now_utc()


async def oogway_brain_loop() -> None:
    await asyncio.sleep(20)
    while True:
        try:
            await run_brain_care_check()
            await run_brain_eating_check()
            await run_oogway_brain(trigger="periodic")
        except Exception:
            # Keep loop alive even if upstream LLM/camera calls fail.
            pass
        await asyncio.sleep(min(
            OOGWAY_BRAIN_INTERVAL_SECONDS,
            OOGWAY_BRAIN_CARE_CHECK_INTERVAL_SECONDS,
            OOGWAY_BRAIN_EATING_CHECK_INTERVAL_SECONDS,
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


@app.on_event("startup")
async def startup() -> None:
    ensure_list_file(ACTION_LOG_PATH)
    ensure_list_file(CHAT_LOG_PATH)
    ensure_list_file(OOGWAY_BRAIN_MEMORY_PATH)
    await refresh_daylight_cache(force=True)
    global DAYLIGHT_TASK, BRAIN_TASK
    DAYLIGHT_TASK = asyncio.create_task(daylight_refresh_loop())
    if OOGWAY_BRAIN_ENABLED and is_brain_configured():
        BRAIN_TASK = asyncio.create_task(oogway_brain_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    global DAYLIGHT_TASK, BRAIN_TASK
    if DAYLIGHT_TASK:
        DAYLIGHT_TASK.cancel()
        DAYLIGHT_TASK = None
    if BRAIN_TASK:
        BRAIN_TASK.cancel()
        BRAIN_TASK = None


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
        "brainModel": OOGWAY_BRAIN_MODEL,
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
        "model": OOGWAY_BRAIN_MODEL,
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
        "memoryItems": len(read_brain_memory()),
        "lastSpokeAt": LAST_BRAIN_SPOKE_AT.isoformat() if LAST_BRAIN_SPOKE_AT else "",
    }


@app.post("/api/admin/login")
def admin_login(payload: AdminLoginRequest) -> dict[str, Any]:
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="ADMIN_PASSWORD is not configured")
    if payload.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")
    return {"ok": True, "token": issue_admin_token()}


@app.delete("/api/admin/chat/{message_id}")
def admin_delete_chat(message_id: str, request: Request) -> dict[str, Any]:
    require_admin(request)
    entries = read_chat_log()
    kept = [item for item in entries if item.get("id") != message_id]
    if len(kept) == len(entries):
        raise HTTPException(status_code=404, detail="Chat message not found")
    write_list_file(CHAT_LOG_PATH, kept, cap=200)
    return {"ok": True, "deleted": message_id}


@app.post("/api/admin/chat/clear")
def admin_clear_chat(request: Request) -> dict[str, Any]:
    require_admin(request)
    write_list_file(CHAT_LOG_PATH, [], cap=200)
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


@app.websocket("/ws/chat")
async def chat_ws(
    ws: WebSocket,
    username: str = "",
    textColor: str = "white",
    usernameColor: str = "#a3e635",
) -> None:
    safe_name = canonical_username(username)
    safe_color = "black" if textColor == "black" else "white"
    safe_name_color = usernameColor[:12] if usernameColor.startswith("#") else "#a3e635"
    await ws.accept()
    CHAT_CLIENTS.add(ws)
    await broadcast_viewer_count()

    for msg in read_chat_log():
        try:
            await ws.send_json(msg)
        except Exception:
            break

    try:
        while True:
            raw = await ws.receive_text()
            text = raw.strip()[:240]
            if not text:
                continue
            msg: dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "kind": "chat",
                "username": safe_name,
                "usernameColor": safe_name_color,
                "text": text,
                "textColor": safe_color,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            append_chat_log(msg)
            await broadcast_chat(msg)

            is_self = safe_name.lower() == OOGWAY_BRAIN_NAME.lower()
            if OOGWAY_BRAIN_ENABLED and is_brain_configured() and (not is_self) and should_trigger_oogway_mention(text):
                asyncio.create_task(run_oogway_brain(trigger="mention", source_message=msg))
    except WebSocketDisconnect:
        CHAT_CLIENTS.discard(ws)
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

    return {
        "ok": True,
        "report": {
            "kind": payload.kind,
            "active": payload.active,
            "reporter": actor,
            "updatedAt": now,
        },
    }
