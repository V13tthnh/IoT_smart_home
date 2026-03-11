import time
import pio


class DualMotorController:

    def __init__(self):

        self.m1_forward = 0
        self.m1_backward = 1

        self.m2_forward = 2
        self.m2_backward = 3

        self.m1_running = False
        self.m2_running = False

        self.door_state = "closed"
        self.window_state = "closed"

        self.m1_direction = None
        self.m2_direction = None

        self.m1_start_time = 0
        self.m2_start_time = 0

        self.rotation_time = 1.5

        self.btn1_last = False
        self.btn2_last = False

        self.btn1_last_time = 0
        self.btn2_last_time = 0

        self.debounce_time = 0.15

        self.stop_all_relays()


    def stop_all_relays(self):

        for i in range(4):
            pio.CRS1.relayOff(i)


    # =====================
    # DOOR MOTOR
    # =====================

    def start_motor1_forward(self):

        if self.m1_running or self.door_state == "open":
            return

        self.stop_all_relays()
        time.sleep(0.05)

        pio.CRS1.relayOn(self.m1_forward)

        self.m1_running = True
        self.m1_direction = "open"
        self.m1_start_time = time.time()

        print("DOOR OPENING")


    def start_motor1_backward(self):

        if self.m1_running or self.door_state == "closed":
            return

        self.stop_all_relays()
        time.sleep(0.05)

        pio.CRS1.relayOn(self.m1_backward)

        self.m1_running = True
        self.m1_direction = "close"
        self.m1_start_time = time.time()

        print("DOOR CLOSING")


    def stop_motor1(self):

        pio.CRS1.relayOff(self.m1_forward)
        pio.CRS1.relayOff(self.m1_backward)

        self.m1_running = False

        if self.m1_direction == "open":
            self.door_state = "open"

        elif self.m1_direction == "close":
            self.door_state = "closed"

        print("DOOR STOP")


    # =====================
    # WINDOW MOTOR
    # =====================

    def start_motor2_forward(self):

        if self.m2_running or self.window_state == "open":
            return

        self.stop_all_relays()
        time.sleep(0.05)

        pio.CRS1.relayOn(self.m2_forward)

        self.m2_running = True
        self.m2_direction = "open"
        self.m2_start_time = time.time()

        print("WINDOW OPENING")


    def start_motor2_backward(self):

        if self.m2_running or self.window_state == "closed":
            return

        self.stop_all_relays()
        time.sleep(0.05)

        pio.CRS1.relayOn(self.m2_backward)

        self.m2_running = True
        self.m2_direction = "close"
        self.m2_start_time = time.time()

        print("WINDOW CLOSING")


    def stop_motor2(self):

        pio.CRS1.relayOff(self.m2_forward)
        pio.CRS1.relayOff(self.m2_backward)

        self.m2_running = False

        if self.m2_direction == "open":
            self.window_state = "open"

        elif self.m2_direction == "close":
            self.window_state = "closed"

        print("WINDOW STOP")


    # =====================
    # AUTO STOP
    # =====================

    def check_auto_stop(self):

        now = time.time()

        if self.m1_running and now - self.m1_start_time >= self.rotation_time:
            self.stop_motor1()

        if self.m2_running and now - self.m2_start_time >= self.rotation_time:
            self.stop_motor2()


    # =====================
    # BUTTON
    # =====================

    def handle_buttons(self):

        now = time.time()

        btn1 = pio.BTN1()

        if btn1 and not self.btn1_last:
            if now - self.btn1_last_time > self.debounce_time:

                if self.door_state == "closed":
                    self.start_motor1_forward()
                else:
                    self.start_motor1_backward()

                self.btn1_last_time = now

        self.btn1_last = btn1


        btn2 = pio.BTN2()

        if btn2 and not self.btn2_last:
            if now - self.btn2_last_time > self.debounce_time:

                if self.window_state == "closed":
                    self.start_motor2_forward()
                else:
                    self.start_motor2_backward()

                self.btn2_last_time = now

        self.btn2_last = btn2

        self.check_auto_stop()


    # =====================
    # EMERGENCY
    # =====================

    def emergency_open(self):

        self.start_motor1_forward()
        self.start_motor2_forward()


    def emergency_close(self):

        self.start_motor1_backward()
        self.start_motor2_backward()


    def open_window(self):
        self.start_motor2_forward()


    def close_window(self):
        self.start_motor2_backward()