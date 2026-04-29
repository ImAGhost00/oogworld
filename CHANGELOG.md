# Changelog

All notable changes to this project are documented in this file.

## [0.3.2] - 2026-04-29
- Added **AI Vision State** panel to the admin modal: shows per-camera boolean observations (visible, basking, sleeping, eating, drinking, in hut, near food/water, fallen over, scene lit), last validation timestamp, and editable summary/location/activity fields.
- Added `GET /api/admin/visual-state`, `POST /api/admin/visual-state` (override), and `POST /api/admin/visual-state/refresh` (fresh snapshot + validation) backend endpoints.
- Admin can now correct wrong AI observations live without waiting for the next vision cycle.

## [0.3.1] - 2026-04-29
- Disabled Oogway automatic chat by default so he only responds when mentioned or manually triggered unless explicitly re-enabled.
- Added admin-configurable `OOGWAY_BRAIN_AUTO_CHAT_ENABLED` runtime setting and persisted it in brain config.
- Changed bowl and behavior vision checks to queue snapshots one image at a time so single-image Ollama models like `moondream:latest` stop failing on dual-camera payloads.
- Aligned Compose defaults to CPU-friendlier Ollama models: `qwen2.5:3b` for chat and `moondream:latest` for vision.
- Bumped backend/docs version to `0.3.1`.

## [0.3.0] - 2026-04-21
- Added Oogway Brain feature in `main.py` with Groq-backed chat generation and camera-vision support.
- Added mention-triggered responses when users include `@oogway` (configurable trigger token).
- Added periodic autonomous chat while Oogway is awake based on existing sunrise/sunset logic.
- Added persistent long-term memory file (`brain_memory.json`) so Oogway can retain interaction context.
- Added brain status endpoint: `GET /api/brain/status`.
- Extended health payload with brain configuration flags and model info.
- Added Docker environment settings for brain behavior, memory, and Groq API integration.
- Updated app container image to include `ffmpeg` for HLS snapshot capture used by multimodal prompts.
- Bumped backend version to `0.3.0` and synchronized README docs.

## [0.2.2] - 2026-04-20
- Added integration-ready React component files at `components/ui/material-ui-dropdown-menu.tsx` and `components/ui/demo.tsx`.
- Included the provided Material-style Radix dropdown menu implementation and demo usage.
- Documented version sync for frontend component scaffold update while current repo remains FastAPI-first.

## [0.2.1] - 2026-04-20
- Removed the welcome tip window and about tip window from the dashboard.
- Updated chat input placeholder from `Type a note...` to `Send a message`.
- Redesigned the UI to feel more like a streaming platform with improved channel hierarchy and visual structure.
- Applied the 21st.dev Nature palette across the interface.
- Kept the automatic moon-and-stars night mode behavior for Oogway's asleep state.
- Updated backend app version to `0.2.1` and synchronized README version/features.

## [0.2.0] - 2026-04-20
- Updated branding to present `www.ghostworld.dev` as the base identity with an OogWorld takeover visual treatment.
- Added two closable dashboard tip cards: one for welcome-to-chat guidance and one explaining the app.
- Added automatic night mode that activates when Oogway is asleep, including moon-and-stars visual atmosphere.
- Preserved daytime styling and automatically exits night mode when Oogway wakes.
- Updated backend app version to `0.2.0` and synchronized README version/features.

## [0.1.2] - 2026-04-20
- Fixed embedded stream `Stream not found` issue by preferring `webrtcDirect` URL for the in-page iframe player (same working path as `Open Player`).
- Kept `/media/webrtc/...` as fallback path for compatibility.
- Updated backend app version to `0.1.2` and synchronized README version.

## [0.1.1] - 2026-04-20
- Fixed stream proxy `405 Method Not Allowed` issue by allowing `/media/...` routes to accept WebRTC signaling methods (`POST`, `PATCH`, `DELETE`, `OPTIONS`, plus `GET`/`HEAD`).
- Updated proxy forwarding to pass through incoming HTTP method, request body, and signaling-relevant headers instead of forcing `GET`.
- Added passthrough of key upstream response headers (including CORS and `Location`) for MediaMTX WebRTC negotiation compatibility.

## [0.1.0] - 2026-04-20
- Reworked emergency reporting UX: replaced chat-area emergency button with a report icon near the video header using the new warning icon asset.
- Added compact report modal with `Need Food` and `Need Water` options.
- Added report locking behavior: once submitted, report stays locked until admin reset.
- Added red emergency banner text pattern `USER has reported that Oogway needs XXX` with live elapsed timer since report timestamp.
- Added password-protected admin panel flow backed by `ADMIN_PASSWORD` environment variable.
- Added admin authentication endpoint (`POST /api/admin/login`) issuing short-lived admin tokens.
- Added admin moderation endpoints:
	- `POST /api/admin/reports/reset` (reset food/water/all report locks)
	- `DELETE /api/admin/chat/{message_id}` (delete single chat message)
	- `POST /api/admin/chat/clear` (clear chat log)
