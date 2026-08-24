import logging
from .hal_base import BaseTransmitter, BaseReceiver
from .real_hardware import GPIOTransmitter, SPIReceiver, GPIO_AVAILABLE, SPIDEV_AVAILABLE
from .mock_hardware import MockTransmitter, MockReceiver

logger = logging.getLogger(__name__)

# Singletons to reuse active hardware instances
_transmitter_instance = None
_receiver_instance = None
_active_mock_tx = None
_active_mock_rx = None


def get_transmitter(use_mock: bool = True) -> BaseTransmitter:
    global _transmitter_instance, _active_mock_tx
    
    # Force mock mode if driver is unavailable
    if not GPIO_AVAILABLE:
        if not use_mock:
            logger.warning("RPi.GPIO library not available. Forcing Transmitter to Mock mode.")
        use_mock = True

    # Recreate if mode changed or first time
    if _transmitter_instance is None or _active_mock_tx != use_mock:
        if _transmitter_instance is not None:
            try:
                _transmitter_instance.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up old transmitter: {e}")
        
        if use_mock:
            _transmitter_instance = MockTransmitter()
        else:
            _transmitter_instance = GPIOTransmitter()
            
        _active_mock_tx = use_mock
        logger.info(f"Transmitter mode set to: {'Mock' if use_mock else 'GPIO'}")
        
    return _transmitter_instance


def get_receiver(use_mock: bool = True) -> BaseReceiver:
    global _receiver_instance, _active_mock_rx
    
    # Force mock mode if driver is unavailable
    if not SPIDEV_AVAILABLE:
        if not use_mock:
            logger.warning("spidev library not available. Forcing Receiver to Mock mode.")
        use_mock = True

    # Recreate if mode changed or first time
    if _receiver_instance is None or _active_mock_rx != use_mock:
        if _receiver_instance is not None:
            try:
                _receiver_instance.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up old receiver: {e}")
        
        if use_mock:
            _receiver_instance = MockReceiver()
        else:
            _receiver_instance = SPIReceiver()
            
        _active_mock_rx = use_mock
        logger.info(f"Receiver mode set to: {'Mock' if use_mock else 'SPI'}")
        
    return _receiver_instance
