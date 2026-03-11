import time
import pio
import RPi.GPIO as GPIO

class FanController:

    def __init__(self):
        GPIO.setup(19, GPIO.OUT) 
        self.fan_state = False
        self.last_button_state = False
        self.last_debounce_time = 0
        self.debounce_time = 0.15

        self.turn_off()

    # Fan control
    def turn_on(self):
        self.fan_state = True
        GPIO.output(19, True)
        print("FAN ON")

    def turn_off(self):
        self.fan_state = False
        GPIO.output(19, False)
        print("FAN OFF")

    def toggle(self):
        if self.fan_state:
            self.turn_off()
        else:
            self.turn_on()


    # Button handling
    def handle_button(self):

        now = time.time()
        current_state = pio.BTN4()

        # Detect rising edge
        if current_state and not self.last_button_state:
            if (now - self.last_debounce_time) > self.debounce_time:
                self.toggle()
                self.last_debounce_time = now

        self.last_button_state = current_state
	

    def emergency_open(self):
        self.fan_state = True
        GPIO.output(19, True)
        print("FAN ON")