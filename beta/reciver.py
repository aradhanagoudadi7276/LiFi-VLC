import spidev
import time

ADC_CHANNEL = 0
BIT_TIME = 0.2
# MCP3008 SPI
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000


def binary_to_char(binary):
    value = int(binary, 2)
    
    if 32 <= value <= 126:
        char = chr(value)
    else:
        char = "?"
    # return binary, char
    return char

def read_adc(channel):

    if channel < 0 or channel > 7:
        return -1

    adc = spi.xfer2([
        1,
        (8 + channel) << 4,
        0
    ])

    value = ((adc[1] & 3) << 8) | adc[2]

    return value


print("Photodiode Receiver")
print("Reading MCP3008 CH0...")
print("Press CTRL+C to stop\n")

try:
    temp = ""
    recv = 0
    word = ""
    while True:

        adc_value = read_adc(ADC_CHANNEL)

        voltage = (adc_value / 1023.0) * 3.3

        # print(
        #     f"ADC: {adc_value:4d} | "
        #     f"Voltage: {voltage:.3f} V"
        # )
        if adc_value == 0:
            temp += '1'
        else:
            temp += '0'
        # print(temp)
        if '10101010' in temp and recv == 0:
            temp = ''
            recv = 1
        elif recv == 1 and len(temp) == 8:
            if temp == '10101010':
                print(word)
                word = ''
            else:
                word += binary_to_char(temp)
            recv = 0
            temp = ''
        elif len(temp) == 32:
            temp = ''
        time.sleep(BIT_TIME)

except KeyboardInterrupt:

    print("\nStopping...")

finally:

    spi.close()