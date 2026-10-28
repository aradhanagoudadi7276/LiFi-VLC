# LiFi VLC dashboard

A Django and SQLite dashboard for the LiFi VLC project. It includes an authenticated live transmitter/receiver bridge, optical signal analytics, a MediaMTX camera player, and a real-time receive activity feed.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py bootstrap_admin
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and sign in with:

- Username: `admin`
- Password: `admin@123`

The bootstrap command creates this account only if the username does not already exist. Set `BOOTSTRAP_ADMIN_USERNAME` and `BOOTSTRAP_ADMIN_PASSWORD` before running it to choose different credentials. The starter password is for local setup only; set a strong password before deployment.

## Camera stream

The dashboard embeds the MediaMTX HLS player configured in [config/app.json](config/app.json). Caddy proxies the default `/cam/` path to MediaMTX's local HLS port `8888` and proxies dashboard and WebSocket requests to Django. Tailscale forwards the single HTTPS listener to Caddy. HLS works through HTTPS without a separate UDP media port, but has more latency than WebRTC. The MediaMTX example uses Low-Latency HLS with 200 ms parts as a balance between delay and stable playback. For details, see [docs/camera-setup.md](docs/camera-setup.md).

## Access Django and camera through Tailscale

Use one HTTPS hostname: Caddy receives requests from Tailscale, then proxies Django at `/` and the MediaMTX HLS player at `/cam`. Caddy listens on `127.0.0.1:8080`, so it is not directly exposed to the LAN. Funnel uses only its existing HTTPS root listener; do not create a second Tailscale listener.

1. Enable HLS in `~/mediamtx/mediamtx.yml`:

   ```yaml
   hls: yes
   hlsAddress: :8888
   ```

   Restart MediaMTX and verify the player responds locally:

   ```bash
   sudo systemctl restart mediamtx
   curl -I http://127.0.0.1:8888/cam/
   ```

2. Stop any Django `runserver` bound to `0.0.0.0:8000` with **Ctrl+C**, then run Django on loopback:

   ```bash
   python manage.py runserver 127.0.0.1:8000
   ```

   Verify it locally with `curl -I http://127.0.0.1:8000/`. Do not expose port `8000` directly to the internet.

3. Install Caddy if it is not already installed (for Raspberry Pi OS, use the official [Caddy Debian/Ubuntu installation instructions](https://caddyserver.com/docs/install#debian-ubuntu-raspbian)). Validate the project config:

   ```bash
   sudo caddy validate --config "$PWD/config/Caddyfile"
   ```

   Caddy is already managed by systemd on this Pi. Do not use `caddy start`, which tries to launch a second instance and fails with `127.0.0.1:2019: address already in use`. The helper below reloads the active Caddy process with the project config, which proxies `/` and `/ws/control/` to Django on `127.0.0.1:8000`, and `/cam/` to MediaMTX HLS on `127.0.0.1:8888`. It also redirects `/cam` to `/cam/`.

4. Configure Funnel to forward its existing HTTPS listener to Caddy:

   ```bash
   chmod +x scripts/expose-dashboard-with-tailscale.sh
   ./scripts/expose-dashboard-with-tailscale.sh
   ```

   The helper validates and reloads the running Caddy service with the project config, checks Django and MediaMTX, points the single Funnel root route at Caddy, removes the old direct `/cam` route if present, and prints Funnel status. It does not reset Funnel configuration.

Test `https://<your-device>.<your-tailnet>.ts.net/` and `https://<your-device>.<your-tailnet>.ts.net/cam/`. See [docs/tailscale-setup.md](docs/tailscale-setup.md) for more details. HLS has more latency than WebRTC, but works through HTTPS without Funnel needing to carry WebRTC's UDP media traffic.

Funnel makes the Django login page publicly accessible. Before enabling it, change the starter password (`python manage.py changepassword admin`), set `DJANGO_DEBUG=false`, and configure a strong `DJANGO_SECRET_KEY`.

## Theme

The login page and dashboard theme are configured in [config/theme.json](config/theme.json). Edit its color, typography, spacing, border, component, chart, and effect tokens to re-theme both pages consistently. Restart Django after changing the file.

## Live LiFi dashboard

After signing in, use the top-right **Connect** button to let the authenticated dashboard bridge connect to the transmitter (`ws://127.0.0.1:8766`) and receiver (`ws://127.0.0.1:8765`) services on the Django host. Enter an ASCII message of up to 500 characters and choose **Send** to queue it for optical transmission. The animated optical network shows packet flow between the transmitter and receiver. The live data exchange panel shows outgoing messages through transmission completion and incoming text as it is decoded, then retains the complete decoded response. Receiver `receiver_status` telemetry is relayed live over the dashboard's `/ws/control/` WebSocket; ADC and voltage are shown together in the signal chart and as current readings. The fixed-height operations view uses the palette and component tokens in `config/theme.json`.

The bridge URLs can be overridden when the hardware services run on another host:

- `LIFI_TRANSMITTER_WEBSOCKET_URL`: transmitter WebSocket URL; defaults to `ws://127.0.0.1:8766`
- `LIFI_RECEIVER_WEBSOCKET_URL`: receiver WebSocket URL; defaults to `ws://127.0.0.1:8765`

The dashboard opens `/ws/control/` using the current page's WebSocket protocol and sends these JSON messages:

```json
{"command": "connection", "value": "connect"}
```

```json
{"command": "connection", "value": "disconnect"}
```

```json
{"command": "send", "message": "Hello World"}
```

The authenticated Django Channels consumer proxies those commands and hardware events between the browser and the two LiFi WebSocket services. Keep the hardware services reachable only on trusted networks; the dashboard credentials protect the browser-facing bridge.

## Configuration and tests

Environment variables:

- `DJANGO_SECRET_KEY`: secret key (required for deployment)
- `DJANGO_DEBUG`: defaults to `true`; set to `false` outside local development
- `DJANGO_ALLOWED_HOSTS`: comma-separated host names; defaults to `allowed_hosts` in `config/app.json`
- `DJANGO_CSRF_TRUSTED_ORIGINS`: comma-separated full origins (including `https://`); defaults to `csrf_trusted_origins` in `config/app.json`
- `CAMERA_STREAM_URL`: overrides `urls.camera_stream` from `config/app.json`
- `CONTROL_WEBSOCKET_URL`: overrides `urls.control_websocket` from `config/app.json`
- `BOOTSTRAP_ADMIN_USERNAME` / `BOOTSTRAP_ADMIN_PASSWORD`: optional initial account values

Run tests with `python manage.py test`.

The application URLs, allowed hosts, and CSRF trusted origins can be edited in `config/app.json`. Add the full origin, including its scheme (for example, `https://vlc-server.tail4db684.ts.net`), under `csrf_trusted_origins` for each site used to access the app. Restart Django after changing the config. The control WebSocket URL can be a path (to use the current page's host and HTTP/HTTPS security) or a full WebSocket URL.

For direct private LAN access, bind Django to all interfaces and include the device address in `DJANGO_ALLOWED_HOSTS`:

```bash
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,10.78.52.72 python manage.py runserver 0.0.0.0:8000
```

This direct LAN option is separate from the Tailscale HTTPS setup above; use the loopback-bound command there when serving Django through Tailscale.
