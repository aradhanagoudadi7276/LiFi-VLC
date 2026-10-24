# Tailscale Setup for Raspberry Pi VLC/LiFi Project

This guide explains how to install Tailscale on a Raspberry Pi, access it remotely from a Windows computer, and optionally publish the VLC/LiFi dashboard to the public internet using Tailscale Funnel.

## 1. Overview

Tailscale allows you to connect to your Raspberry Pi remotely without needing to know its local network IP address.

You can use it to:

- Access the Raspberry Pi through SSH.
- Access the VLC/LiFi dashboard remotely.
- Connect from different networks, including mobile hotspots.
- Optionally publish the dashboard using a public HTTPS URL through Tailscale Funnel.

### Access methods

| Method | Access requirement | Use case |
|---|---|---|
| Tailscale private access | Visitor's device must connect to your Tailscale network | Private SSH and dashboard |
| Tailscale Funnel | Public HTTPS URL | Access dashboard without installing Tailscale |
| Custom domain | Separate domain and public-facing hosting/proxy configuration | Use a domain such as `vlc.example.com` |

**Important:** Tailscale Funnel provides a Tailscale-managed `ts.net` domain. It does not directly assign an arbitrary custom domain.

## 2. Requirements

- Raspberry Pi with Raspberry Pi OS installed.
- Working internet connection.
- Tailscale account.
- Windows laptop or computer.
- SSH server installed if remote terminal access is required.
- VLC/LiFi dashboard running on the Raspberry Pi.

## 3. Install Tailscale on Raspberry Pi

Open the Raspberry Pi terminal and run the following commands.

### Step 1: Update the system

```bash
sudo apt update
```

### Step 2: Install curl

```bash
sudo apt install -y curl
```

### Step 3: Install Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

### Step 4: Connect to Tailscale

```bash
sudo tailscale up
```

Open the login URL displayed in the terminal and sign in to your Tailscale account.

Authorize the Raspberry Pi when prompted.

### Step 5: Verify the connection

```bash
tailscale status
```

Get the Raspberry Pi's Tailscale IPv4 address:

```bash
tailscale ip -4
```

The address will generally start with `100.`. Use the actual IP returned by your device.

Official guide: https://tailscale.com/docs/install/linux

## 4. Install Tailscale on Windows

1. Visit https://tailscale.com/download
2. Download and install Tailscale for Windows.
3. Sign in using the same Tailscale account as the Raspberry Pi.
4. Confirm that both devices appear in your Tailscale device list.
5. Verify that the Raspberry Pi is online.

## 5. Enable SSH on Raspberry Pi

SSH allows you to control the Raspberry Pi from Windows without using a monitor.

### Step 1: Install the SSH server if necessary

```bash
sudo apt update
sudo apt install -y openssh-server
```

### Step 2: Enable and start SSH

```bash
sudo systemctl enable --now ssh
```

### Step 3: Check SSH status

```bash
sudo systemctl status ssh
```

### Step 4: Connect from Windows

Open PowerShell or Command Prompt on Windows.

Run:

```powershell
ssh <linux-username>@<tailscale-ip>
```

For example:

```powershell
ssh pi@100.x.x.x
```

Replace `pi` with your actual Raspberry Pi Linux username and `100.x.x.x` with the Tailscale IP address.

You can now access the Raspberry Pi terminal remotely.

## 6. Access the VLC/LiFi Dashboard Privately

Assume the project uses the following ports:

| Component | Port | Purpose |
|---|---:|---|
| Frontend | 5173 | Dashboard UI |
| Backend | 8000 | Python API and WebSocket services |

Start the frontend and backend using the project's normal startup commands.

From a Windows device connected to Tailscale, open:

Frontend:

```text
http://<tailscale-ip>:5173
```

Backend, if direct access is required:

```text
http://<tailscale-ip>:8000
```

Replace `<tailscale-ip>` with the actual Tailscale IP.

**Note:** These URLs work only if the corresponding services are running and listening on an address reachable through Tailscale. Check your frontend and backend configuration if the pages do not load.

If your frontend proxy uses `localhost:8000`, remember that `localhost` refers to the machine running the frontend server, not the visitor's computer.

## 7. Public Dashboard Access Using Tailscale Funnel

Tailscale Funnel can expose a supported local service through a public HTTPS URL.

This allows visitors to open the dashboard in a normal browser without installing Tailscale.

### Step 1: Start the frontend

Start your frontend using the project's normal startup command.

Confirm that it responds locally on the Raspberry Pi:

```bash
curl -I http://127.0.0.1:5173
```

If this fails, check that the frontend is running and listening on port `5173`.

### Step 2: Enable Funnel

Run the following command on the Raspberry Pi, assuming your frontend uses port `5173` and your installed Tailscale CLI supports this syntax:

```bash
sudo tailscale funnel --bg http://127.0.0.1:5173
```

If Tailscale requires additional configuration or authorization, follow the instructions displayed in the terminal and in the Tailscale admin console.

### Step 3: Check Funnel status

```bash
sudo tailscale funnel status
```

Use the exact public HTTPS URL provided by Tailscale.

It may resemble this format:

```text
https://<device-name>.<tailnet-name>.ts.net
```

This is an example format, not your actual URL.

Open the generated HTTPS URL from a device that is not connected to Tailscale to test public access.

Official Funnel documentation:

https://tailscale.com/kb/1223/funnel

### Important precautions

- Do not expose port `8000` directly to the internet; keep it bound to `127.0.0.1` behind Tailscale's HTTPS proxy.
- Funnel makes the Django login and dashboard publicly accessible; replace the starter `admin` password with a strong password and set `DJANGO_DEBUG=false`.
- Make sure API and WebSocket connections work through the HTTPS proxy.
- Review the current Tailscale documentation for supported commands and configuration.

