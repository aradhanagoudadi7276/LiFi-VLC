# LiFi VLC dashboard

A Django and SQLite starter dashboard for the LiFi VLC project. It includes a login page, a MediaMTX camera player, and an authenticated WebSocket control channel.

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

The dashboard embeds the MediaMTX HLS player configured in [config/app.json](config/app.json). The default `/cam` path uses the same Tailscale HTTPS hostname as Django; configure Tailscale Serve to forward that path to MediaMTX's local HLS port `8888` as described in [docs/tailscale-setup.md](docs/tailscale-setup.md). HLS works through HTTPS without a separate UDP media port, with somewhat more latency than WebRTC. See [docs/camera-setup.md](docs/camera-setup.md) to configure the Raspberry Pi camera and MediaMTX.

## Access Django and camera through Tailscale

Use one HTTPS hostname: Django at `/` and the MediaMTX HLS player at `/cam`. Do not create another default HTTPS listener for port `443`; add `/cam` to the existing Serve/Funnel configuration.

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

   Verify it locally with `curl -I http://127.0.0.1:8000/`. Tailscale will proxy HTTPS requests to this local address; do not expose port `8000` directly to the internet.

3. If the dashboard is public through Funnel, configure the existing HTTPS listener's root route for Django and add the camera path:

   ```bash
   chmod +x scripts/expose-dashboard-with-tailscale.sh
   ./scripts/expose-dashboard-with-tailscale.sh
   ```

   The script verifies Django and MediaMTX respond locally, configures `/` for Django and `/cam` for the camera, then prints Funnel status. It does not reset the Funnel configuration.

   Test `https://<your-device>.<your-tailnet>.ts.net/` and `https://<your-device>.<your-tailnet>.ts.net/cam/`.

   For private tailnet-only access, use Tailscale Serve instead; see [docs/tailscale-setup.md](docs/tailscale-setup.md). Test `https://<your-device>.<your-tailnet>.ts.net/cam/` directly, then open the dashboard at `https://<your-device>.<your-tailnet>.ts.net/`.

HLS has more latency than WebRTC, but works through HTTPS without Funnel needing to carry WebRTC's UDP media traffic. See [docs/tailscale-setup.md](docs/tailscale-setup.md) for more details. Do not use `tailscale funnel http://0.0.0.0:8000`: `0.0.0.0` is a bind address, and the command attempts to create another default HTTPS listener.

Funnel makes the Django login page publicly accessible. Before enabling it, change the starter password (`python manage.py changepassword admin`), set `DJANGO_DEBUG=false`, and configure a strong `DJANGO_SECRET_KEY`.

## Theme

The login page and dashboard theme are configured in [config/theme.json](config/theme.json). Edit its color, typography, spacing, border, component, chart, and effect tokens to re-theme both pages consistently. Restart Django after changing the file.

## WebSocket control

The dashboard opens `/ws/control/` using the current page's WebSocket protocol and sends these JSON messages when the connection button is toggled:

```json
{"command": "connection", "value": "connect"}
```

```json
{"command": "connection", "value": "disconnect"}
```

The authenticated Django Channels consumer validates the message, logs the requested state, and replies with an `accepted` acknowledgement. The in-memory channel layer is sufficient for this single-process starter; connect a hardware/controller integration to the consumer when implementing device behavior.

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
