import random
import time
import logging
from .hal_base import BaseTransmitter, BaseReceiver

logger = logging.getLogger(__name__)

class MockBus:
    """Simulates the physical medium (light channel) between LED and Photodiode."""
    def __init__(self):
        self.led_on = False
        self.noise_level = 0.0  # 0.0 to 1.0
        self.ambient_light = 0.0 # 0.0 to 1.0

    def set_led_state(self, state: bool):
        self.led_on = state

    def get_voltage(self) -> float:
        # Physical logic:
        # LED ON -> light hits photodiode -> pulls down voltage -> near 0V
        # LED OFF -> dark -> voltage pulls high -> near 3.3V
        base_voltage = 0.05 if self.led_on else 3.25
        
        # Add random ambient light offset (shifts voltage down slightly)
        base_voltage -= self.ambient_light * 0.5
        
        # Add random noise based on noise_level (amplitude up to 1.65V at max noise)
        if self.noise_level > 0:
            noise = random.uniform(-1.65, 1.65) * self.noise_level
            voltage = base_voltage + noise
        else:
            voltage = base_voltage
            
        # Clamp voltage to standard 0.0V - 3.3V range
        return max(0.0, min(3.3, voltage))


# Global singleton instance of the mock bus to simulate wire-level loopback
mock_bus = MockBus()


class MockTransmitter(BaseTransmitter):
    def __init__(self):
        self.led_pin = None

    def setup(self, led_pin: int):
        self.led_pin = led_pin
        mock_bus.set_led_state(False)
        logger.info(f"[MOCK] Transmitter initialized on pin {led_pin}")

    def set_led(self, state: bool):
        mock_bus.set_led_state(state)

    def cleanup(self):
        mock_bus.set_led_state(False)
        logger.info("[MOCK] Transmitter cleaned up.")
        self.led_pin = None


class MockReceiver(BaseReceiver):
    def __init__(self):
        self.spi_port = None
        self.spi_device = None

    def setup(self, spi_port: int, spi_device: int, max_speed_hz: int):
        self.spi_port = spi_port
        self.spi_device = spi_device
        logger.info(f"[MOCK] Receiver initialized on SPI (port={spi_port}, dev={spi_device})")

    def read_adc(self, channel: int) -> int:
        if self.spi_port is None:
            raise RuntimeError("Mock Receiver has not been set up. Call setup() first.")
        
        # Read the simulated voltage
        voltage = mock_bus.get_voltage()
        
        # Translate to 10-bit ADC value (0 - 1023)
        adc_value = int((voltage / 3.3) * 1023)
        return max(0, min(1023, adc_value))

    def set_noise_level(self, level: float):
        mock_bus.noise_level = level
        logger.info(f"[MOCK] Noise level set to {level:.2f}")

    def cleanup(self):
        logger.info("[MOCK] Receiver cleaned up.")
        self.spi_port = None
