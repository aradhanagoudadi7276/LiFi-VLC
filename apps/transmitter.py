
import asyncio
import json
import signal
import time

import RPi.GPIO as GPIO
from websockets.asyncio.server import serve

# ---------------- Configuration ----------------

LED_PIN = 18
BIT_TIME = 0.2

HOST = "0.0.0.0"
PORT = 8766

PREAMBLE = "10101010"

# ---------------- GPIO Setup ----------------

GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)

clients = set()
message_queue = asyncio.Queue()
running = True


def led_on():
    GPIO.output(LED_PIN, GPIO.HIGH)


def led_off():
    GPIO.output(LED_PIN, GPIO.LOW)


def send_byte(char):
    """Transmit one character with its preamble."""
    original_bits = format(ord(char), "08b")
    bits = PREAMBLE + original_bits

    for bit in bits:
        if bit == "1":
            led_on()
        else:
            led_off()

        time.sleep(BIT_TIME)

    led_off()


def transmit_message(message):
    """Transmit a message followed by the end marker."""
    for char in message:
        send_byte(char)

    # Preserve the original end marker.
    send_byte(chr(int(PREAMBLE, 2)))

    led_off()


async def broadcast(event):
    if not clients:
        return

    payload = json.dumps(event)
    disconnected = set()

    for client in list(clients):
        try:
            await client.send(payload)
        except Exception:
            disconnected.add(client)

    clients.difference_update(disconnected)


async def websocket_handler(websocket):
    clients.add(websocket)

    try:
        await websocket.send(json.dumps({
            "type": "status",
            "status": "connected",
            "message": "VLC transmitter is ready",
            "led_pin": LED_PIN,
            "bit_time": BIT_TIME
        }))

        async for raw_message in websocket:
            try:
                data = json.loads(raw_message)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON"
                }))
                continue

            command = data.get("command")

            if command == "send":
                message = data.get("message")

                if not isinstance(message, str) or not message:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Provide a non-empty message"
                    }))
                    continue

                if len(message) > 500:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Maximum message length is 500 characters"
                    }))
                    continue

                # This transmitter uses 8-bit ASCII.
                if not message.isascii():
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Only ASCII characters are supported"
                    }))
                    continue

                await message_queue.put(message)

                await websocket.send(json.dumps({
                    "type": "queued",
                    "message": message,
                    "queue_size": message_queue.qsize()
                }))

            elif command == "status":
                await websocket.send(json.dumps({
                    "type": "status",
                    "status": "running",
                    "led_pin": LED_PIN,
                    "queue_size": message_queue.qsize()
                }))

            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Unknown command. Use send or status."
                }))

    finally:
        clients.discard(websocket)


async def transmitter_worker():
    """Transmit queued messages sequentially."""
    while running:
        message = await message_queue.get()

        try:
            print(f"Transmitting: {message!r}")

            await broadcast({
                "type": "transmitting",
                "message": message,
                "timestamp": time.time()
            })

            # Run blocking GPIO timing outside the event loop,
            # so WebSocket connections remain responsive.
            await asyncio.to_thread(transmit_message, message)

            print(f"Transmission complete: {message!r}")

            await broadcast({
                "type": "transmitted",
                "message": message,
                "timestamp": time.time()
            })

        except Exception as exc:
            print(f"Transmission error: {exc}")

            await broadcast({
                "type": "error",
                "message": str(exc),
                "timestamp": time.time()
            })

        finally:
            led_off()
            message_queue.task_done()


async def main():
    global running

    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_service)

    worker = asyncio.create_task(transmitter_worker())

    try:
        async with serve(
            websocket_handler,
            HOST,
            PORT,
            ping_interval=20,
            ping_timeout=20
        ):
            print("VLC Transmitter WebSocket Microservice")
            print(f"LED GPIO: {LED_PIN}")
            print(f"WebSocket: ws://{HOST}:{PORT}")
            print("Waiting for messages...")

            await asyncio.Event().wait()

    finally:
        running = False
        worker.cancel()

        try:
            await worker
        except asyncio.CancelledError:
            pass

        led_off()
        GPIO.cleanup()
        print("Transmitter stopped. GPIO cleaned up.")


def stop_service():
    global running
    running = False


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
