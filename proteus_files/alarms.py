import time
import pio

class AlarmController:

    def __init__(self, blink_interval=0.5):

        self.blink_interval = blink_interval

        self.last_blink_time = 0
        self.alarm_state = False
        self.alarm_active = False

        self.led = pio.ALARM_LED
        self.led.off()
	
        self.buz = pio.ALARM_BUZ
        self.buz.off()


    def activate(self):
        self.alarm_active = True
        self.led.on()
        self.buz.on()


    def deactivate(self):
        self.alarm_active = False
        self.led.off()
        self.buz.off()

    def update(self):
        if not self.alarm_active:
            return
        now = time.time()
        if now - self.last_blink_time >= self.blink_interval:
            self.last_blink_time = now
            self.alarm_state = not self.alarm_state
            
            # LED 
            if self.alarm_state:
                self.led.on()
		
            else:
                self.led.off()
            
            # Buzzer 
            self.buz.on()
            