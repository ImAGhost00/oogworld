# OogWorld Dashboard v0.1.0

A real-time terrarium monitoring and control dashboard for Oogway's enclosure, featuring live HLS stream playback and action notifications via ntfy.

## Architecture

- **Backend**: FastAPI (Python 3.12)
- **Frontend**: Responsive SPA with Tailwind CSS, HLS.js video player
- **Stream Source**: MediaMTX RTSP-to-HLS gateway
- **Notifications**: ntfy.sh webhook integration
- **Deployment**: Docker Compose

## Prerequisites

1. **MediaMTX** running on your wall PC with the `oogway` stream configured and outputting HLS at `http://localhost:8554/oogway/index.m3u8`
2. **Docker & Docker Compose** installed on the deployment target
3. **ntfy.sh topic** created (or use a self-hosted ntfy server)
4. **Admin password** configured with `ADMIN_PASSWORD`
5. **Terrarium coordinates** configured with `SUN_LAT` and `SUN_LNG`

### MediaMTX Configuration Example

```yaml
oogway:
  runOnInit: >
    ffmpeg -f dshow -rtbufsize 250M -i video="c922 Pro Stream Webcam" 
    -vcodec h264_qsv -profile:v high -bf 0 -s 1920x1080 -b:v 6M -maxrate 6M -bufsize 12M 
    -preset fast -f rtsp -rtsp_transport tcp rtsp://localhost:$RTSP_PORT/$MTX_PATH
  runOnInitRestart: yes
```

This captures from a Logitech C922 Pro Stream Webcam, encodes with H.264 Quick Sync, and outputs RTSP to MediaMTX, which automatically converts to HLS.

## Setup & Run

### 1. Configure Environment

#### With Portainer (Recommended)

1. In Portainer, create a new stack and paste the `docker-compose.yml` file
2. In the **Environment variables** section, add:
  - `STREAM_URL` → `http://localhost:8554/oogway/index.m3u8` (or wall PC IP if remote)
  - `NTFY_TOPIC` → your ntfy topic
  - `TZ` → your timezone (e.g., `America/New_York`)
  - `ADMIN_PASSWORD` → password for admin panel access
  - `SUN_LAT` / `SUN_LNG` → latitude/longitude for sunrise/sunset schedule
  - `BEDTIME_SOON_MINUTES` → minutes before sunset to show bedtime countdown (default `90`)
  - `ACTIVITY_LOG_PATH` → `/app/activity_log.json` (leave as default)
  - `CHAT_LOG_PATH` → `/app/chat_log.json` (leave as default)
3. Deploy the stack

#### With Docker CLI

```bash
cp .env.example .env
# Edit .env with your values
docker compose up --build
```

Edit `.env` with your values:

```env
STREAM_URL=http://localhost:8554/oogway/index.m3u8
NTFY_TOPIC=your-unique-ntfy-topic
TZ=UTC
ADMIN_PASSWORD=change-me
SUN_LAT=40.7128
SUN_LNG=-74.0060
BEDTIME_SOON_MINUTES=90
ACTIVITY_LOG_PATH=/app/activity_log.json
CHAT_LOG_PATH=/app/chat_log.json
```

**Note**: If running OogWorld on a different machine from MediaMTX, replace `localhost` with the IP/hostname of your wall PC.

### 2. Start Deployment

The app will be available at `http://localhost:4120`.

