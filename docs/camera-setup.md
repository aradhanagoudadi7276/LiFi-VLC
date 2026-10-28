# Raspberry Pi CSI Camera — Low-Latency WebRTC Setup

## 1. Check the Raspberry Pi

Run the following commands to verify the system architecture, camera detection, and IP address.

```bash
uname -m
cat /proc/device-tree/model
rpicam-hello --list-cameras
hostname -I
```

The expected architecture is `aarch64`. Confirm that the CSI ribbon camera is detected.

## 2. Download MediaMTX v1.21.2

Create the MediaMTX directory in the Raspberry Pi user's home directory.

```bash
cd ~
mkdir -p mediamtx
cd ~/mediamtx
```

Download and extract MediaMTX:

```bash
curl -fL https://github.com/bluenviron/mediamtx/releases/download/v1.21.2/mediamtx_v1.21.2_linux_arm64.tar.gz -o mediamtx.tar.gz

tar -xzf mediamtx.tar.gz
chmod +x mediamtx
./mediamtx --version
```

Expected version:

```text
MediaMTX v1.21.2
```

## 3. Configure the camera

Create the configuration file:

```bash
cd ~/mediamtx
nano mediamtx.yml
```

Add the following configuration:

```yaml
logLevel: info

webrtc: yes
webrtcAddress: :8889
webrtcLocalUDPAddress: :8189

paths:
  cam:
    source: rpiCamera
    rpiCameraWidth: 1280
    rpiCameraHeight: 720
    rpiCameraFPS: 20
    rpiCameraBitrate: 1500000
```

Save using `Ctrl+O`, press Enter, and exit using `Ctrl+X`.

## 4. Start streaming manually

Before configuring automatic startup, test the camera stream manually.

```bash
cd ~/mediamtx
./mediamtx mediamtx.yml
```

Check the logs for messages confirming that:

- MediaMTX has loaded `mediamtx.yml`.
- The Raspberry Pi camera has started.
- Hardware H.264 encoding is enabled.
- The `cam` stream is available and online.
- WebRTC signaling is listening on TCP port `8889`, with ICE media on UDP port `8189`.

Example successful log message:

```text
INF [path cam] stream is available and online, 1 track (H264)
```

Press `Ctrl+C` to stop the manual process before starting the systemd service.

## 5. Open the live stream

Find the Raspberry Pi IP address:

```bash
hostname -I
```

For direct local-network access, open the MediaMTX WebRTC player:

```text
http://YOUR_PI_IP:8889/cam
```

Replace `YOUR_PI_IP` with the actual IP address of the Raspberry Pi.

The MediaMTX player page and WebRTC signaling use TCP port `8889`. WebRTC video also needs a working ICE media route to the Raspberry Pi on UDP port `8189`; allow that UDP port through the Pi's firewall and network. The dashboard uses the `/cam/` path on the Django/Caddy origin and sends WHEP signaling to `/cam/whep`.

The project [Caddyfile](../config/Caddyfile) listens on `127.0.0.1:8080`, redirects `/cam` to `/cam/`, proxies `/cam/*` to MediaMTX on `127.0.0.1:8889`, and sends other requests to Django on `127.0.0.1:8000`. This reverse proxy carries the HTTP player and WHEP signaling; it does not proxy the separate UDP media traffic.

Tailscale Funnel can carry the dashboard and WebRTC signaling over HTTPS, but it does not carry WebRTC's UDP media traffic. The dashboard camera therefore requires a direct working ICE route from the browser to the Raspberry Pi; Funnel alone is not sufficient for remote video playback. For remote viewing, connect through a network/VPN that provides that route or configure an appropriate WebRTC media relay.

## 6. Configure automatic startup on reboot

Create a systemd service so MediaMTX starts automatically when the Raspberry Pi boots.

### 6.1 Create the service file

```bash
sudo nano /etc/systemd/system/mediamtx.service
```

Add:

```ini
[Unit]
Description=MediaMTX Raspberry Pi Camera Streaming
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/mediamtx
ExecStart=/home/pi/mediamtx/mediamtx /home/pi/mediamtx/mediamtx.yml
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Save using `Ctrl+O`, Enter, and `Ctrl+X`.

**Important:** This service launches the MediaMTX binary directly. It does not depend on a separate shell script.

### 6.2 Enable and start the service

```bash
sudo systemctl daemon-reload
sudo systemctl reset-failed mediamtx
sudo systemctl enable mediamtx
sudo systemctl start mediamtx
```

### 6.3 Verify service status

```bash
sudo systemctl status mediamtx --no-pager
```

Expected status:

```text
Active: active (running)
```

View live logs:

```bash
sudo journalctl -u mediamtx -f
```

View the last 40 log lines:

```bash
sudo journalctl -u mediamtx -n 40 --no-pager
```

### 6.4 Test after reboot

```bash
sudo reboot
```

Reconnect to the Raspberry Pi and run:

```bash
sudo systemctl status mediamtx --no-pager
```

If the service is active, MediaMTX has started automatically.

Useful service commands:

```bash
sudo systemctl start mediamtx
sudo systemctl stop mediamtx
sudo systemctl restart mediamtx
sudo systemctl disable mediamtx
```

## 7. WebRTC settings and troubleshooting

- **Resolution:** This configuration uses 1280 × 720 at 20 FPS.
- **Bitrate:** This configuration uses 1.5 Mbps; adjust it if the network or encoder requires different settings.
- **Network:** Prefer Ethernet or a strong local Wi-Fi connection.
- **WebRTC signaling:** TCP port `8889` serves the player page and WHEP signaling.
- **WebRTC media:** UDP port `8189` is used for ICE media connectivity. Verify the browser can reach the Pi over this port; a working HTTP/WHEP response alone does not prove that the video media route works.
- **Tailscale Funnel:** Funnel does not carry WebRTC UDP media. A dashboard reachable through Funnel may still show the camera as unavailable unless a separate ICE route or WebRTC media relay is configured.
- **Camera detection:** Confirm the CSI ribbon is seated correctly and that `rpicam-hello --list-cameras` detects the camera.
- **Service errors:** Check `sudo journalctl -u mediamtx -n 40 --no-pager`.
- **Port conflicts:** Ensure another MediaMTX process is not already using the configured ports.
- **TLS key warnings:** If MediaMTX reports that it cannot write `auto.key` or `auto.crt`, check directory permissions and the service's working directory. These warnings are separate from the shell-script execution error.

For remote access, use a secure VPN such as Tailscale rather than exposing camera ports directly to the public internet.

## 8. Optional MediaMTX player integration

For a standalone test or a frontend that intentionally uses MediaMTX's built-in player, embed the WebRTC player page in an iframe:

```jsx
export default function CameraStream() {
  const playerUrl = "http://192.168.1.100:8889/cam";

  return (
    <div style={{ width: "100%", background: "#000" }}>
      <iframe
        src={playerUrl}
        title="Raspberry Pi live camera"
        allow="autoplay; fullscreen; picture-in-picture"
        style={{
          display: "block",
          width: "100%",
          aspectRatio: "16 / 9",
          border: 0,
        }}
      />
    </div>
  );
}
```

Replace `192.168.1.100` with the Raspberry Pi's actual IP address. The browser device must be able to reach the Pi over the WebRTC media path as well as load the player page. This is separate from the dashboard's native, control-free video player.

## References

- MediaMTX: https://github.com/bluenviron/mediamtx
- MediaMTX releases: https://github.com/bluenviron/mediamtx/releases
- Raspberry Pi camera software documentation: https://www.raspberrypi.com/documentation/computers/camera_software.html
