
import asyncio
import json
import websockets

# Update this with your Raspberry Pi IP address
PI_IP = "10.14.131.72"

TX_URL = f"ws://{PI_IP}:8766"
RX_URL = f"ws://{PI_IP}:8765"

MESSAGE = "Hello World"


async def main():
    print("Connecting to VLC transmitter and receiver...")

    try:
        async with (
            websockets.connect(TX_URL) as tx,
            websockets.connect(RX_URL) as rx
        ):
            print("Connected to both services.")

            # Receiver task: listen for decoded characters/messages
            async def receive_messages():
                async for raw in rx:
                    data = json.loads(raw)

                    if data.get("type") == "status":
                        print("Receiver:", data.get("message", data.get("status")))

                    elif data.get("type") == "character":
                        print("Received character:", data.get("character"))

                    elif data.get("type") == "message":
                        received = data.get("text", "")
                        print("Complete message received:", repr(received))

                        if received.strip() == MESSAGE:
                            print("SUCCESS: Hello World received!")
                        else:
                            print("Message differs from expected text.")

            receiver_task = asyncio.create_task(receive_messages())

            # Allow receiver listener to start
            await asyncio.sleep(1)

            print(f"Sending: {MESSAGE}")

            await tx.send(json.dumps({
                "command": "send",
                "message": MESSAGE
            }))

            # Wait for transmission to finish.
            # At 0.2 seconds per bit, 11 characters plus
            # the end marker take approximately 19.2 seconds.
            async for raw in tx:
                data = json.loads(raw)
                event_type = data.get("type")

                if event_type == "queued":
                    print("Message queued:", data.get("message"))

                elif event_type == "transmitting":
                    print("Optical transmission started.")

                elif event_type == "transmitted":
                    print("Optical transmission completed.")
                    break

                elif event_type == "error":
                    print("Transmitter error:", data.get("message"))

            # Keep the receiver listening briefly after transmission.
            await asyncio.sleep(3)

            receiver_task.cancel()
            try:
                await receiver_task
            except asyncio.CancelledError:
                pass

    except OSError as exc:
        print("Cannot connect to the WebSocket services:", exc)
        print("Check the Raspberry Pi IP, ports, and systemd services.")

    except websockets.exceptions.WebSocketException as exc:
        print("WebSocket error:", exc)


if __name__ == "__main__":
    asyncio.run(main())
