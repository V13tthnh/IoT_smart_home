from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
import json
import os
import sqlite3
import csv
import io
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# ===== DATABASE =====
DB_PATH = os.path.join(os.path.dirname(__file__), 'sensor_history.db')


def get_db():
    """Mở kết nối SQLite (mỗi request dùng kết nối riêng)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Khởi tạo bảng nếu chưa tồn tại."""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   DATETIME DEFAULT (datetime('now','localtime')),
                temperature REAL,
                humidity    REAL,
                lux         INTEGER,
                fire        INTEGER DEFAULT 0,
                gas         INTEGER DEFAULT 0,
                rain        INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
    print("[DB] Database initialized:", DB_PATH)


# ===== IN-MEMORY STATE =====

# Trạng thái hệ thống (cập nhật từ Proteus)
system_status = {
    "door":      "closed",  # closed / open
    "window":    "closed",  # closed / open
    "fan":       False,     # True / False
    "light":     False,     # True / False
    "emergency": False      # True / False
}

# Dữ liệu cảm biến hiện tại
sensor_data = {
    "temperature": 0.0,
    "humidity":    0.0,
    "lux":         0,
    "fire":        False,
    "gas":         False,
    "rain":        False
}

# Text LCD
lcd_text = {"lcd_text": ""}

# Lệnh từ web gửi xuống Proteus
current_command = {"command": "none"}

# Timestamp lần cuối lưu vào DB (throttle 1 phút / lần)
_last_db_save_time = None


# ===== PAGES =====

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/history')
def history():
    return render_template('history.html')


# ===== API: DEVICE STATUS =====

@app.route('/api/status', methods=['GET'])
def get_status():
    """Web lấy trạng thái thiết bị."""
    return jsonify(system_status)


@app.route('/api/status', methods=['POST'])
def set_status():
    """Proteus gửi trạng thái thiết bị lên."""
    try:
        data = request.get_json()
        for key in ('door', 'window', 'fan', 'light', 'emergency'):
            if key in data:
                system_status[key] = data[key]
        print(f"[{_ts()}] Status updated: {system_status}")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ===== API: COMMAND =====

# Optimistic status mapping: apply immediately when command is received
# so the web polling sees the new state right away (no 5s lag)
COMMAND_STATUS_MAP = {
    'fan_on':      {'fan':    True},
    'fan_off':     {'fan':    False},
    'door_open':   {'door':   'open'},
    'door_close':  {'door':   'closed'},
    'window_open': {'window': 'open'},
    'window_close':{'window': 'closed'},
    'light_on':    {'light':  True},
    'light_off':   {'light':  False},
}


@app.route('/api/command', methods=['GET'])
def get_command():
    """Proteus reads command from web."""
    cmd = current_command['command']
    current_command['command'] = 'none'
    return jsonify({"command": cmd})


@app.route('/api/command', methods=['POST'])
def set_command():
    """Web sends command to Proteus. Also optimistically updates system_status."""
    try:
        data = request.get_json()
        command = data.get('command', 'none')
        current_command['command'] = command

        # Optimistic update so polling immediately reflects the intended state
        if command in COMMAND_STATUS_MAP:
            system_status.update(COMMAND_STATUS_MAP[command])

        print(f"[{_ts()}] Command received: {command} | status now: {system_status}")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ===== API: SENSORS =====

@app.route('/api/sensors', methods=['GET'])
def get_sensors():
    """Web lấy dữ liệu cảm biến hiện tại."""
    return jsonify(sensor_data)


@app.route('/api/sensors', methods=['POST'])
def set_sensors():
    """Proteus gửi dữ liệu cảm biến lên web và lưu vào SQLite."""
    try:
        data = request.get_json()

        # Cập nhật in-memory
        if 'temperature' in data:
            sensor_data['temperature'] = float(data['temperature'])
        if 'humidity' in data:
            sensor_data['humidity'] = float(data['humidity'])
        if 'lux' in data:
            sensor_data['lux'] = int(data['lux'])
        if 'fire' in data:
            sensor_data['fire'] = bool(data['fire'])
        if 'gas' in data:
            sensor_data['gas'] = bool(data['gas'])
        if 'rain' in data:
            sensor_data['rain'] = bool(data['rain'])

        print(f"[{_ts()}] Sensors: T={sensor_data['temperature']}°C "
              f"H={sensor_data['humidity']}% L={sensor_data['lux']} lux")

        if sensor_data['fire']:
            print("CẢNH BÁO: Phát hiện lửa!")
        if sensor_data['gas']:
            print("CẢNH BÁO: Phát hiện khí gas!")
        if sensor_data['rain']:
            print("CẢNH BÁO: Phát hiện mưa!")

        # Lưu vào SQLite tối đa 1 lần / phút
        global _last_db_save_time
        now = datetime.now()
        if _last_db_save_time is None or (now - _last_db_save_time).total_seconds() >= 60:
            _save_sensor_to_db(sensor_data)
            _last_db_save_time = now
            print(f"[{_ts()}] Saved to DB")

        return jsonify({"success": True})
    except Exception as e:
        print(f"Error set_sensors: {e}")
        return jsonify({"success": False, "error": str(e)}), 400


