from __future__ import annotations

import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

APP_VERSION = "0.0.0"
BASE_DIR = Path(__file__).parent
LOG_PATH = Path(os.getenv("ACTIVITY_LOG_PATH", BASE_DIR / "activity_log.json"))
STREAM_URL = os.getenv("STREAM_URL", "")  # Base MediaMTX URL e.g. http://host:8889/path/
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
TZ = os.getenv("TZ", "UTC")


def derive_stream_urls(base: str) -> dict[str, str]:
    """Compute all MediaMTX stream URLs from the base WebRTC/HLS URL."""
    if not base:
        return {}
    base = base.rstrip("/")
    # Detect scheme+host, swap ports for MediaMTX defaults
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(base)
    host_only = parsed.hostname or ""
    scheme = parsed.scheme
    path = parsed.path

    def swap_port(p: int) -> str:
        return urlunparse((scheme, f"{host_only}:{p}", path, "", "", ""))

    webrtc = swap_port(8889) + "/"
    hls = swap_port(8888) + "/index.m3u8"
    rtsp = f"rtsp://{host_only}:8554{path}"
    return {"webrtc": webrtc, "hls": hls, "rtsp": rtsp}


STREAM_URLS = derive_stream_urls(STREAM_URL)

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
CHAT_HISTORY: deque[dict[str, str]] = deque(maxlen=50)
CHAT_CLIENTS: set[WebSocket] = set()

ACTION_MESSAGE: dict[str, str] = {
    "Request Food": "OogWorld request: Please feed Oogway.",
    "Refill Water": "OogWorld request: Please refill Oogway's water.",
}


class ActionRequest(BaseModel):
    action: Literal["Request Food", "Refill Water"]


app = FastAPI(title="OogWorld", version=APP_VERSION)


def ensure_log_file() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        LOG_PATH.write_text("[]", encoding="utf-8")


def read_log() -> list[dict[str, Any]]:
    ensure_log_file()
    try:
        payload = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = []
    if not isinstance(payload, list):
        return []
    return payload[-5:]


def write_log(entries: list[dict[str, Any]]) -> None:
    ensure_log_file()
    trimmed = entries[-5:]
    LOG_PATH.write_text(json.dumps(trimmed, indent=2), encoding="utf-8")


def add_log(action: str, delivery: str) -> dict[str, Any]:
    entries = read_log()
    item = {
        "action": action,
        "delivery": delivery,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(item)
    write_log(entries)
    return item


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
    ensure_log_file()


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
        "streams": STREAM_URLS,
    }


@app.websocket("/ws/chat")
async def chat_ws(ws: WebSocket, username: str = "") -> None:
    safe_name = (username.strip()[:24] or "Anonymous").replace("<", "").replace(">", "")
    await ws.accept()
    CHAT_CLIENTS.add(ws)
    # Deliver history to the new joiner
    for msg in list(CHAT_HISTORY):
        try:
            await ws.send_json(msg)
        except Exception:
            break
    try:
        while True:
            raw = await ws.receive_text()
            text = raw.strip()[:200]
            if not text:
                continue
            msg: dict[str, str] = {
                "username": safe_name,
                "text": text,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            CHAT_HISTORY.append(msg)
            dead: set[WebSocket] = set()
            for client in list(CHAT_CLIENTS):
                try:
                    await client.send_json(msg)
                except Exception:
                    dead.add(client)
            CHAT_CLIENTS -= dead
    except WebSocketDisconnect:
        CHAT_CLIENTS.discard(ws)


@app.get("/api/activity")
def activity() -> dict[str, list[dict[str, Any]]]:
    return {"items": read_log()}


@app.post("/api/actions")
async def trigger_action(payload: ActionRequest) -> dict[str, Any]:
    if not NTFY_TOPIC:
        raise HTTPException(status_code=500, detail="NTFY_TOPIC is not configured")

    action = payload.action
    message = ACTION_MESSAGE[action]

    try:
        await send_ntfy_message(NTFY_TOPIC, message)
        entry = add_log(action, "sent")
    except HTTPException:
        add_log(action, "failed")
        raise

    return {"ok": True, "item": entry}
