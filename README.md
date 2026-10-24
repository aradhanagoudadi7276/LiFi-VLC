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

The dashboard embeds the MediaMTX WebRTC player at `http://127.0.0.1:8889/cam` by default. See [docs/camera-setup.md](docs/camera-setup.md) to configure the Raspberry Pi camera and MediaMTX. Override the player URL with `CAMERA_STREAM_URL` if MediaMTX is hosted elsewhere.

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
- `DJANGO_ALLOWED_HOSTS`: comma-separated host names; defaults to `localhost,127.0.0.1`
- `CAMERA_STREAM_URL`: MediaMTX WebRTC player URL
- `BOOTSTRAP_ADMIN_USERNAME` / `BOOTSTRAP_ADMIN_PASSWORD`: optional initial account values

Run tests with `python manage.py test`.

When accessing the dashboard from another device, add the server's LAN IP to `DJANGO_ALLOWED_HOSTS`, for example:

```bash
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,10.78.52.72 python manage.py runserver 0.0.0.0:8000
```

The default list includes `10.78.52.72` for the current LAN setup. Update it if the server's IP changes.