def _save_sensor_to_db(sd):
    """Ghi một bản ghi cảm biến vào bảng sensor_readings."""
    try:
        with get_db() as conn:
            conn.execute(
                '''INSERT INTO sensor_readings
                   (temperature, humidity, lux, fire, gas, rain)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (
                    sd['temperature'],
                    sd['humidity'],
                    sd['lux'],
                    1 if sd['fire'] else 0,
                    1 if sd['gas']  else 0,
                    1 if sd['rain'] else 0,
                )
            )
            conn.commit()
    except Exception as e:
        print(f"[DB] Save error: {e}")


# ===== API: LCD =====

@app.route('/api/lcd', methods=['GET'])
def get_lcd():
    return jsonify(lcd_text)


@app.route('/api/lcd', methods=['POST'])
def set_lcd():
    try:
        data = request.get_json()
        lcd_text['lcd_text'] = data.get('lcd_text', '')
        print(f"[{_ts()}] LCD updated")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ===== API: CHARTS =====

def _slot_avg(conn, h_start, h_end):
    """Trung bình cảm biến trong khung giờ h_start–h_end của hôm nay."""
    row = conn.execute(
        '''SELECT AVG(temperature) AS t, AVG(humidity) AS h, AVG(lux) AS l
           FROM sensor_readings
           WHERE timestamp >= datetime('now','localtime','start of day', ?)
             AND timestamp <  datetime('now','localtime','start of day', ?)''',
        (f'+{h_start} hours', f'+{h_end} hours')
    ).fetchone()
    if row and row['t'] is not None:
        return {'temp': round(float(row['t']), 1),
                'humidity': round(float(row['h']), 1),
                'lux': int(row['l'] or 0)}
    return None


def _row_slot(row, label):
    """Chuyển sqlite3.Row thành dict slot cho chart timeline."""
    return {
        'label':    label,
        'temp':     round(float(row['t']), 1) if row and row['t'] is not None else None,
        'humidity': round(float(row['h']), 1) if row and row['h'] is not None else None,
        'lux':      int(row['l'])              if row and row['l'] is not None else None,
    }


@app.route('/api/chart/today', methods=['GET'])
def chart_today():
    """Mini-chart: trung bình sáng (6–10h), trưa (10–14h) và live now."""
    try:
        with get_db() as conn:
            morning = _slot_avg(conn, 6, 10)
            noon    = _slot_avg(conn, 10, 14)
        return jsonify({
            'morning': morning,
            'noon':    noon,
            'now': {
                'temp':     sensor_data['temperature'],
                'humidity': sensor_data['humidity'],
                'lux':      sensor_data['lux'],
            },
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/chart/timeline', methods=['GET'])
def chart_timeline():
    """Chuỗi 7 điểm dữ liệu cho biểu đồ lịch sử theo period."""
    period = request.args.get('period', 'today')
    _now = {'label': 'Now',
            'temp': sensor_data['temperature'],
            'humidity': sensor_data['humidity'],
            'lux': sensor_data['lux']}
    try:
        if period == 'today':
            windows = [(0, 4, '12 AM'), (4, 8, '4 AM'), (8, 12, '8 AM'),
                       (12, 16, '12 PM'), (16, 20, '4 PM'), (20, 24, '8 PM')]
            slots = []
            with get_db() as conn:
                for h0, h1, label in windows:
                    row = conn.execute(
                        '''SELECT AVG(temperature) AS t, AVG(humidity) AS h, AVG(lux) AS l
                           FROM sensor_readings
                           WHERE timestamp >= datetime('now','localtime','start of day', ?)
                             AND timestamp <  datetime('now','localtime','start of day', ?)''',
                        (f'+{h0} hours', f'+{h1} hours')
                    ).fetchone()
                    slots.append(_row_slot(row, label))
            slots.append(_now)

        elif period == 'week':
            slots = []
            with get_db() as conn:
                for offset in range(6, -1, -1):
                    day = datetime.now() - timedelta(days=offset)
                    label = 'Today' if offset == 0 else day.strftime('%a %d')
                    row = conn.execute(
                        '''SELECT AVG(temperature) AS t, AVG(humidity) AS h, AVG(lux) AS l
                           FROM sensor_readings
                           WHERE date(timestamp) = date('now','localtime', ?)''',
                        (f'-{offset} days',)
                    ).fetchone()
                    slots.append(_row_slot(row, label))

        elif period == 'month':
            # 7 điểm đại diện, mỗi điểm cách nhau ~5 ngày
            offsets = [30, 25, 20, 15, 10, 5, 0]
            slots = []
            with get_db() as conn:
                for offset in offsets:
                    if offset == 0:
                        slots.append(_now)
                        continue
                    day = datetime.now() - timedelta(days=offset)
                    label = day.strftime('%d/%m')
                    row = conn.execute(
                        '''SELECT AVG(temperature) AS t, AVG(humidity) AS h, AVG(lux) AS l
                           FROM sensor_readings
                           WHERE date(timestamp) = date('now','localtime', ?)''',
                        (f'-{offset} days',)
                    ).fetchone()
                    slots.append(_row_slot(row, label))
        else:
            return jsonify({'error': 'Invalid period. Use: today, week, month'}), 400

        return jsonify({'period': period, 'slots': slots})
    except Exception as e:
        print(f'[chart_timeline] error: {e}')
        return jsonify({'error': str(e)}), 500


# ===== API: HISTORY (SQLite) =====

PERIOD_INTERVALS = {
    'today': "-1 day",
    'week':  "-7 days",
    'month': "-30 days",
}

PERIOD_LABELS = {
    'today': ("Today Trends",
              "Aggregated data across all environmental sensors (Last 24 hours)",
              "Today"),
    'week':  ("This Week Trends",
              "7-day environmental trends and patterns",
              "This Week"),
    'month': ("This Month Trends",
              "30-day environmental statistics",
              "This Month"),
}


@app.route('/api/history', methods=['GET'])
def get_history():
    """
    Trả về thống kê cao nhất / thấp nhất / trung bình theo khoảng thời gian.
    Query param: ?period=today|week|month  (mặc định: today)
    """
    period = request.args.get('period', 'today')
    if period not in PERIOD_INTERVALS:
        return jsonify({"error": "Invalid period. Use: today, week, month"}), 400

    interval = PERIOD_INTERVALS[period]
    title, subtitle, label = PERIOD_LABELS[period]

    try:
        with get_db() as conn:
            row = conn.execute(
                f'''SELECT
                        MAX(temperature) AS temp_max,
                        MIN(temperature) AS temp_min,
                        AVG(temperature) AS temp_avg,
                        MAX(humidity)    AS hum_max,
                        MIN(humidity)    AS hum_min,
                        AVG(humidity)    AS hum_avg,
                        MAX(lux)         AS lux_max,
                        MIN(lux)         AS lux_min,
                        AVG(lux)         AS lux_avg,
                        COUNT(*)         AS total_records
                    FROM sensor_readings
                    WHERE timestamp >= datetime('now', 'localtime', ?)''',
                (interval,)
            ).fetchone()

        if row is None or row['total_records'] == 0:
            # Không có dữ liệu – trả về rỗng
            return jsonify({
                "period":   period,
                "title":    title,
                "subtitle": subtitle,
                "label":    label,
                "total_records": 0,
                "highest": {"temp": None, "humidity": None, "light": None},
                "lowest":  {"temp": None, "humidity": None, "light": None},
                "average": {"temp": None, "humidity": None, "light": None},
            })

        def r1(v):
            return round(v, 1) if v is not None else None

        return jsonify({
            "period":   period,
            "title":    title,
            "subtitle": subtitle,
            "label":    label,
            "total_records": row['total_records'],
            "highest": {
                "temp":     r1(row['temp_max']),
                "humidity": r1(row['hum_max']),
                "light":    int(row['lux_max']) if row['lux_max'] is not None else None,
            },
            "lowest": {
                "temp":     r1(row['temp_min']),
                "humidity": r1(row['hum_min']),
                "light":    int(row['lux_min']) if row['lux_min'] is not None else None,
            },
            "average": {
                "temp":     r1(row['temp_avg']),
                "humidity": r1(row['hum_avg']),
                "light":    int(row['lux_avg']) if row['lux_avg'] is not None else None,
            },
        })

    except Exception as e:
        print(f"[DB] History query error: {e}")
        return jsonify({"error": str(e)}), 500


# ===== API: EXPORT CSV =====

@app.route('/api/history/export', methods=['GET'])
def export_history_csv():
    """
    Xuất dữ liệu lịch sử ra file CSV.
    Query param: ?period=today|week|month  (mặc định: today)
    """
    period = request.args.get('period', 'today')
    interval = PERIOD_INTERVALS.get(period, "-1 day")

    try:
        with get_db() as conn:
            rows = conn.execute(
                '''SELECT timestamp, temperature, humidity, lux, fire, gas, rain
                   FROM sensor_readings
                   WHERE timestamp >= datetime('now', 'localtime', ?)
                   ORDER BY timestamp ASC''',
                (interval,)
            ).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Timestamp', 'Temperature (°C)', 'Humidity (%)',
                         'Lux', 'Fire', 'Gas', 'Rain'])
        for r in rows:
            writer.writerow([
                r['timestamp'],
                r['temperature'],
                r['humidity'],
                r['lux'],
                'Yes' if r['fire'] else 'No',
                'Yes' if r['gas']  else 'No',
                'Yes' if r['rain'] else 'No',
            ])

        filename = f"sensor_history_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== HEALTH CHECK =====

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status":    "running",
        "timestamp": datetime.now().isoformat()
    })


# ===== HELPERS =====

def _ts():
    return datetime.now().strftime('%H:%M:%S')


# ===== ENTRY POINT =====

if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("  Smart Environment System - API Server")
    print("=" * 60)
    print("  Web Interface : http://localhost:5000/")
    print("  History Page  : http://localhost:5000/history")
    print("  API Health    : http://localhost:5000/api/health")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
