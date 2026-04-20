# OogWorld Split Deployment Setup

This guide explains how to run OogWorld with MediaMTX on your Windows machine and OogWorld backend on your server.

## Architecture

```
Windows Machine (with C922 webcam)
├── MediaMTX (native)
│   ├── Captures video via DShow
│   ├── Publishes RTSP (8554), HLS (8888), WebRTC (8889)
│   └── Available on local network (e.g., 192.168.1.100)
│
Server (Ubuntu/Linux)
└── OogWorld Backend (Docker)
    ├── Consumes stream from Windows MediaMTX
    ├── FastAPI server (4120)
    └── Chat + Emergency reports
```

## Windows Setup (MediaMTX + Webcam)

### Prerequisites
- Windows machine with C922 Pro Stream Webcam connected and recognized
- ffmpeg installed (via scoop, chocolatey, or manual download)

### Step 1: Download MediaMTX

1. Visit: https://github.com/bluenviron/mediamtx/releases
2. Download `mediamtx_vX.X.X_windows_amd64.zip`
3. Extract to a folder (e.g., `C:\mediamtx\`)
4. Copy `mediamtx.yml` from your OogWorld repo to the mediamtx folder

### Step 2: Start MediaMTX

Run the included script:
```powershell
.\run_mediamtx.bat
```

Or manually:
```powershell
cd C:\mediamtx
.\mediamtx.exe
```

Expected output:
```
[2026-04-20 12:00:00] INFO logger_service.go:68: ...
[2026-04-20 12:00:00] INFO  ... RTSP: :8554
[2026-04-20 12:00:00] INFO  ... HLS:  :8888
[2026-04-20 12:00:00] INFO  ... WebRTC: :8889
```

### Step 3: Verify MediaMTX is Running

1. Find your Windows local IP:
   ```powershell
   ipconfig  # Look for "IPv4 Address" (e.g., 192.168.1.100)
   ```

2. Test the stream (on Windows, substitute your IP if testing from another machine):
   ```
   WebRTC (browser):  http://localhost:8889/oogway
   HLS (browser):     http://localhost:8888/oogway
   RTSP (VLC):        rtsp://localhost:8554/oogway
   ```

## Server Setup (OogWorld on Docker)

### Step 1: Configure Connection to Windows MediaMTX

Create `.env` file (or update existing):
```env
# Replace 192.168.1.100 with your actual Windows machine IP
STREAM_URL=http://192.168.1.100:8889/oogway
NTFY_TOPIC=your-ntfy-topic
TZ=UTC
```

### Step 2: Deploy on Server

```bash
docker compose up -d
```

Or with explicit env var:
```bash
STREAM_URL=http://192.168.1.100:8889/oogway docker compose up -d
```

### Step 3: Access OogWorld Dashboard

```
http://server-ip:4120
```

## Finding Your Windows IP

### PowerShell
```powershell
ipconfig
# Look for "IPv4 Address" under your active network adapter (e.g., 192.168.1.100)
```

### Command Prompt
```cmd
ipconfig
```

## Troubleshooting

### MediaMTX crashes immediately on Windows
- Verify ffmpeg is installed: `ffmpeg -version`
- Check C922 is recognized: `ffmpeg -f dshow -list_devices true -i dummy`
- If "c922 Pro Stream Webcam" not listed, use the exact name from the list

### Server can't reach Windows MediaMTX
- Verify Windows IP is correct: `ipconfig` on Windows
- Test from server: `curl http://192.168.1.100:8889/oogway` (should return 404 + OK)
- Check Windows firewall allows port 8889 inbound
- Test with VLC to confirm stream works: `rtsp://192.168.1.100:8554/oogway`

### Camera name is different
1. On Windows, run:
   ```
   ffmpeg -f dshow -list_devices true -i dummy
   ```
2. Find your camera name in the output
3. Edit `mediamtx.yml`: Update `video="..."` with exact name
4. Restart MediaMTX

## Firewall Configuration (Windows)

If MediaMTX can't be accessed from the server:

1. Open Windows Defender Firewall
2. Click "Allow an app through firewall"
3. Add mediamtx.exe or allow ports 8554, 8888, 8889 inbound

## Performance Notes

- Encoder: libx264 ultrafast (low CPU usage, suitable for older hardware)
- Resolution: 1280×720 @ 30fps
- Bitrate: 1500 kbps (adjustable in mediamtx.yml)

If CPU usage is high, reduce resolution or bitrate in `mediamtx.yml`.

