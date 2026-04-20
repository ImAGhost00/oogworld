# Changelog

All notable changes to this project are documented in this file.

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
