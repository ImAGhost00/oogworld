from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

APP_VERSION = "0.0.0"
BASE_DIR = Path(__file__).parent
LOG_PATH = Path(os.getenv("ACTIVITY_LOG_PATH", BASE_DIR / "activity_log.json"))
STREAM_URL = os.getenv("STREAM_URL", "")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
TZ = os.getenv("TZ", "UTC")

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
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "tz": TZ,
        "streamUrl": STREAM_URL,
        "streamConfigured": "yes" if STREAM_URL else "no",
        "ntfyConfigured": "yes" if NTFY_TOPIC else "no",
    }


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
