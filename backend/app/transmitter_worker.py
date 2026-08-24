import time
import threading
import asyncio
import logging
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Settings, MessageLog
from .hardware.manager import get_transmitter
from .websocket_manager import ws_manager

logger = logging.getLogger(__name__)

class TransmitterWorker:
    """Manages transmission of messages in a background thread."""
    def __init__(self):
        self.thread = None
        self.is_transmitting = False
        self._lock = threading.Lock()

    def transmit(self, message: str, loop: asyncio.AbstractEventLoop):
        with self._lock:
            if self.is_transmitting:
                raise RuntimeError("A transmission is already in progress.")
            
            self.is_transmitting = True
            self.thread = threading.Thread(
                target=self._run_transmission, 
                args=(message, loop),
                name="LiFiTransmitterThread"
            )
            self.thread.daemon = True
            self.thread.start()

    def _run_transmission(self, message: str, loop: asyncio.AbstractEventLoop):
        db: Session = SessionLocal()
        log_entry = None
        tx = None
        
        try:
            # 1. Load settings
            settings = db.query(Settings).first()
            if not settings:
                settings = Settings()
                db.add(settings)
                db.commit()
                db.refresh(settings)

            # 2. Setup Transmitter hardware
            tx = get_transmitter(settings.use_mock)
            tx.setup(settings.led_pin)

            # 3. Create database log entry
            log_entry = MessageLog(
                direction="SENT",
                text=message,
                binary_data="",
                status="IN_PROGRESS"
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)

            bit_time = settings.bit_time
            full_binary_sequence = []

            # Helper function to push telemetry safely to the main event loop
            def send_ws_update(bit: str, char: str, progress: float):
                # Simulated voltage output based on bit logic (1 = Low V, 0 = High V)
                voltage = 0.05 if bit == "1" else 3.25
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
                asyncio.run_coroutine_threadsafe(ws_manager.broadcast(data), loop)

            # Calculate total characters to transmit (message + stop char)
            total_chars = len(message) + 1
            char_count = 0

            # 4. Transmit characters
            for idx, char in enumerate(message):
                original_bits = format(ord(char), "08b")
                # Prepend the synchronization preamble (10101010)
                bits = "10101010" + original_bits
                full_binary_sequence.append(bits)

                char_count += 1
                progress = round((char_count / total_chars) * 100, 1)

                logger.info(f"Transmitting char: '{char}' -> Bin: {bits}")
                for bit in bits:
                    tx.set_led(bit == "1")
                    send_ws_update(bit, char, progress)
                    time.sleep(bit_time)

            # 5. Transmit stop indicator (preamble 10101010 + char value 170 which is 10101010)
            stop_bits = "1010101010101010"
            full_binary_sequence.append(stop_bits)
            char_count += 1
            progress = 100.0

            logger.info("Transmitting stop sequence...")
            for bit in stop_bits:
                tx.set_led(bit == "1")
                send_ws_update(bit, "STOP", progress)
                time.sleep(bit_time)

            # Finalize transmission: turn off LED and release GPIO pins
            tx.set_led(False)
            tx.cleanup()

            # Commit completion to DB
            log_entry.binary_data = "".join(full_binary_sequence)
            log_entry.status = "SUCCESS"
            db.commit()

            # Notify clients of completion
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast({
                "event": "tx_complete",
                "data": {
                    "id": log_entry.id,
                    "text": message,
                    "binary_data": log_entry.binary_data
                }
            }), loop)

        except Exception as e:
            logger.error(f"Error in transmitter thread: {e}")
            if tx:
                try:
                    tx.set_led(False)
                    tx.cleanup()
                except Exception:
                    pass

            if log_entry:
                try:
                    log_entry.status = "FAILED"
                    db.commit()
                except Exception:
                    pass

            asyncio.run_coroutine_threadsafe(ws_manager.broadcast({
                "event": "tx_failed",
                "data": {"error": str(e)}
            }), loop)

        finally:
            with self._lock:
                self.is_transmitting = False
            db.close()


# Global transmitter worker instance
tx_worker = TransmitterWorker()
