import time
import pio
import Generic

class LightController:

    def __init__(self):
        self.light = pio.LED2
        self.led_state = False
        self.button_pressed = False
        self.last_time = 0
        self.debounce_time = 0.15

        self.light.off()

    def turn_on(self):
        self.led_state = True
        self.light.on()
        print("LED ON")

    def turn_off(self):
        self.led_state = False
        self.light.off()
        print("LED OFF")

    def toggle(self):
        if self.led_state:
            self.turn_off()
        else:
            self.turn_on()

    def handle_button(self):

        now = time.time()
        btn = pio.BTN3()

        if btn and not self.button_pressed:
            self.button_pressed = True

        if not btn and self.button_pressed:
            if now - self.last_time > self.debounce_time:
                self.toggle()
                self.last_time = now

            self.button_pressed = False