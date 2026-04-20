from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

APP_VERSION = "0.0.1"
BASE_DIR = Path(__file__).parent
ACTION_LOG_PATH = Path(os.getenv("ACTIVITY_LOG_PATH", BASE_DIR / "activity_log.json"))
CHAT_LOG_PATH = Path(os.getenv("CHAT_LOG_PATH", BASE_DIR / "chat_log.json"))
STREAM_URL = os.getenv("STREAM_URL", "")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
TZ = os.getenv("TZ", "UTC")

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


app = FastAPI(title="OogWorld", version=APP_VERSION)
CHAT_CLIENTS: set[WebSocket] = set()


def derive_stream_urls(base: str) -> dict[str, str]:
    """Compute MediaMTX URLs from a single base stream URL."""
    if not base:
        return {}
    base = base.rstrip("/")
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(base)
    host_only = parsed.hostname or ""
    scheme = parsed.scheme or "http"
    path = parsed.path

    def swap_port(p: int) -> str:
        return urlunparse((scheme, f"{host_only}:{p}", path, "", "", ""))

    webrtc = swap_port(8889) + "/"
    hls = swap_port(8888) + "/index.m3u8"
    rtsp = f"rtsp://{host_only}:8554{path}"
    return {"webrtc": webrtc, "hls": hls, "rtsp": rtsp}


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


@app.on_event("startup")
def startup() -> None:
    ensure_list_file(ACTION_LOG_PATH)
    ensure_list_file(CHAT_LOG_PATH)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "tz": TZ,
        "streamConfigured": "yes" if STREAM_URL else "no",
        "ntfyConfigured": "yes" if NTFY_TOPIC else "no",
        "streams": derive_stream_urls(STREAM_URL),
    }


@app.get("/api/activity")
def activity() -> dict[str, list[dict[str, Any]]]:
    return {"items": read_action_log()}


@app.get("/api/chat/history")
def chat_history() -> dict[str, list[dict[str, Any]]]:
    return {"items": read_chat_log()}


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
