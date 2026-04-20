from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

APP_VERSION = "0.1.2"
BASE_DIR = Path(__file__).parent
ACTION_LOG_PATH = Path(os.getenv("ACTIVITY_LOG_PATH", BASE_DIR / "activity_log.json"))
CHAT_LOG_PATH = Path(os.getenv("CHAT_LOG_PATH", BASE_DIR / "chat_log.json"))
STREAM_URL = os.getenv("STREAM_URL", "")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
TZ = os.getenv("TZ", "UTC")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SUN_LAT = os.getenv("SUN_LAT", "40.7128")
SUN_LNG = os.getenv("SUN_LNG", "-74.0060")
BEDTIME_SOON_MINUTES = int(os.getenv("BEDTIME_SOON_MINUTES", "90"))

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


def derive_stream_urls(base: str) -> dict[str, str]:
    """Compute same-origin proxy URLs plus direct MediaMTX URLs."""
    if not base:
        return {}
    base = base.rstrip("/")
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(base)
    host_only = parsed.hostname or ""
    scheme = parsed.scheme or "http"
    path = parsed.path.lstrip("/")

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


def get_stream_origin(base: str) -> str:
    parsed = urlparse(base.rstrip("/"))
    if not parsed.hostname:
        return ""
    scheme = parsed.scheme or "http"
    return f"{scheme}://{parsed.hostname}"


async def proxy_mediastream(mode: str, stream_path: str, request: Request) -> Response:
    if mode not in {"webrtc", "hls"}:
        raise HTTPException(status_code=404, detail="Unknown stream mode")
    if not STREAM_URL:
        raise HTTPException(status_code=503, detail="STREAM_URL is not configured")

    origin = get_stream_origin(STREAM_URL)
    if not origin:
        raise HTTPException(status_code=500, detail="STREAM_URL is invalid")

    upstream_port = 8889 if mode == "webrtc" else 8888
    query = request.url.query
    upstream_url = f"{origin}:{upstream_port}/{stream_path}"
    if query:
        upstream_url += f"?{query}"

    # Forward core request headers so MediaMTX WebRTC signaling endpoints behave correctly.
    fwd_headers = {
        "Accept": request.headers.get("accept", "*/*"),
        "User-Agent": request.headers.get("user-agent", "oogworld-proxy"),
    }
    for h in ["content-type", "authorization", "origin", "referer"]:
        val = request.headers.get(h)
        if val:
            fwd_headers[h] = val

    body = await request.body()

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        upstream = await client.request(
            request.method,
            upstream_url,
            headers=fwd_headers,
            content=body if body else None,
        )

    passthrough = {}
    for key in [
        "content-type",
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
    return Response(content=upstream.content, status_code=upstream.status_code, headers=passthrough)


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


async def send_ntfy_message(topic: str, message: str) -> None:
    url = f"https://ntfy.sh/{topic}"
    headers = {
        "Title": "OogWorld Action",
        "Priority": "default",
        "Tags": "turtle,terrarium",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, content=message.encode("utf-8"), headers=headers)
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Failed to deliver notification to ntfy")


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
    await refresh_daylight_cache(force=True)
    global DAYLIGHT_TASK
    DAYLIGHT_TASK = asyncio.create_task(daylight_refresh_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    global DAYLIGHT_TASK
    if DAYLIGHT_TASK:
        DAYLIGHT_TASK.cancel()
        DAYLIGHT_TASK = None


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
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "tz": TZ,
        "streamConfigured": "yes" if STREAM_URL else "no",
        "ntfyConfigured": "yes" if NTFY_TOPIC else "no",
        "adminConfigured": "yes" if ADMIN_PASSWORD else "no",
        "streams": derive_stream_urls(STREAM_URL),
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
    except WebSocketDisconnect:
        CHAT_CLIENTS.discard(ws)


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
