# lcd.py - LCD 16x2 I2C controller + text state tracker
import smbus
import time

# Module-level variables to track what is currently displayed on the LCD
_lcd_line1 = ""
_lcd_line2 = ""


# ── Public helpers (used by main.py and api.py) ───────────────────────────────

def get_lcd_text():
    # Returns current LCD content as a single string: "line1 | line2"
    return _lcd_line1 + " | " + _lcd_line2


def set_lcd_text(line1="", line2=""):
    # Call this every time pio.LCD1 is updated in main.py
    # so that api.py can read the latest LCD state via get_lcd_text()
    global _lcd_line1, _lcd_line2
    _lcd_line1 = line1[:16]
    _lcd_line2 = line2[:16]


# ── LCD hardware class (I2C, for real RPi hardware) ───────────────────────────

class LCD:
    def __init__(self, address=0x27, bus_id=1):
        self.address = address
        self.bus = smbus.SMBus(bus_id)

        self.LCD_WIDTH = 16
        self.LCD_CHR = 1
        self.LCD_CMD = 0

        self.LCD_LINE_1 = 0x80
        self.LCD_LINE_2 = 0xC0

        self.LCD_BACKLIGHT = 0x08
        self.ENABLE = 0b00000100

        self.init_lcd()

    def init_lcd(self):
        self.lcd_byte(0x33, self.LCD_CMD)
        self.lcd_byte(0x32, self.LCD_CMD)
        self.lcd_byte(0x06, self.LCD_CMD)
        self.lcd_byte(0x0C, self.LCD_CMD)
        self.lcd_byte(0x28, self.LCD_CMD)
        self.lcd_byte(0x01, self.LCD_CMD)
        time.sleep(0.005)

    def lcd_byte(self, bits, mode):
        high_bits = mode | (bits & 0xF0) | self.LCD_BACKLIGHT
        low_bits = mode | ((bits << 4) & 0xF0) | self.LCD_BACKLIGHT

        self.bus.write_byte(self.address, high_bits)
        self.lcd_toggle_enable(high_bits)

        self.bus.write_byte(self.address, low_bits)
        self.lcd_toggle_enable(low_bits)

    def lcd_toggle_enable(self, bits):
        time.sleep(0.0005)
        self.bus.write_byte(self.address, bits | self.ENABLE)
        time.sleep(0.0005)
        self.bus.write_byte(self.address, bits & ~self.ENABLE)
        time.sleep(0.0005)

    def clear(self):
        global _lcd_line1, _lcd_line2
        _lcd_line1 = ""
        _lcd_line2 = ""
        self.lcd_byte(0x01, self.LCD_CMD)
        time.sleep(0.002)

    def write_line(self, message, line):
        global _lcd_line1, _lcd_line2
        # Track displayed text
        if line == self.LCD_LINE_1:
            _lcd_line1 = message.strip()[:self.LCD_WIDTH]
        elif line == self.LCD_LINE_2:
            _lcd_line2 = message.strip()[:self.LCD_WIDTH]

        message = message.ljust(self.LCD_WIDTH, " ")
        self.lcd_byte(line, self.LCD_CMD)

        for char in message:
            self.lcd_byte(ord(char), self.LCD_CHR)
