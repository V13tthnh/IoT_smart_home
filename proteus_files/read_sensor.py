import pio
import RPi.GPIO as GPIO
from config import FLAME_SENSOR, GAS_SENSOR, RAIN_SENSOR, SOUND_SENSOR

GPIO.setup(FLAME_SENSOR, GPIO.IN)
GPIO.setup(GAS_SENSOR, GPIO.IN)
GPIO.setup(RAIN_SENSOR, GPIO.IN)

def flame_detected():
    return GPIO.input(FLAME_SENSOR) == GPIO.HIGH

def gas_detected():
    return GPIO.input(GAS_SENSOR) == GPIO.HIGH

def rain_detected():
    return GPIO.input(RAIN_SENSOR) == GPIO.HIGH

def sound_detected():
   return GPIO.input(SOUND_SENSOR) == GPIO.HIGH


def read_temperature():
    high = [0]
    low = [0]

    pio.i2c.receive(0x40, 227, high)
    pio.i2c.receive(0x40, 227, low)

    raw = high[0] * 256 + low[0]

    temperature = (175.72 * raw) / 65536 - 46.85

    return temperature


def read_humidity():
    high = [0]
    low = [0]

    pio.i2c.receive(0x40, 229, high)
    pio.i2c.receive(0x40, 229, low)

    raw = high[0] * 256 + low[0]

    humidity = (125 * raw) / 65536 - 6

    return humidity


def read_lux():
    pio.U3.setAddress(0x48)

    # Doc gia tri analog kenh 0
    volt_val = pio.U3.readAnalogue(0)

    # Chuyen doi sang lux
    lux = (volt_val * 1000) / 2.058

    return lux
