#!/bin/sh
set -eu

if ! command -v tailscale >/dev/null 2>&1; then
  printf 'Error: tailscale is not installed or is not on PATH.\n' >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  printf 'Error: curl is required to check the local services.\n' >&2
  exit 1
fi

if ! command -v caddy >/dev/null 2>&1; then
  printf 'Error: Caddy is not installed or is not on PATH.\n' >&2
  exit 1
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
caddyfile="$script_dir/../config/Caddyfile"

caddy validate --config "$caddyfile"

if ! curl --fail --silent --show-error --output /dev/null --max-time 5 http://127.0.0.1:8000/; then
  printf 'Error: Django is not responding at http://127.0.0.1:8000/.\n' >&2
  printf 'Start Django on 127.0.0.1:8000, then run this script again.\n' >&2
  exit 1
fi

if ! curl --fail --silent --show-error --output /dev/null --max-time 5 http://127.0.0.1:8889/cam/; then
  printf 'Error: MediaMTX WebRTC player is not responding at http://127.0.0.1:8889/cam/.\n' >&2
  printf 'Start MediaMTX with WebRTC enabled, then run this script again.\n' >&2
  exit 1
fi

printf 'Reloading the running Caddy service with the project configuration ...\n'
sudo caddy reload --config "$caddyfile"

if ! curl --fail --silent --show-error --output /dev/null --max-time 5 http://127.0.0.1:8080/; then
  printf 'Error: Caddy is not responding at http://127.0.0.1:8080/.\n' >&2
  printf 'Check the Caddy service and config/Caddyfile, then run this script again.\n' >&2
  exit 1
fi

if ! curl --fail --silent --show-error --output /dev/null --max-time 5 http://127.0.0.1:8080/cam/; then
  printf 'Error: Caddy cannot serve the camera at http://127.0.0.1:8080/cam/.\n' >&2
  printf 'Check the Caddy and MediaMTX configuration, then run this script again.\n' >&2
  exit 1
fi

printf 'Warning: Funnel makes the Django app publicly accessible.\n'
printf 'Ensure the starter password has been changed and DJANGO_DEBUG=false.\n'
printf 'Setting the Funnel HTTPS root route -> http://127.0.0.1:8080 (Caddy) ...\n'
sudo tailscale funnel --bg --set-path=/ http://127.0.0.1:8080

printf 'Removing the old direct /cam Funnel route, if present ...\n'
sudo tailscale funnel --https=443 --set-path=/cam off

printf '\nCurrent Funnel configuration:\n'
sudo tailscale funnel status
