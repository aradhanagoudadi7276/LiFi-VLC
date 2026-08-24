import time
import asyncio
import sys
import os

# Adjust path to import app package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.hardware.manager import get_transmitter, get_receiver
from app.hardware.mock_hardware import mock_bus


def run_test():
    print("--------------------------------------------------")
    print("Starting LiFi Mock Hardware Loopback Verification")
    print("--------------------------------------------------")
    
    tx = get_transmitter(use_mock=True)
    rx = get_receiver(use_mock=True)
    
    # Setup simulated hardware
    tx.setup(led_pin=18)
    rx.setup(spi_port=0, spi_device=0, max_speed_hz=1350000)
    
    # Default clean state
    mock_bus.noise_level = 0.0
    
    # Test LED ON state
    print("Testing LED ON...")
    tx.set_led(True)
    time.sleep(0.05) # allow time settling
    adc_on = rx.read_adc(channel=0)
    volts_on = (adc_on / 1023.0) * 3.3
    print(f"  LED ON -> ADC: {adc_on:4d} | Voltage: {volts_on:.3f}V (Expected: ~0.05V, Low)")
    
    # Test LED OFF state
    print("Testing LED OFF...")
    tx.set_led(False)
    time.sleep(0.05)
    adc_off = rx.read_adc(channel=0)
    volts_off = (adc_off / 1023.0) * 3.3
    print(f"  LED OFF -> ADC: {adc_off:4d} | Voltage: {volts_off:.3f}V (Expected: ~3.25V, High)")
    
    # Test Threshold Logic
    threshold = 1.65
    bit_on = "1" if volts_on < threshold else "0"
    bit_off = "1" if volts_off < threshold else "0"
    
    print("Verifying Logic Decoding:")
    print(f"  LED ON Decodes as: '{bit_on}' (Expected: '1')")
    print(f"  LED OFF Decodes as: '{bit_off}' (Expected: '0')")
    
    # Test with noise
    mock_bus.noise_level = 0.2
    print("Testing with 20% noise introduced...")
    noisy_readings = []
    for _ in range(5):
        tx.set_led(True)
        time.sleep(0.02)
        v = (rx.read_adc(0) / 1023.0) * 3.3
        noisy_readings.append(v)
    print(f"  Noisy LED ON Voltages: {[round(x, 3) for x in noisy_readings]}")
    
    # Cleanup
    tx.cleanup()
    rx.cleanup()
    
    # Validation checks
    assert bit_on == "1", "Error: LED ON did not decode to binary '1'"
    assert bit_off == "0", "Error: LED OFF did not decode to binary '0'"
    assert volts_on < 0.2, f"Error: LED ON voltage was too high: {volts_on}V"
    assert volts_off > 3.0, f"Error: LED OFF voltage was too low: {volts_off}V"
    
    print("\nSUCCESS: Hardware Abstraction Layer Loopback tests passed with 100% logic accuracy!")
    print("--------------------------------------------------")


if __name__ == "__main__":
    run_test()