### 3. (Optional) Local Development

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
export STREAM_URL="http://localhost:8554/oogway/index.m3u8"
export NTFY_TOPIC="your-topic"
export TZ="UTC"
export ADMIN_PASSWORD="change-me"
export SUN_LAT="40.7128"
export SUN_LNG="-74.0060"
export BEDTIME_SOON_MINUTES="90"
uvicorn main:app --reload --host 0.0.0.0 --port 4120
```

## API Endpoints

- `GET /` – Serves dashboard UI
- `GET /api/health` – Returns app status, version, and configuration flags
- `GET /api/activity` – Returns the latest 5 logged actions with timestamps
- `GET /api/chat/history` – Returns the latest 200 chat/feed events
- `GET /api/reports` – Returns active emergency report state
- `GET /api/daylight` – Returns sunrise/sunset lamp state and countdown values
- `POST /api/actions` – Triggers an action (`"Request Food"` or `"Refill Water"`), sends to ntfy, and logs
- `POST /api/reports/toggle` – Submits a food/water emergency report (locks until admin reset)
- `POST /api/admin/login` – Authenticates admin via `ADMIN_PASSWORD`
- `POST /api/admin/reports/reset` – Admin reset for food, water, or all report alerts
- `DELETE /api/admin/chat/{message_id}` – Admin delete for individual chat messages
- `POST /api/admin/chat/clear` – Admin clear entire chat log
- `WS /ws/chat` – Real-time chat broadcast channel

## Features

- **Live Stream**: WebRTC stream embed with same-origin MediaMTX proxy routing
- **Action Log**: Last 5 actions persisted to JSON, displayed in reverse chronological order
- **Notifications**: One-click buttons send POST requests to ntfy.sh with action messages
- **Report Icon Workflow**: Report button is now a dedicated icon beside the video header and opens a compact report window
- **Locked Emergency Alerts**: Once a user reports food/water need, alert stays locked until an admin reset
- **Red Alert Banner**: Displays `USER has reported that Oogway needs XXX` and a live timer since report time
- **Admin Panel**: Password-gated admin tools for resetting alerts, deleting chat messages, and clearing chat log
- **Heatlamp Daylight Automation**: Sunrise/sunset schedule fetched from `https://sunrise-sunset.org/api` several times per day
- **Bedtime Banners**: Countdown appears before sunset; overnight banner shows `oogway is asleep, his heatlamp will turn on in XX:XX`
- **Responsive Design**: Desktop layout (video left, controls right) and mobile stack (video top, buttons bottom)
- **GhostWorld Aesthetic**: Dark theme with accent colors (#39FF14 lime, #050505 background)
- **Live Status Pulse**: Animated breathing dot indicates stream is live

## Activity Log

Actions are automatically logged with:
- Action name (`"Request Food"` or `"Refill Water"`)
- Delivery status (`"sent"` or `"failed"`)
- ISO 8601 timestamp

The log file is stored at the path specified by `ACTIVITY_LOG_PATH` and is automatically capped at the latest 5 entries.

## Admin & Reporting

- Users click the report icon near video and choose food or water.
- Reports lock immediately after submit to avoid accidental toggles.
- Admin logs in from the in-app **Admin** button using `ADMIN_PASSWORD`.
- Admin can reset food/water/all alerts and clear active alert banner state.
- Admin can delete specific chat messages inline and clear the full chat history.

## Heatlamp Schedule

- Heatlamp is considered **ON** from sunrise to sunset.
- Heatlamp is considered **OFF** during bedtime (after sunset until sunrise).
- Before bedtime, the app shows a countdown until lamp-off.
- During bedtime, the UI text is: `oogway is asleep, his heatlamp will turn on in XX:XX`.

## Future Extensions

The application is designed with extension points for:
- **Authentication**: Authentik/OIDC middleware can be added to protect endpoints without major refactor (currently open access)
- **Additional Actions**: New action types can be added to `ACTION_MESSAGE` dict and action types enum
- **Persistent Storage**: JSON log can be migrated to a database
- **Advanced Metrics**: Historical trend analysis of action frequency

## Troubleshooting

- **Stream not loading**: Verify `STREAM_URL` is accessible from the container. If MediaMTX is on a different machine, use its IP instead of `localhost`.
- **Notifications not sending**: Check that `NTFY_TOPIC` is correctly set and ntfy.sh is reachable from the container.
- **Activity log not persisting**: Ensure the container has write permissions to the volume or path specified by `ACTIVITY_LOG_PATH`.

## Version

- Current: 0.1.0
- Bump method: semver (major.minor.patch, each segment 0–99)

## Changelog

- Version history is tracked in `CHANGELOG.md`.

---

Built with ❤️ for Oogway's home.