- Added static file hosting for `/images` so UI icon assets are served directly by FastAPI.
- Added sunrise/sunset scheduling integration using `https://sunrise-sunset.org/api`.
- Added new daylight endpoint (`GET /api/daylight`) with cached periodic refresh to represent heatlamp on/off state.
- Added bedtime UI banners:
	- Countdown banner near sunset.
	- Overnight banner text: `oogway is asleep, his heatlamp will turn on in XX:XX`.
- Added new environment variables: `ADMIN_PASSWORD`, `SUN_LAT`, `SUN_LNG`, and `BEDTIME_SOON_MINUTES`.
- Updated backend app version to `0.1.0` and synchronized README version/docs.

## [0.0.8] - 2026-04-20
- Rearchitected for split deployment: MediaMTX runs natively on Windows machine (captures C922 via DShow), OogWorld backend runs on server (connects via network RTSP/WebRTC).
- Updated `mediamtx.yml` to use libx264 ultrafast (stable encoder for older Intel iGPU).
- Docker-compose now accepts `STREAM_URL` env var; default assumes localhost (modify for remote Windows IP).
- **Setup:** Run `mediamtx.exe` on Windows with this config; server connects to Windows IP:8889/oogway.

## [0.0.7] - 2026-04-20
- Fixed MediaMTX crash in Docker: ffmpeg input changed from DShow (unavailable in container) to test pattern.
- Docker-compose now includes both `mediamtx` and `oogworld` services with proper networking.
- **For real webcam:** Run MediaMTX natively on Windows with DShow input, or connect Docker MediaMTX to native MediaMTX instance via RTSP.

## [0.0.6] - 2026-04-20
- Rolled back `mediamtx.yml` ffmpeg profile to ultra-conservative: 1280x720@30fps, libx264 ultrafast baseline. Addresses CMD flash-close on i5-4590T + Intel HD 4600.

## [0.0.5] - 2026-04-20
- Upgraded `mediamtx.yml` ffmpeg publisher profile to high-quality 1080p30.
- Increased bitrate settings to `6 Mbps` target with `8 Mbps` maxrate and larger VBV buffer.
- Switched encoder profile from baseline/ultrafast low-load settings to `libx264` high-profile `superfast` for improved image quality.
- Increased DirectShow input buffer and explicit 1080p capture settings for the C922 webcam.

## [0.0.4] - 2026-04-20
- Updated `mediamtx.yml` `runOnInit` ffmpeg command for older hardware compatibility.
- Replaced `h264_qsv` encoding with software `libx264` using `ultrafast` + `zerolatency` tuning.
- Lowered default stream profile to 1280x720 at 30fps with reduced bitrate for stability on older CPUs/iGPUs.
- Kept RTSP publishing flow unchanged (`rtsp://localhost:$RTSP_PORT/$MTX_PATH`).

## [0.0.3] - 2026-04-20
- Added emergency report workflow with toggle buttons for food and water issues.
- Added hanging report banner with fade-in/out behavior that reflects active emergency reports.
- Added report endpoints (`/api/reports`, `/api/reports/toggle`) with ntfy notifications and chat broadcast entries.
- Added report messages to unified chat feed in the format: `XXX has reported that Oogway is out of ...`.
- Preserved emoji usage in chat and added explicit emoji-capable font fallback in the frontend.
- Added complete `mediamtx.yml` configuration file with RTSP, HLS, WebRTC, API, metrics, and `oogway` path startup command.

## [0.0.2] - 2026-04-20
- Added same-origin MediaMTX stream proxy routes (`/media/webrtc/...` and `/media/hls/...`) so stream loading stays on app domain for cloudflared access.
- Updated health stream URLs to prefer proxy paths while still exposing direct URLs.
- Removed `Go Live` button from video controls.
- Removed `Controls themed for WebRTC player` text from video controls.
- Updated control hint text to reflect tunnel-safe routing.
- Updated popout behavior to prefer direct MediaMTX URL while keeping embedded iframe on proxied URL.

## [0.0.1] - 2026-04-20
- Enforced repository policy that every edit must include a version bump.
- Enforced repository policy that every version bump must include a changelog entry.
- Updated agent versioning guidance to require synchronized version updates.
- Bumped backend APP_VERSION to 0.0.1.
- Updated README current version to 0.0.1 and linked changelog tracking.
