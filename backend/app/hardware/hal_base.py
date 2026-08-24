from abc import ABC, abstractmethod

class BaseTransmitter(ABC):
    @abstractmethod
    def setup(self, led_pin: int):
        """Initialize the transmitter hardware with the specified pin."""
        pass

    @abstractmethod
    def set_led(self, state: bool):
        """Set the LED state: True for ON, False for OFF."""
        pass

    @abstractmethod
    def cleanup(self):
        """Release hardware resources."""
        pass


class BaseReceiver(ABC):
    @abstractmethod
    def setup(self, spi_port: int, spi_device: int, max_speed_hz: int):
        """Initialize the SPI connection for the receiver."""
        pass

    @abstractmethod
    def read_adc(self, channel: int) -> int:
        """Read the 10-bit raw value (0-1023) from the specified ADC channel."""
        pass

    @abstractmethod
    def cleanup(self):
        """Release hardware resources."""
        pass
