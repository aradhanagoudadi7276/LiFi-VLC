import time
import threading
import asyncio
import logging
import spidev

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Settings, MessageLog
from .websocket_manager import ws_manager

logger = logging.getLogger(__name__)


def binary_to_char(binary: str) -> str:
    """
    Convert an 8-bit binary string to printable ASCII.
    """

    try:
        value = int(binary, 2)

        if 32 <= value <= 126:
            return chr(value)

        return "?"

    except Exception:
        return "?"


class ReceiverWorker:
    """
    Background VLC receiver using MCP3008 + SPI.

    Receiver logic follows the working standalone receiver:

        ADC == 0  -> bit 1
        ADC != 0  -> bit 0

    Transmission format:

        10101010 + 8-bit ASCII character

    Stop character:

        10101010 + 10101010
    """

    def __init__(self):

        self.thread = None
        self.is_running = False

        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # MCP3008 SPI object
        self.spi = None

    # ==============================================================
    # START RECEIVER
    # ==============================================================

    def start(self, loop: asyncio.AbstractEventLoop):

        with self._lock:

            if self.is_running:
                logger.info(
                    "Receiver is already running."
                )
                return

            self.is_running = True
            self._stop_event.clear()

            self.thread = threading.Thread(
                target=self._run_receiver,
                args=(loop,),
                name="LiFiReceiverThread",
                daemon=True
            )

            self.thread.start()

            logger.info(
                "Receiver background thread spawned."
            )

    # ==============================================================
    # STOP RECEIVER
    # ==============================================================

    def stop(self):

        with self._lock:

            if not self.is_running:
                logger.info(
                    "Receiver is not running."
                )
                return

            self._stop_event.set()

            logger.info(
                "Receiver stop signal issued."
            )

    # ==============================================================
    # MCP3008 READ
    # ==============================================================

    def read_adc(self, channel: int) -> int:

        if channel < 0 or channel > 7:
            raise ValueError(
                f"Invalid MCP3008 channel: {channel}"
            )

        adc = self.spi.xfer2(
            [
                1,
                (8 + channel) << 4,
                0
            ]
        )

        value = (
            ((adc[1] & 3) << 8)
            | adc[2]
        )

        return value

    # ==============================================================
    # WEBSOCKET HELPER
    # ==============================================================

    def broadcast(self, loop, data):

        try:

            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast(data),
                loop
            )

        except Exception as e:

            logger.error(
                f"WebSocket broadcast error: {e}"
            )

    # ==============================================================
    # RECEIVER THREAD
    # ==============================================================

    def _run_receiver(
        self,
        loop: asyncio.AbstractEventLoop
    ):

        db: Session = SessionLocal()

        try:

            # ======================================================
            # 1. LOAD SETTINGS
            # ======================================================

            settings = db.query(Settings).first()

            if not settings:

                settings = Settings()

                db.add(settings)
                db.commit()
                db.refresh(settings)

            adc_channel = settings.adc_channel
            bit_time = settings.bit_time

            # ======================================================
            # 2. SETUP MCP3008 SPI
            # ======================================================

            self.spi = spidev.SpiDev()

            self.spi.open(
                settings.spi_port,
                settings.spi_device
            )

            self.spi.max_speed_hz = settings.spi_speed

            logger.info(
                "MCP3008 SPI initialized | "
                f"Bus={settings.spi_port} | "
                f"Device={settings.spi_device} | "
                f"Speed={settings.spi_speed} | "
                f"Channel={adc_channel}"
            )

            # ======================================================
            # 3. RECEIVER VARIABLES
            # ======================================================

            temp = ""

            # 0 = searching for preamble
            # 1 = receiving character
            recv = 0

            word = ""

            accumulated_binary = []

            logger.info(
                "Photodiode receiver started."
            )

            # ======================================================
            # 4. RECEIVE LOOP
            # ======================================================

            while not self._stop_event.is_set():

                # --------------------------------------------------
                # Reload settings
                # --------------------------------------------------

                settings = db.query(
                    Settings
                ).first()

                if not settings:
                    settings = Settings()

                adc_channel = settings.adc_channel
                bit_time = settings.bit_time

                # --------------------------------------------------
                # Read MCP3008
                # --------------------------------------------------

                adc_value = self.read_adc(
                    adc_channel
                )

                voltage = (
                    adc_value / 1023.0
                ) * 3.3

                # ==================================================
                # BIT DECODING
                # ==================================================
                #
                # This matches your working standalone receiver:
                #
                # ADC = 0     -> 1
                # ADC != 0    -> 0
                #
                # ==================================================

                if adc_value == 0:

                    bit = "1"

                else:

                    bit = "0"

                temp += bit

                # ==================================================
                # STATE 0
                # SEARCH FOR PREAMBLE
                # ==================================================

                if recv == 0:

                    if "10101010" in temp:

                        logger.info(
                            "Synchronization preamble "
                            "'10101010' detected."
                        )

                        # Keep only data after preamble
                        temp = ""

                        recv = 1

                        accumulated_binary.append(
                            "10101010"
                        )

                    elif len(temp) >= 32:

                        # Prevent unlimited buffer growth
                        temp = ""

                # ==================================================
                # STATE 1
                # RECEIVE 8-BIT CHARACTER
                # ==================================================

                elif recv == 1:

                    if len(temp) == 8:

                        binary_data = temp

                        accumulated_binary.append(
                            binary_data
                        )

                        # ==========================================
                        # STOP CHARACTER
                        # ==========================================

                        if binary_data == "10101010":

                            logger.info(
                                "Stop sequence detected."
                            )

                            logger.info(
                                f"Received message: '{word}'"
                            )

                            # --------------------------------------
                            # Save received message
                            # --------------------------------------

                            new_msg = MessageLog(
                                direction="RECEIVED",
                                text=word,
                                binary_data="".join(
                                    accumulated_binary
                                ),
                                status="SUCCESS"
                            )

                            db.add(new_msg)
                            db.commit()
                            db.refresh(new_msg)

                            # --------------------------------------
                            # Notify dashboard
                            # --------------------------------------

                            self.broadcast(
                                loop,
                                {
                                    "event": "rx_complete",

                                    "data": {
                                        "id": new_msg.id,
                                        "text": word,
                                        "binary_data":
                                            new_msg.binary_data
                                    }
                                }
                            )

                            # --------------------------------------
                            # Reset message
                            # --------------------------------------

                            word = ""

                            accumulated_binary = []

                        # ==========================================
                        # NORMAL CHARACTER
                        # ==========================================

                        else:

                            char = binary_to_char(
                                binary_data
                            )

                            word += char

                            logger.info(
                                f"Decoded: "
                                f"{binary_data} -> "
                                f"'{char}' | "
                                f"Word: '{word}'"
                            )

                            # --------------------------------------
                            # Send character to dashboard
                            # --------------------------------------

                            self.broadcast(
                                loop,
                                {
                                    "event": "rx_char",

                                    "data": {
                                        "char": char,
                                        "word": word,
                                        "binary":
                                            binary_data
                                    }
                                }
                            )

                        # ------------------------------------------
                        # Return to preamble search
                        # ------------------------------------------

                        recv = 0
                        temp = ""

                # ==================================================
                # LIVE TELEMETRY
                # ==================================================

                telemetry = {

                    "event": "rx_telemetry",

                    "data": {

                        "voltage": round(
                            voltage,
                            3
                        ),

                        "adc_value": adc_value,

                        "bit": bit,

                        "temp_buffer": temp,

                        "recv_state": recv,

                        "word": word,

                        "threshold":
                            settings.threshold_voltage
                    }
                }

                self.broadcast(
                    loop,
                    telemetry
                )

                # ==================================================
                # BIT TIMING
                # ==================================================

                time.sleep(bit_time)

            logger.info(
                "Receiver stop requested."
            )

        except Exception as e:

            logger.exception(
                f"Fatal error in receiver thread: {e}"
            )

            self.broadcast(
                loop,
                {
                    "event": "rx_failed",

                    "data": {
                        "error": str(e)
                    }
                }
            )

        finally:

            # ======================================================
            # CLOSE SPI
            # ======================================================

            if self.spi:

                try:

                    self.spi.close()

                    logger.info(
                        "MCP3008 SPI closed."
                    )

                except Exception as e:

                    logger.error(
                        f"Error closing SPI: {e}"
                    )

                self.spi = None

            # ======================================================
            # RECEIVER STATE
            # ======================================================

            with self._lock:

                self.is_running = False

            db.close()

            logger.info(
                "Receiver thread terminated."
            )


# ==============================================================
# GLOBAL RECEIVER WORKER
# ==============================================================

rx_worker = ReceiverWorker()