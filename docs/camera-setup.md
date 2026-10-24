## Raspberry Pi CSI Camera — Low-Latency WebRTC Setup

### 1. Check the Raspberry Pi

```bash
uname -m
cat /proc/device-tree/model
rpicam-hello --list-cameras
hostname -I
```

The expected architecture is `aarch64`. Confirm that the CSI ribbon camera is detected.

### 2. Download MediaMTX v1.21.2

```bash
cd ~/projects
mkdir -p mediamtx
cd mediamtx

curl -fL https://github.com/bluenviron/mediamtx/releases/download/v1.21.2/mediamtx_v1.21.2_linux_arm64.tar.gz -o mediamtx.tar.gz

tar -xzf mediamtx.tar.gz
chmod +x mediamtx
./mediamtx --version
```

### 3. Configure the camera

Create the configuration file:

```bash
nano mediamtx.yml
```

Add:

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
    rpiCameraFPS: 30
    rpiCameraBitrate: 3000000
```

Save with `Ctrl+O`, Enter, then `Ctrl+X`.

### 4. Start streaming

```bash
cd ~/projects/blink/LiFi-VLC/mediamtx
./mediamtx mediamtx.yml
```

Keep the terminal open and check for camera initialization errors.

### 5. Open the live stream

Get the Raspberry Pi IP address:

```bash
hostname -I
```

On another device connected to the same network, open:

```text
http://YOUR_PI_IP:8889/cam
```

Replace `YOUR_PI_IP` with the actual IP address of the Raspberry Pi.

### 6. Low-latency settings

- Start with 720p at 30 FPS.
- Prefer Ethernet or a strong local Wi-Fi connection.
- If the video stutters, reduce the resolution or bitrate.
- Check TCP port 8889 and UDP port 8189 if the browser cannot connect.
- For remote access, use a secure VPN such as Tailscale rather than exposing camera ports publicly.

**Note:** Verify camera-source compatibility against the MediaMTX v1.21.2 documentation if the camera fails to initialize.

References:
- https://github.com/bluenviron/mediamtx
- https://github.com/bluenviron/mediamtx/releases
- https://www.raspberrypi.com/documentation/computers/camera_software.html