## 8. Use a Custom Domain

Tailscale Funnel does not directly replace its Tailscale-managed hostname with a custom domain such as:

```text
https://vlc.example.com
```

To use your own domain, you need a separate public-facing reverse proxy, tunnel, or hosting setup that supports your domain and HTTPS certificates.

## 9. Serve Django and the camera through one HTTPS URL

Keep Django on the existing root URL (`https://<device>.<tailnet>.ts.net/`) and map the camera path to MediaMTX's HLS player. This uses the existing HTTPS listener on port `443`; it does not create another listener or require a separate camera hostname.

First, confirm the local services respond on the Raspberry Pi:

```bash
curl -I http://127.0.0.1:8000/
curl -I http://127.0.0.1:8888/cam/
```

Run Django bound to loopback (the current development server is suitable for testing only):

```bash
python manage.py runserver 127.0.0.1:8000
```

If Django is currently running with `0.0.0.0:8000`, stop it with `Ctrl+C` first, then restart using the loopback command above. Change the starter password with `python manage.py changepassword admin`.

The existing root Serve route should already forward HTTPS `/` to Django on `127.0.0.1:8000`. Add a camera path on that same listener:

```bash
sudo tailscale serve --bg --set-path=/cam http://127.0.0.1:8888/cam/
sudo tailscale serve status
```

The project config sets `urls.camera_stream` to `/cam/`, so the dashboard iframe uses the current hostname and HTTPS automatically. The proxy target must include MediaMTX's `/cam/` path: otherwise Tailscale forwards the request to the MediaMTX root and MediaMTX returns a 404. Open `https://<device>.<tailnet>.ts.net/cam/` directly to verify the player, then open the dashboard.

If the dashboard must be public, inspect existing Funnel routes before changing them:

```bash
sudo tailscale funnel status
```

Do not run `tailscale funnel http://0.0.0.0:8000`: `0.0.0.0` is a bind address, not a reverse-proxy target, and this tries to create another default HTTPS listener. Funnel supports paths on its HTTPS listener; if the current public configuration does not already expose the `/cam` route, add the path-specific target:

```bash
sudo tailscale funnel --bg --set-path=/cam http://127.0.0.1:8888/cam/
sudo tailscale funnel status
```

Keep the existing root Funnel route for Django. Do not reset the Serve or Funnel configuration, since that can remove the working root route. Tailscale Serve/Funnel path routing is documented by the [Tailscale CLI reference](https://tailscale.com/docs/reference/tailscale-cli/serve) and [Funnel CLI reference](https://tailscale.com/docs/reference/tailscale-cli/funnel).

This uses HLS over HTTPS, which is compatible with a single Funnel HTTPS listener. It has more latency than WebRTC, but does not require forwarding ICE media over UDP. Keep MediaMTX's HLS server enabled on local port `8888`.

A DNS record pointing to a private Tailscale IP will not make the service accessible to ordinary internet visitors who are not connected to Tailscale.

For a simple project demonstration, the Tailscale Funnel URL is usually the easiest option.

## 9. Security Considerations

Before publishing the VLC/LiFi dashboard publicly:

- Protect LED control endpoints with authentication and authorization.
- Never expose an unauthenticated API that can switch the LED or control hardware.
- Do not publish passwords, API tokens, private logs, or other secrets.
- Keep Raspberry Pi OS and Tailscale updated.
- Expose only the ports that are necessary.
- Avoid exposing development servers permanently without reviewing their security.
- Test the public URL from a device outside your Tailscale network.
- Use private Tailscale access instead if the dashboard is intended only for your personal use.

**Recommended setup:** Keep SSH and the Python backend private, and expose only the dashboard frontend if public access is required.

## 10. Troubleshooting

### Problem 1: Tailscale command not found

Check the installation:

```bash
tailscale version
```

If the command is missing, review the installation output and official installation guide.

### Problem 2: Raspberry Pi is offline in Tailscale

Run:

```bash
sudo tailscale status
```

Check the Tailscale service:

```bash
sudo systemctl status tailscaled
```

Verify that the Pi has internet access and complete the `sudo tailscale up` login process.

### Problem 3: SSH connection refused

Check the SSH service:

```bash
sudo systemctl status ssh
```

Check the Tailscale IP:

```bash
tailscale ip -4
```

Confirm that Tailscale is connected on both devices and that you are using the correct Linux username and IP address.

### Problem 4: Dashboard does not load

Check the frontend locally:

```bash
curl -I http://127.0.0.1:5173
```

Confirm that the frontend process is running and that the configured port is correct.

### Problem 5: Funnel URL does not work

Check the Funnel configuration:

```bash
sudo tailscale funnel status
```

Confirm that the frontend is running and review any authorization or configuration messages from Tailscale.

Consult the official documentation:

https://tailscale.com/kb/1223/funnel

### Problem 6: Frontend loads but API requests fail

Check:

- Backend service status and port.
- Frontend API and WebSocket proxy settings.
- Whether the proxy target points to the correct backend address.
- Browser console errors and backend logs.

Do not expose the backend publicly just to work around an incorrect proxy configuration.

## 11. Official References

- Tailscale Linux installation: https://tailscale.com/docs/install/linux
- Tailscale downloads: https://tailscale.com/download
- Tailscale Funnel: https://tailscale.com/kb/1223/funnel
- Tailscale Serve: https://tailscale.com/kb/1242/tailscale-serve

---

**Project:** Visible Light Communication (VLC/LiFi) System with Optical Camera Communication (OCC) and Dashboard

**Platform:** Raspberry Pi

**Purpose:** Secure remote access and optional public HTTPS access to the project dashboard.
