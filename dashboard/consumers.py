import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer


logger = logging.getLogger(__name__)


class ControlConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4401)
            return
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        try:
            message = json.loads(text_data or "")
        except json.JSONDecodeError:
            await self.send_json({"error": "Message must be valid JSON."})
            return

        if (
            not isinstance(message, dict)
            or message.get("command") != "connection"
            or message.get("value") not in {"connect", "disconnect"}
        ):
            await self.send_json(
                {"error": 'Expected {"command":"connection","value":"connect|disconnect"}.'}
            )
            return

        logger.info(
            "Connection command received from user %s: %s",
            self.scope["user"].get_username(),
            message["value"],
        )
        await self.send_json(
            {
                "command": "connection",
                "value": message["value"],
                "status": "accepted",
            }
        )

    async def send_json(self, content):
        await self.send(text_data=json.dumps(content))
