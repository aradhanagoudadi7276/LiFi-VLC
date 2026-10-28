import asyncio
import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException


logger = logging.getLogger(__name__)


class ControlConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4401)
            return

        self.transmitter = None
        self.receiver = None
        self._relay_tasks = []
        self._closing_hardware = False
        await self.accept()

    async def disconnect(self, close_code):
        await self._close_hardware()

    async def receive(self, text_data=None, bytes_data=None):
        try:
            message = json.loads(text_data or "")
        except json.JSONDecodeError:
            await self.send_json({"error": "Message must be valid JSON."})
            return

        if not isinstance(message, dict):
            await self.send_json({"error": "Message must be a JSON object."})
            return

        command = message.get("command")
        if command == "connection":
            await self._handle_connection(message.get("value"))
        elif command == "send":
            await self._handle_send(message.get("message"))
        else:
            await self.send_json({"error": "Unknown command. Use connection or send."})

    async def _handle_connection(self, value):
        if value == "disconnect":
            await self._close_hardware()
            await self.send_json(
                {"command": "connection", "value": "disconnect", "status": "accepted"}
            )
            logger.info("LiFi hardware disconnected for user %s", self.scope["user"].get_username())
            return

        if value != "connect":
            await self.send_json(
                {"error": 'Expected {"command":"connection","value":"connect|disconnect"}.'}
            )
            return

        if self.transmitter is not None and self.receiver is not None:
            await self.send_json(
                {"command": "connection", "value": "connect", "status": "accepted"}
            )
            return

        try:
            self.transmitter = await connect(
                settings.LIFI_TRANSMITTER_WEBSOCKET_URL,
                open_timeout=5,
            )
            self.receiver = await connect(
                settings.LIFI_RECEIVER_WEBSOCKET_URL,
                open_timeout=5,
            )
        except (OSError, TimeoutError, ValueError, WebSocketException) as exc:
            await self._close_hardware()
            logger.warning(
                "Unable to connect LiFi hardware for user %s: %s",
                self.scope["user"].get_username(),
                exc,
            )
            await self.send_json(
                {"error": f"Could not connect to the LiFi transmitter and receiver: {exc}"}
            )
            return

        self._relay_tasks = [
            asyncio.create_task(self._relay_events(self.transmitter, "transmitter")),
            asyncio.create_task(self._relay_events(self.receiver, "receiver")),
        ]
        logger.info("LiFi hardware connected for user %s", self.scope["user"].get_username())
        await self.send_json(
            {"command": "connection", "value": "connect", "status": "accepted"}
        )

    async def _handle_send(self, message):
        if self.transmitter is None:
            await self.send_json(
                {"command": "transmission", "status": "error", "message": "Connect to LiFi hardware first."}
            )
            return
        if not isinstance(message, str) or not message:
            await self.send_json(
                {"command": "transmission", "status": "error", "message": "Provide a non-empty message."}
            )
            return
        if len(message) > 500:
            await self.send_json(
                {"command": "transmission", "status": "error", "message": "Maximum message length is 500 characters."}
            )
            return
        if not message.isascii():
            await self.send_json(
                {"command": "transmission", "status": "error", "message": "Only ASCII characters are supported."}
            )
            return

        try:
            await self.transmitter.send(
                json.dumps({"command": "send", "message": message})
            )
        except (ConnectionClosed, OSError) as exc:
            logger.warning("LiFi transmitter send failed: %s", exc)
            await self.send_json(
                {"command": "transmission", "status": "error", "message": "The transmitter connection was lost."}
            )
            return

        await self.send_json(
            {"command": "transmission", "status": "accepted", "message": message}
        )

    async def _relay_events(self, websocket, source):
        try:
            async for raw_event in websocket:
                try:
                    event = json.loads(raw_event)
                except json.JSONDecodeError:
                    await self.send_json(
                        {"source": source, "error": "Received invalid JSON from the hardware service."}
                    )
                    continue
                if isinstance(event, dict):
                    await self.send_json({**event, "source": source})
                else:
                    await self.send_json(
                        {"source": source, "error": "Received an invalid event from the hardware service."}
                    )
        except (ConnectionClosed, OSError) as exc:
            if not self._closing_hardware:
                logger.warning("LiFi %s connection closed: %s", source, exc)
        finally:
            if not self._closing_hardware and self.transmitter is not None:
                await self.send_json(
                    {"error": f"The LiFi {source} connection was closed.", "source": source}
                )
                await self._close_hardware()

    async def _close_hardware(self):
        self._closing_hardware = True
        current_task = asyncio.current_task()
        relay_tasks, self._relay_tasks = self._relay_tasks, []
        for task in relay_tasks:
            if task is not current_task:
                task.cancel()
        if relay_tasks:
            await asyncio.gather(
                *(task for task in relay_tasks if task is not current_task),
                return_exceptions=True,
            )

        transmitter, self.transmitter = self.transmitter, None
        receiver, self.receiver = self.receiver, None
        for websocket in (transmitter, receiver):
            if websocket is not None:
                await websocket.close()
        self._closing_hardware = False

    async def send_json(self, content):
        await self.send(text_data=json.dumps(content))
