# api.py - HTTP client: read commands from server, send status and sensor data
import json
import time
import urllib.request
import urllib.error
from config import SERVER_URL, API_INTERVAL
from lcd import get_lcd_text

TIMEOUT = 2

# Timestamp of the last send cycle (shared by write_status and send_sensor_data)
_last_send_time = 0


def _is_send_due():
    # Returns True when API_INTERVAL seconds have elapsed since the last send
    return (time.time() - _last_send_time) >= API_INTERVAL


def _mark_sent():
    # Update the timestamp after a successful send cycle
    global _last_send_time
    _last_send_time = time.time()


# ── Read command from server (called every loop iteration) ────────────────────

def read_command():
    try:
        with urllib.request.urlopen(
            f"{SERVER_URL}/api/command",
            timeout=TIMEOUT
        ) as res:
            data = json.loads(res.read().decode())
            return data.get("command", "none")

    except urllib.error.URLError:
        return "none"
    except Exception:
        return "none"


# ── Send device status (rate-limited by API_INTERVAL) ────────────────────────

def write_status(system_state):
    if not _is_send_due():
        return

    try:
        payload = json.dumps(system_state).encode()

        req = urllib.request.Request(
            f"{SERVER_URL}/api/status",
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        urllib.request.urlopen(req, timeout=TIMEOUT)
        print(f"[API] Status sent: {system_state}")

    except Exception as e:
        print(f"[API] write_status error: {e}")


# ── Send LCD text (rate-limited by API_INTERVAL) ──────────────────────────────

def send_lcd_text():
    if not _is_send_due():
        return

    try:
        payload = json.dumps({
            "lcd_text": get_lcd_text()
        }).encode()

        req = urllib.request.Request(
            f"{SERVER_URL}/api/lcd",
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        urllib.request.urlopen(req, timeout=TIMEOUT)

    except Exception as e:
        print(f"[API] send_lcd_text error: {e}")


# ── Send sensor data (rate-limited; updates timer after successful send) ───────

def send_sensor_data(temp, hum, lux, fire, gas, rain):
    # This is called last in the send cycle so it owns the timer update
    if not _is_send_due():
        return

    try:
        payload = json.dumps({
            "temperature": temp,
            "humidity":    hum,
            "lux":         lux,
            "fire":        fire,
            "gas":         gas,
            "rain":        rain
        }).encode()

        req = urllib.request.Request(
            f"{SERVER_URL}/api/sensors",
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        urllib.request.urlopen(req, timeout=TIMEOUT)
        print(f"[API] Sensors sent: T={temp:.1f} H={hum:.1f} L={lux}")

        _mark_sent()

    except Exception as e:
        print(f"[API] send_sensor_data error: {e}")
