import time
import threading
import asyncio
import logging
import RPi.GPIO as GPIO

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Settings, MessageLog
from .websocket_manager import ws_manager

logger = logging.getLogger(__name__)


class TransmitterWorker:
    """Manages VLC transmission in a background thread."""

    def __init__(self):
        self.thread = None
        self.is_transmitting = False
        self._lock = threading.Lock()

    def transmit(self, message: str, loop: asyncio.AbstractEventLoop):
        """
        Start transmission in a background thread.
        """

        with self._lock:

            if self.is_transmitting:
                raise RuntimeError(
                    "A transmission is already in progress."
                )

            self.is_transmitting = True

            self.thread = threading.Thread(
                target=self._run_transmission,
                args=(message, loop),
                name="LiFiTransmitterThread",
                daemon=True
            )

            self.thread.start()

    def _run_transmission(
        self,
        message: str,
        loop: asyncio.AbstractEventLoop
    ):
        db: Session = SessionLocal()

        log_entry = None
        gpio_initialized = False

        try:

            # ==========================================================
            # 1. LOAD SETTINGS
            # ==========================================================

            settings = db.query(Settings).first()

            if not settings:
                settings = Settings()
                db.add(settings)
                db.commit()
                db.refresh(settings)

            bit_time = settings.bit_time

            # Use database LED pin if configured.
            # Otherwise default to GPIO 18.
            led_pin = settings.led_pin or 18

            logger.info(
                f"VLC Transmission started | "
                f"LED GPIO: {led_pin} | "
                f"BIT_TIME: {bit_time}"
            )

            # ==========================================================
            # 2. GPIO SETUP
            # ==========================================================

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(led_pin, GPIO.OUT)

            gpio_initialized = True

            # Start with LED OFF
            GPIO.output(led_pin, GPIO.LOW)

            # ==========================================================
            # 3. CREATE DATABASE LOG
            # ==========================================================

            log_entry = MessageLog(
                direction="SENT",
                text=message,
                binary_data="",
                status="IN_PROGRESS"
            )

            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)

            # ==========================================================
            # 4. WEBSOCKET TELEMETRY
            # ==========================================================

            def send_ws_update(
                bit: str,
                char: str,
                progress: float
            ):

                # Match the actual GPIO logic:
                #
                # bit 1 -> GPIO HIGH
                # bit 0 -> GPIO LOW
                #
                # Voltage is only a dashboard representation.

                voltage = 3.3 if bit == "1" else 0.0

                data = {
                    "event": "tx_bit",

                    "data": {
                        "bit": bit,
                        "led_on": bit == "1",
                        "voltage": voltage,
                        "char": char,
                        "progress": progress
                    }
                }

                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast(data),
                    loop
                )

            # ==========================================================
            # 5. HELPER FUNCTIONS
            # ==========================================================

            def led_on():

                GPIO.output(
                    led_pin,
                    GPIO.HIGH
                )

            def led_off():

                GPIO.output(
                    led_pin,
                    GPIO.LOW
                )

            def send_bits(bits: str, char: str, progress: float):

                for bit in bits:

                    if bit == "1":
                        led_on()
                    else:
                        led_off()

                    # Send current bit information to dashboard
                    send_ws_update(
                        bit,
                        char,
                        progress
                    )

                    # Maintain exact bit duration
                    time.sleep(bit_time)

            # ==========================================================
            # 6. TRANSMISSION
            # ==========================================================

            full_binary_sequence = []

            # Total characters:
            #
            # MESSAGE characters
            # +
            # STOP character
            #
            total_chars = len(message) + 1

            char_count = 0

            logger.info(
                f"Message: {message}"
            )

            # ----------------------------------------------------------
            # Send message characters
            # ----------------------------------------------------------

            for char in message:

                # Convert character to 8-bit ASCII
                original_bits = format(
                    ord(char),
                    "08b"
                )

                # Add synchronization preamble
                bits = (
                    "10101010"
                    +
                    original_bits
                )

                full_binary_sequence.append(bits)

                char_count += 1

                progress = round(
                    (char_count / total_chars) * 100,
                    1
                )

                logger.info(
                    f"Sending '{char}' -> {bits}"
                )

                send_bits(
                    bits,
                    char,
                    progress
                )

            # ==========================================================
            # 7. STOP CHARACTER
            # ==========================================================

            # Same as:
            #
            # send_byte(chr(int("10101010", 2)))
            #
            # 10101010 = preamble
            # 10101010 = character value 170
            #
            stop_bits = (
                "10101010"
                "10101010"
            )

            full_binary_sequence.append(
                stop_bits
            )

            char_count += 1

            progress = 100.0

            logger.info(
                "Sending STOP sequence..."
            )

            send_bits(
                stop_bits,
                "STOP",
                progress
            )

            # ==========================================================
            # 8. TURN LED OFF
            # ==========================================================

            led_off()

            # ==========================================================
            # 9. CLEANUP GPIO
            # ==========================================================

            GPIO.cleanup()

            gpio_initialized = False

            # ==========================================================
            # 10. SAVE TRANSMISSION RESULT
            # ==========================================================

            log_entry.binary_data = "".join(
                full_binary_sequence
            )

            log_entry.status = "SUCCESS"

            db.commit()

            logger.info(
                "VLC transmission completed successfully."
            )

            # ==========================================================
            # 11. NOTIFY FRONTEND
            # ==========================================================

            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast(
                    {
                        "event": "tx_complete",

                        "data": {
                            "id": log_entry.id,
                            "text": message,
                            "binary_data": log_entry.binary_data
                        }
                    }
                ),
                loop
            )

        except Exception as e:

            logger.exception(
                f"Error in transmitter thread: {e}"
            )

            # ==========================================================
            # GPIO SAFETY
            # ==========================================================

            if gpio_initialized:

                try:
                    GPIO.output(
                        led_pin,
                        GPIO.LOW
                    )
                except Exception:
                    pass

                try:
                    GPIO.cleanup()
                except Exception:
                    pass

            # ==========================================================
            # DATABASE FAILURE STATUS
            # ==========================================================

            if log_entry:

                try:

                    log_entry.status = "FAILED"

                    db.commit()

                except Exception:
                    db.rollback()

            # ==========================================================
            # NOTIFY FRONTEND
            # ==========================================================

            try:

                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast(
                        {
                            "event": "tx_failed",

                            "data": {
                                "error": str(e)
                            }
                        }
                    ),
                    loop
                )

            except Exception:
                pass

        finally:

            # ==========================================================
            # RESET WORKER STATE
            # ==========================================================

            with self._lock:
                self.is_transmitting = False

            db.close()


# ==============================================================
# GLOBAL TRANSMITTER WORKER
# ==============================================================

tx_worker = TransmitterWorker()