import time
import threading
import asyncio
import logging
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Settings, MessageLog
from .hardware.manager import get_receiver
from .websocket_manager import ws_manager

logger = logging.getLogger(__name__)


def binary_to_char(binary_str: str) -> str:
    """Converts an 8-bit binary string to a printable ASCII character."""
    try:
        value = int(binary_str, 2)
        # Printable ASCII range
        if 32 <= value <= 126:
            return chr(value)
        return "?"
    except Exception:
        return "?"


class ReceiverWorker:
    """Manages the background thread that continuously reads and decodes the LiFi signal."""
    def __init__(self):
        self.thread = None
        self.is_running = False
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def start(self, loop: asyncio.AbstractEventLoop):
        with self._lock:
            if self.is_running:
                logger.info("Receiver is already running.")
                return
            
            self.is_running = True
            self._stop_event.clear()
            self.thread = threading.Thread(
                target=self._run_receiver,
                args=(loop,),
                name="LiFiReceiverThread"
            )
            self.thread.daemon = True
            self.thread.start()
            logger.info("Receiver background thread spawned.")

    def stop(self):
        with self._lock:
            if not self.is_running:
                logger.info("Receiver is not running.")
                return
            
            self._stop_event.set()
            self.is_running = False
            logger.info("Receiver stop signal issued.")

    def _run_receiver(self, loop: asyncio.AbstractEventLoop):
        db: Session = SessionLocal()
        rx = None
        
        try:
            # 1. Fetch settings from SQLite
            settings = db.query(Settings).first()
            if not settings:
                settings = Settings()
                db.add(settings)
                db.commit()
                db.refresh(settings)

            # 2. Get and setup Receiver hardware
            rx = get_receiver(settings.use_mock)
            rx.setup(settings.spi_port, settings.spi_device, settings.spi_speed)
            
            if settings.use_mock and hasattr(rx, 'set_noise_level'):
                rx.set_noise_level(settings.noise_level)

            temp = ""
            recv_state = 0
            word = ""
            accumulated_binary = []

            logger.info("Receiver thread loop active. Monitoring photodiode voltage...")

            while not self._stop_event.is_set():
                # Re-fetch settings on every iteration to adapt to live UI configuration changes
                settings = db.query(Settings).first()
                if not settings:
                    settings = Settings()

                # Sync mock noise if changed from control panel
                if settings.use_mock and hasattr(rx, 'set_noise_level'):
                    rx.set_noise_level(settings.noise_level)

                # Read from SPI ADC
                adc_value = rx.read_adc(settings.adc_channel)
                voltage = (adc_value / 1023.0) * 3.3

                # Decode bit (LED ON pulls down photodiode channel below threshold voltage)
                if voltage < settings.threshold_voltage:
                    bit = '1'
                else:
                    bit = '0'

                # State Machine
                if recv_state == 0:
                    temp += bit
                    if '10101010' in temp:
                        temp = ""
                        recv_state = 1
                        accumulated_binary.append("10101010")
                        logger.info("Synchronization preamble '10101010' matched. Awaiting data...")
                    elif len(temp) >= 32:
                        temp = ""
                
                elif recv_state == 1:
                    temp += bit
                    if len(temp) == 8:
                        accumulated_binary.append(temp)
                        
                        # Stop sequence is matching the preamble byte value as data
                        if temp == '10101010':
                            logger.info(f"Stop sequence detected. Received message: '{word}'")
                            
                            # Write message to database log
                            new_msg = MessageLog(
                                direction="RECEIVED",
                                text=word,
                                binary_data="".join(accumulated_binary),
                                status="SUCCESS"
                            )
                            db.add(new_msg)
                            db.commit()

                            # Notify clients over websocket
                            asyncio.run_coroutine_threadsafe(ws_manager.broadcast({
                                "event": "rx_complete",
                                "data": {
                                    "id": new_msg.id,
                                    "text": word,
                                    "binary_data": new_msg.binary_data
                                }
                            }), loop)

                            # Reset buffers
                            word = ""
                            accumulated_binary = []
                        else:
                            char = binary_to_char(temp)
                            word += char
                            logger.info(f"Decoded: {temp} -> '{char}' | Word so far: '{word}'")

                            # Notify clients of progressive decoding character
                            asyncio.run_coroutine_threadsafe(ws_manager.broadcast({
                                "event": "rx_char",
                                "data": {
                                    "char": char,
                                    "word": word,
                                    "binary": temp
                                }
                            }), loop)

                        # Reset state back to search for next preamble
                        recv_state = 0
                        temp = ""

                # Broadcast live signal and state telemetry (Scope wave, bit readings, config lines)
                telemetry = {
                    "event": "rx_telemetry",
                    "data": {
                        "voltage": round(voltage, 3),
                        "adc_value": adc_value,
                        "bit": bit,
                        "temp_buffer": temp,
                        "recv_state": recv_state,
                        "word": word,
                        "threshold": settings.threshold_voltage
                    }
                }
                asyncio.run_coroutine_threadsafe(ws_manager.broadcast(telemetry), loop)

                # Delay for bit-width duration
                time.sleep(settings.bit_time)

            logger.info("Receiver thread terminating.")
            rx.cleanup()

        except Exception as e:
            logger.error(f"Fatal error in Receiver thread loop: {e}")
            if rx:
                try:
                    rx.cleanup()
                except Exception:
                    pass
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast({
                "event": "rx_failed",
                "data": {"error": str(e)}
            }), loop)
            
        finally:
            with self._lock:
                self.is_running = False
            db.close()


# Global receiver worker instance
rx_worker = ReceiverWorker()
