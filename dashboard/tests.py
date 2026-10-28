import asyncio
import json
from unittest.mock import AsyncMock, patch

from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from dashboard.consumers import ControlConsumer


class FakeHardwareSocket:
    def __init__(self):
        self.sent = []
        self.closed = False
        self.events = asyncio.Queue()

    async def send(self, message):
        self.sent.append(message)

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        event = await self.events.get()
        if event is None:
            raise StopAsyncIteration
        return event


class DashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin",
            password="admin@123",
        )

    def test_dashboard_requires_login(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/login/?next=/")

    def test_login_shows_dashboard(self):
        self.assertTrue(self.client.login(username="admin", password="admin@123"))
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Live camera stream")
        self.assertContains(
            response,
            '<video class="stream" id="camera-video" autoplay muted playsinline disablepictureinpicture disableremoteplayback',
        )
        self.assertNotContains(response, "<iframe")
        self.assertNotContains(response, 'id="camera-video" controls')
        self.assertContains(response, "peer.connectionState === \"failed\"")
        self.assertContains(response, settings.CAMERA_STREAM_URL)
        self.assertEqual(settings.CAMERA_STREAM_URL, "/cam/")
        self.assertContains(response, "/ws/control/")
        self.assertContains(response, "Photodiode signal")
        self.assertContains(response, "Optical network")
        self.assertContains(response, "Transmitter")
        self.assertContains(response, "Receiver")
        self.assertContains(response, "ADC · 0–1023")
        self.assertContains(response, "Voltage · 0–3.3 V")
        self.assertContains(response, 'id="network-stage"')
        self.assertContains(response, "Data exchange")
        self.assertContains(response, 'grid-template-areas: "network exchange" "graph camera"')
        self.assertContains(response, 'id="connect-button"')
        self.assertContains(response, "Sent messages and decoded responses appear here")
        self.assertContains(response, "--chart-signal: #0891B2")
        self.assertContains(response, "--color-primary: #2563EB")

    def test_tailscale_origin_is_csrf_trusted(self):
        self.assertIn(
            "https://vlc-server.tail4db684.ts.net",
            settings.CSRF_TRUSTED_ORIGINS,
        )

    def test_login_page_uses_configured_theme(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "--color-background: #F9FAFB")
        self.assertContains(response, "--component-button-primary_background: #2563EB")


class ControlConsumerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin",
            password="admin@123",
        )

    async def test_authenticated_user_can_connect_send_and_disconnect(self):
        transmitter = FakeHardwareSocket()
        receiver = FakeHardwareSocket()
        with patch(
            "dashboard.consumers.connect",
            new_callable=AsyncMock,
            side_effect=[transmitter, receiver],
        ) as hardware_connect:
            communicator = WebsocketCommunicator(
                ControlConsumer.as_asgi(),
                "/ws/control/",
            )
            communicator.scope["user"] = self.user
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.send_to(text_data=json.dumps({
                "command": "connection",
                "value": "connect",
            }))
            self.assertEqual(
                await communicator.receive_json_from(),
                {
                    "command": "connection",
                    "value": "connect",
                    "status": "accepted",
                },
            )
            self.assertEqual(hardware_connect.await_count, 2)

            await receiver.events.put(json.dumps({
                "type": "character",
                "character": "H",
                "text": "H",
                "adc": 470,
                "voltage": 1.516,
                "timestamp": 123.0,
            }))
            self.assertEqual(
                await communicator.receive_json_from(),
                {
                    "type": "character",
                    "character": "H",
                    "text": "H",
                    "adc": 470,
                    "voltage": 1.516,
                    "timestamp": 123.0,
                    "source": "receiver",
                },
            )

            await communicator.send_to(text_data=json.dumps({
                "command": "send",
                "message": "Hello World",
            }))
            self.assertEqual(
                await communicator.receive_json_from(),
                {
                    "command": "transmission",
                    "status": "accepted",
                    "message": "Hello World",
                },
            )
            self.assertEqual(
                json.loads(transmitter.sent[0]),
                {"command": "send", "message": "Hello World"},
            )

            await communicator.send_to(text_data=json.dumps({
                "command": "connection",
                "value": "disconnect",
            }))
            self.assertEqual(
                await communicator.receive_json_from(),
                {
                    "command": "connection",
                    "value": "disconnect",
                    "status": "accepted",
                },
            )
            self.assertTrue(transmitter.closed)
            self.assertTrue(receiver.closed)
            await communicator.disconnect()

    async def test_connect_reports_unavailable_hardware(self):
        with patch(
            "dashboard.consumers.connect",
            new_callable=AsyncMock,
            side_effect=OSError("connection refused"),
        ):
            communicator = WebsocketCommunicator(
                ControlConsumer.as_asgi(),
                "/ws/control/",
            )
            communicator.scope["user"] = self.user
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.send_to(text_data=json.dumps({
                "command": "connection",
                "value": "connect",
            }))
            response = await communicator.receive_json_from()
            self.assertIn("Could not connect", response["error"])
            await communicator.disconnect()

    async def test_send_requires_hardware_connection(self):
        communicator = WebsocketCommunicator(
            ControlConsumer.as_asgi(),
            "/ws/control/",
        )
        communicator.scope["user"] = self.user
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.send_to(text_data=json.dumps({
            "command": "send",
            "message": "Hello",
        }))
        response = await communicator.receive_json_from()
        self.assertEqual(response["command"], "transmission")
        self.assertEqual(response["status"], "error")
        await communicator.disconnect()

    async def test_anonymous_user_is_rejected(self):
        communicator = WebsocketCommunicator(ControlConsumer.as_asgi(), "/ws/control/")
        communicator.scope["user"] = AnonymousUser()
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4401)
