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

if ! curl --fail --silent --show-error --output /dev/null --max-time 5 http://127.0.0.1:8000/; then
  printf 'Error: Django is not responding at http://127.0.0.1:8000/.\n' >&2
  printf 'Start Django on 127.0.0.1:8000, then run this script again.\n' >&2
  exit 1
fi

if ! curl --fail --silent --show-error --output /dev/null --max-time 5 http://127.0.0.1:8888/cam/; then
  printf 'Error: MediaMTX HLS player is not responding at http://127.0.0.1:8888/cam.\n' >&2
  printf 'Start MediaMTX with HLS enabled, then run this script again.\n' >&2
  exit 1
fi

printf 'Warning: Funnel makes the Django app publicly accessible.\n'
printf 'Ensure the starter password has been changed and DJANGO_DEBUG=false.\n'
printf 'Setting Funnel route / -> http://127.0.0.1:8000 ...\n'
sudo tailscale funnel --bg --set-path=/ http://127.0.0.1:8000

printf 'Setting Funnel route /cam -> http://127.0.0.1:8888/cam/ ...\n'
sudo tailscale funnel --bg --set-path=/cam http://127.0.0.1:8888/cam/

printf '\nCurrent Funnel configuration:\n'
sudo tailscale funnel status
