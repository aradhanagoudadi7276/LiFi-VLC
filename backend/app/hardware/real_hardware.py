import logging
from .hal_base import BaseTransmitter, BaseReceiver

logger = logging.getLogger(__name__)

# Try to import RPi.GPIO
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    GPIO = None

# Try to import spidev
try:
    import spidev
    SPIDEV_AVAILABLE = True
except ImportError:
    SPIDEV_AVAILABLE = False
    spidev = None


class GPIOTransmitter(BaseTransmitter):
    def __init__(self):
        if not GPIO_AVAILABLE:
            raise RuntimeError("RPi.GPIO library is not installed or available on this system.")
        self.led_pin = None

    def setup(self, led_pin: int):
        self.led_pin = led_pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.led_pin, GPIO.OUT)
        GPIO.output(self.led_pin, GPIO.LOW)
        logger.info(f"GPIO Transmitter configured on pin BCM {self.led_pin}")

    def set_led(self, state: bool):
        if self.led_pin is None:
            raise RuntimeError("Transmitter has not been set up. Call setup() first.")
        GPIO.output(self.led_pin, GPIO.HIGH if state else GPIO.LOW)

    def cleanup(self):
        if self.led_pin is not None:
            try:
                GPIO.output(self.led_pin, GPIO.LOW)
                GPIO.cleanup(self.led_pin)
                logger.info(f"GPIO pin BCM {self.led_pin} cleaned up.")
            except Exception as e:
                logger.error(f"Error cleaning up GPIO: {e}")
            self.led_pin = None


class SPIReceiver(BaseReceiver):
    def __init__(self):
        if not SPIDEV_AVAILABLE:
            raise RuntimeError("spidev library is not installed or available on this system.")
        self.spi = None

    def setup(self, spi_port: int, spi_device: int, max_speed_hz: int):
        self.spi = spidev.SpiDev()
        self.spi.open(spi_port, spi_device)
        self.spi.max_speed_hz = max_speed_hz
        logger.info(f"SPI Receiver opened on bus {spi_port}, chip select {spi_device} at speed {max_speed_hz}Hz")

    def read_adc(self, channel: int) -> int:
        if self.spi is None:
            raise RuntimeError("SPI receiver is not set up. Call setup() first.")
        if channel < 0 or channel > 7:
            return -1

        # MCP3008 standard 3-byte protocol:
        # byte 0: Start bit (1)
        # byte 1: Single-ended configuration (bit 7 set) + Channel select in bits 6, 5, 4
        # byte 2: Don't care byte
        adc = self.spi.xfer2([
            1,
            (8 + channel) << 4,
            0
        ])
        
        # Extract 10-bit raw ADC value from last 2 bytes
        value = ((adc[1] & 3) << 8) | adc[2]
        return value

    def cleanup(self):
        if self.spi is not None:
            try:
                self.spi.close()
                logger.info("SPI connection closed.")
            except Exception as e:
                logger.error(f"Error closing SPI connection: {e}")
            self.spi = None
