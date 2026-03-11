#!/usr/bin/env python3

from goto import *
import RPi.GPIO as GPIO
import time
import var
import pio
import resource
from read_sensor import read_temperature, read_humidity, read_lux, flame_detected, gas_detected, rain_detected
from motor_control import DualMotorController
from fan_toggle import FanController
from light_toggle import LightController
from alarms import AlarmController
from api import read_command, write_status, send_sensor_data, send_lcd_text
from lcd import set_lcd_text

# Peripheral Configuration Code (do not edit)
#---CONFIG_BEGIN---
import cpu
import FileStore
import VFP
import Ports
import Generic
import Displays

def peripheral_setup () :
# Peripheral Constructors
 pio.cpu=cpu.CPU ()
 pio.storage=FileStore.FileStore ()
 pio.server=VFP.VfpServer ()
 pio.i2c=Ports.I2c ()
 pio.CRS1=Generic.RelayBoards (pio.GPIO4, pio.GPIO17, pio.GPIO18, pio.GPIO27)
 pio.BTN1=Generic.Button (pio.GPIO5)
 pio.BTN2=Generic.Button (pio.GPIO12)
 pio.BTN3=Generic.Button (pio.GPIO6)
 pio.BTN4=Generic.Button (pio.GPIO13)
 pio.LCD1=Displays.I2CLDC ()
 pio.U3=Generic.ADS1015 ()
 pio.LED2=Generic.LED (pio.GPIO20)
 pio.ALARM_LED=Generic.LED (pio.GPIO21)
 pio.ALARM_BUZ=Generic.Buzzer (pio.GPIO16)
 pio.storage.begin ()
 pio.server.begin (0)
# Install interrupt handlers

def peripheral_loop () :
 pio.server.poll ()

#---CONFIG_END---

GPIO.setmode(GPIO.BCM)   
GPIO.setwarnings(False)

TEMP_THRESHOLD = 35
HUM_THRESHOLD  = 85
MAX_LUX_THRESHOLD  = 1000
MIN_LUX_THRESHOLD  = 100
BUZZER_PIN = 16

# Xu ly lenh tu api
def handle_api_command(command, motor_ctrl, fan_ctrl, light_ctrl):

    if command == 'none':
        return

    print(f"[API] Received command: {command}")

    commands = {
        "fan_on": fan_ctrl.turn_on,
        "fan_off": fan_ctrl.turn_off,
        "door_open": motor_ctrl.start_motor1_forward,
        "door_close": motor_ctrl.start_motor1_backward,
        "window_open": motor_ctrl.open_window,
        "window_close": motor_ctrl.close_window,
        "light_on": light_ctrl.turn_on,
        "light_off": light_ctrl.turn_off,
    }

    action = commands.get(command)

    if action:
        action()

def handle_environment(
    temperature, humidity, lux,
    fire, gas, rain,
    motor_ctrl, fan_ctrl, light_ctrl, alarm_ctrl
):

    if fire:
        show_lcd("FIRE DETECTED!", "EMERGENCY!")
        alarm_ctrl.activate()
        motor_ctrl.emergency_open()
        return

    if gas:
        show_lcd("GAS DETECTED!", "EMERGENCY!")
        alarm_ctrl.activate()
        motor_ctrl.emergency_open()
        fan_ctrl.turn_on()
        return

    if rain:
        motor_ctrl.close_window()
        show_lcd("RAIN DETECTED!", "CLOSING WINDOWS")
        return

    if temperature > TEMP_THRESHOLD or humidity > HUM_THRESHOLD or lux >= MAX_LUX_THRESHOLD:
        light_ctrl.turn_off()
        show_lcd("ENV WARNING!", f"T:{temperature:.1f}C H:{humidity:.0f}%")
        return

    if lux < MIN_LUX_THRESHOLD:
        light_ctrl.turn_on()
        show_lcd("LUX WARNING!", f"LUX:{lux:.0f} lux")
        return

    # normal
    light_ctrl.turn_off()
    alarm_ctrl.deactivate()
    show_lcd(
        f"T:{temperature:.1f}C H:{humidity:.1f}%",
        f"L:{lux:.0f} lux"
    )

def show_lcd(line1, line2):
    pio.LCD1.clear()
    pio.LCD1.print(line1)
    pio.LCD1.println("")
    pio.LCD1.print(line2)

    set_lcd_text(line1, line2)

def main():

  peripheral_setup()

  motor_ctrl = DualMotorController()
  fan_ctrl = FanController()
  light_ctrl = LightController()
  alarm_ctrl = AlarmController(BUZZER_PIN)

  while True:

    peripheral_loop()

    command = read_command()
    handle_api_command(command, motor_ctrl, fan_ctrl, light_ctrl)

    temperature = read_temperature()
    humidity = read_humidity()
    lux = read_lux()

    fire = flame_detected()
    gas = gas_detected()
    rain = rain_detected()

    motor_ctrl.handle_buttons()
    fan_ctrl.handle_button()
    light_ctrl.handle_button()

    handle_environment(
        temperature, humidity, lux,
        fire, gas, rain,
        motor_ctrl, fan_ctrl, light_ctrl, alarm_ctrl
    )
    
    motor_ctrl.check_auto_stop()

    # Dong bo trang thai thiet bi (ke ca khi nhan button vat ly) ve web server
    write_status({
        "door":      motor_ctrl.door_state,
        "window":    motor_ctrl.window_state,
        "fan":       fan_ctrl.fan_state,
        "light":     light_ctrl.led_state,
        "emergency": alarm_ctrl.alarm_active,
    })

    send_sensor_data(temperature, humidity, lux, fire, gas, rain)
    send_lcd_text()

    alarm_ctrl.update()

    time.sleep(0.01)

# Command line execution
if __name__ == '__main__':
  main()