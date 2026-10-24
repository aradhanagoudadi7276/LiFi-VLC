import RPi.GPIO as GPIO
import time

LED_PIN = 18

BIT_TIME = 0.2

MESSAGE = "Hellow World"

GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)


def led_on():
    GPIO.output(LED_PIN, GPIO.HIGH)


def led_off():
    GPIO.output(LED_PIN, GPIO.LOW)


def send_byte(char):

    original_bits = format(ord(char), "08b")
    bits = "10101010" + original_bits

    # print(f"Sending: '{char}'  Binary: {bits}")

    # -------------------------
    # START
    # -------------------------
    # led_off()
    # time.sleep(0.5)

    # -------------------------
    # DATA
    # -------------------------
    for bit in bits:

        if bit == "1":
            led_on()
        else:
            led_off()

        time.sleep(BIT_TIME)

    # -------------------------
    # STOP
    # -------------------------
    # led_on()
    # time.sleep(0.5)


try:

    print("VLC Transmitter Started")
    print(f"Message: {MESSAGE}")
    print("Press CTRL+C to stop\n")

    # led_on()

    # time.sleep(2)

    for char in MESSAGE:
        send_byte(char)
    send_byte(chr(int("10101010", 2)))

except KeyboardInterrupt:

    print("\nTransmitter stopped.")

finally:

    led_off()
    GPIO.cleanup()