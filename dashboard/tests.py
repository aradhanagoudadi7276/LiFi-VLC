import json

from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from dashboard.consumers import ControlConsumer


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
        self.assertContains(response, "Camera stream")
        self.assertContains(response, settings.CAMERA_STREAM_URL)
        self.assertEqual(settings.CAMERA_STREAM_URL, "/cam/")
        self.assertContains(response, "/ws/control/")
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

    async def test_authenticated_user_can_send_connection_command(self):
        communicator = WebsocketCommunicator(ControlConsumer.as_asgi(), "/ws/control/")
        communicator.scope["user"] = self.user
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_to(text_data=json.dumps({
            "command": "connection",
            "value": "connect",
        }))
        response = await communicator.receive_json_from()
        self.assertEqual(
            response,
            {
                "command": "connection",
                "value": "connect",
                "status": "accepted",
            },
        )
        await communicator.disconnect()

    async def test_anonymous_user_is_rejected(self):
        communicator = WebsocketCommunicator(ControlConsumer.as_asgi(), "/ws/control/")
        communicator.scope["user"] = AnonymousUser()
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4401)
