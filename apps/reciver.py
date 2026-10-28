
import asyncio
import json
import signal
import time

import spidev
from websockets.asyncio.server import serve

# ---------------- Configuration ----------------

ADC_CHANNEL = 0
BIT_TIME = 0.2
ADC_THRESHOLD = 500

HOST = "0.0.0.0"
PORT = 8765

PREAMBLE = "10101010"

# ---------------- SPI Setup ----------------

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

clients = set()
running = True

# ---------------- Receiver State ----------------

temp = ""
recv = 0
word = ""


def binary_to_char(binary):
    value = int(binary, 2)

    if 32 <= value <= 126:
        return chr(value)

    return "?"


def read_adc(channel):
    if channel < 0 or channel > 7:
        return -1

    adc = spi.xfer2([
        1,
        (8 + channel) << 4,
        0
    ])

    return ((adc[1] & 3) << 8) | adc[2]


async def broadcast(event):
    """Send a JSON event to every connected WebSocket client."""
    if not clients:
        return

    message = json.dumps(event)
    disconnected = set()

    for client in list(clients):
        try:
            await client.send(message)
        except Exception:
            disconnected.add(client)

    clients.difference_update(disconnected)


# ---------------- WebSocket Handler ----------------

async def websocket_handler(websocket):
    clients.add(websocket)

    try:
        await websocket.send(json.dumps({
            "type": "status",
            "status": "connected",
            "message": "Photodiode receiver is running",
            "channel": ADC_CHANNEL,
            "threshold": ADC_THRESHOLD,
            "bit_time": BIT_TIME
        }))

        # Keep the connection alive and optionally accept commands.
        async for message in websocket:
            try:
                command = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON"
                }))
                continue

            if command.get("command") == "status":
                await websocket.send(json.dumps({
                    "type": "status",
                    "status": "running",
                    "clients": len(clients),
                    "channel": ADC_CHANNEL
                }))

    finally:
        clients.discard(websocket)


# ---------------- Receiver Loop ----------------

async def receiver_loop():
    global temp, recv, word, running

    last_status = 0

    print("Photodiode Receiver Microservice")
    print(f"MCP3008 CH{ADC_CHANNEL}")
    print(f"WebSocket: ws://{HOST}:{PORT}")
    print("Press CTRL+C to stop")

    while running:
        try:
            adc_value = read_adc(ADC_CHANNEL)

            if adc_value < 0:
                await asyncio.sleep(BIT_TIME)
                continue

            voltage = (adc_value / 1023.0) * 3.3

            # Preserve the original bit-decoding threshold.
            if adc_value < ADC_THRESHOLD:
                temp += "1"
            else:
                temp += "0"

            # Detect the preamble.
            if PREAMBLE in temp and recv == 0:
                temp = ""
                recv = 1

            # Read the next 8 bits after the preamble.
            elif recv == 1 and len(temp) == 8:
                if temp == PREAMBLE:
                    # A repeated preamble terminates the current word.
                    print(f"Received: {word!r}")

                    await broadcast({
                        "type": "message",
                        "text": word,
                        "timestamp": time.time()
                    })

                    word = ""

                else:
                    char = binary_to_char(temp)
                    word += char

                    print(
                        f"Character: {char!r} | "
                        f"ADC: {adc_value} | "
                        f"Voltage: {voltage:.3f} V"
                    )

                    # Publish each decoded character immediately.
                    await broadcast({
                        "type": "character",
                        "character": char,
                        "text": word,
                        "adc": adc_value,
                        "voltage": round(voltage, 3),
                        "timestamp": time.time()
                    })

                recv = 0
                temp = ""

            elif len(temp) == 32:
                temp = ""

            # Periodic health/status event.
            now = time.monotonic()

            if now - last_status >= 1:
                await broadcast({
                    "type": "receiver_status",
                    "status": "running",
                    "adc": adc_value,
                    "voltage": round(voltage, 3),
                    "connected_clients": len(clients),
                    "timestamp": time.time()
                })

                last_status = now

            await asyncio.sleep(BIT_TIME)

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(f"Receiver error: {exc}")

            await broadcast({
                "type": "error",
                "message": str(exc),
                "timestamp": time.time()
            })

            await asyncio.sleep(1)


# ---------------- Main ----------------

async def main():
    global running

    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: stop_service())
        except NotImplementedError:
            pass

    try:
        async with serve(
            websocket_handler,
            HOST,
            PORT,
            ping_interval=20,
            ping_timeout=20
        ):
            await receiver_loop()

    finally:
        running = False
        spi.close()
        print("SPI closed. Receiver service stopped.")


def stop_service():
    global running
    running = False


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
