# Smart Home IoT Dashboard — Tài liệu kỹ thuật

## 1. Tổng quan hệ thống

Dashboard IoT điều khiển và giám sát nhà thông minh gồm hai phần:

- **Proteus (client)** — Mô phỏng phần cứng (Raspberry Pi), đọc cảm biến, điều khiển thiết bị, giao tiếp với server qua HTTP.
- **Flask Server (server)** — Lưu trạng thái, phục vụ giao diện web, lưu lịch sử vào SQLite, cung cấp API.

```
┌─────────────────────┐        HTTP REST API        ┌─────────────────────┐
│   Proteus / RPi     │ ◄────────────────────────►  │  Flask Server       │
│  (main.py)          │                             │  (app.py)           │
│  - Đọc cảm biến     │  POST /api/sensors ──►      │  - In-memory state  │
│  - Điều khiển relay │  POST /api/status  ──►      │  - SQLite DB        │
│  - Nhấn nút vật lý  │  GET  /api/command ──►      │  - Serve HTML/JS    │
└─────────────────────┘                             └─────────────────────┘
                                                            ▲
                                                            │  HTTP polling
                                                    ┌───────┴─────────┐
                                                    │  Trình duyệt    │
                                                    │  (index.html /  │
                                                    │   history.html) │
                                                    └─────────────────┘
```

---

## 2. Luồng xử lý dữ liệu chi tiết

### 2.1 Gửi lệnh từ Web → Proteus

```
Người dùng nhấn nút trên web
  │
  ▼
index.js: sendCommand("fan_on")
  │  POST /api/command  { "command": "fan_on" }
  ▼
app.py: set_command()
  ├─ Lưu vào current_command["command"] = "fan_on"
  └─ Optimistic update: system_status["fan"] = True
  │
  ▼ (Proteus polling ~ mỗi 10ms)
main.py: read_command() → GET /api/command
  └─ Nhận "fan_on" → handle_api_command() → fan_ctrl.turn_on()
  └─ Server trả về "none" cho các lần gọi tiếp theo (đã clear)
```

### 2.2 Nhấn nút vật lý trong Proteus → Cập nhật Web

```
Người dùng nhấn BTN4 (nút quạt) trong Proteus
  │
  ▼
main.py: fan_ctrl.handle_button() → fan_ctrl.toggle()
  │  fan_ctrl.fan_state = True/False
  │
  ▼
main.py: write_status({ fan: True/False, door: ..., ... })
  │  POST /api/status  (rate-limited: API_INTERVAL = 5s)
  ▼
app.py: set_status() → cập nhật system_status{}
  │
  ▼ (Web polling mỗi 2s)
index.js: getSystemStatus() → GET /api/status
  └─ updateDeviceButtons(status) → applyButtonState()
  └─ Nút Fan trên web hiển thị pressed/unpressed
```

### 2.3 Gửi dữ liệu cảm biến từ Proteus → Web + DB

```
Proteus: send_sensor_data(temp, hum, lux, fire, gas, rain)
  │  POST /api/sensors  (rate-limited: API_INTERVAL = 5s)
  ▼
app.py: set_sensors()
  ├─ Cập nhật sensor_data{} in-memory (luôn luôn)
  └─ Lưu vào SQLite: tối đa 1 lần / 60 giây (_last_db_save_time)
  │
  ├──► Web polling (3s): GET /api/sensors → updateSensorDisplay()
  │      └─ Cập nhật nhiệt độ / độ ẩm / lux trên trang
  │
  └──► Chart polling (60s): GET /api/chart/today → updateMiniCharts()
         └─ Vẽ lại mini chart Morning / Noon / Now
```

---

## 3. Cơ sở dữ liệu SQLite

### 3.1 Vị trí file

```
f:\IoT\do_an\web\sensor_history.db
```

File được tạo tự động khi chạy `app.py` lần đầu (hàm `init_db()`).

> **Tại sao không thấy trong IDE?**
> File `.db` là file nhị phân. Một số IDE ẩn file nhị phân mặc định.
> Để xem nội dung, dùng một trong các cách sau:
> - **DB Browser for SQLite** (GUI miễn phí): https://sqlitebrowser.org/
> - **VS Code extension**: "SQLite Viewer" hoặc "SQLite"
> - **Python REPL**:
>   ```python
>   import sqlite3
>   conn = sqlite3.connect('sensor_history.db')
>   rows = conn.execute('SELECT * FROM sensor_readings ORDER BY id DESC LIMIT 5').fetchall()
>   for r in rows: print(r)
>   ```

### 3.2 Cấu trúc bảng

```sql
CREATE TABLE sensor_readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   DATETIME DEFAULT (datetime('now','localtime')),
    temperature REAL,      -- °C
    humidity    REAL,      -- %
    lux         INTEGER,   -- lux
    fire        INTEGER DEFAULT 0,  -- 0 = không, 1 = có
    gas         INTEGER DEFAULT 0,
    rain        INTEGER DEFAULT 0
);
```

### 3.3 Tần suất ghi

| Tần suất Proteus gửi | Tần suất ghi DB |
|---|---|
| Mỗi 5s (API_INTERVAL) | Tối đa 1 lần/phút |

**Lý do throttle**: Tránh DB phình to quá nhanh. 1 bản ghi/phút = 1440 bản ghi/ngày = hợp lý cho thống kê.

---

## 4. API Endpoints

### Thiết bị

| Method | URL | Mô tả |
|---|---|---|
| GET | `/api/status` | Lấy trạng thái thiết bị (door, window, fan, light, emergency) |
| POST | `/api/status` | Proteus cập nhật trạng thái thiết bị |
| GET | `/api/command` | Proteus đọc lệnh mới nhất (sau khi đọc → reset về "none") |
| POST | `/api/command` | Web gửi lệnh xuống Proteus |

### Cảm biến

| Method | URL | Mô tả |
|---|---|---|
| GET | `/api/sensors` | Lấy dữ liệu cảm biến hiện tại (live) |
| POST | `/api/sensors` | Proteus gửi dữ liệu cảm biến lên |

### Biểu đồ

| Method | URL | Mô tả |
|---|---|---|
| GET | `/api/chart/today` | Trung bình sáng (6–10h), trưa (10–14h) và live now |
| GET | `/api/chart/timeline?period=today\|week\|month` | 7 điểm timeline cho biểu đồ lịch sử |

**Ví dụ response `/api/chart/today`:**
```json
{
  "morning": { "temp": 24.5, "humidity": 62.0, "lux": 280 },
  "noon":    { "temp": 30.1, "humidity": 58.0, "lux": 950 },
  "now":     { "temp": 27.8, "humidity": 60.5, "lux": 520 }
}
```

**Ví dụ response `/api/chart/timeline?period=today`:**
```json
{
  "period": "today",
  "slots": [
    { "label": "12 AM", "temp": 22.1, "humidity": 65.0, "lux": 0 },
    { "label": "4 AM",  "temp": 21.8, "humidity": 66.0, "lux": 0 },
    { "label": "8 AM",  "temp": 24.3, "humidity": 63.0, "lux": 310 },
    { "label": "12 PM", "temp": 30.0, "humidity": 57.0, "lux": 980 },
    { "label": "4 PM",  "temp": 29.2, "humidity": 59.0, "lux": 820 },
    { "label": "8 PM",  "temp": 26.5, "humidity": 61.0, "lux": 140 },
    { "label": "Now",   "temp": 27.8, "humidity": 60.5, "lux": 520 }
  ]
}
```

### Lịch sử & Export

| Method | URL | Mô tả |
|---|---|---|
| GET | `/api/history?period=today\|week\|month` | Thống kê max/min/avg từ DB |
| GET | `/api/history/export?period=today\|week\|month` | Xuất CSV từ DB |
| GET | `/api/lcd` | Lấy text hiển thị trên LCD |
| POST | `/api/lcd` | Proteus cập nhật text LCD |

---

## 5. Export CSV

### Dữ liệu lấy từ đâu?

**Export CSV đọc trực tiếp từ bảng `sensor_readings` trong SQLite.**

```
Người dùng nhấn "Export CSV"
  │
  ▼
history.js: exportCSV()
  │  GET /api/history/export?period=today
  ▼
app.py: export_history_csv()
  └─ Query SQLite: SELECT * FROM sensor_readings WHERE timestamp >= ...
  └─ Tạo file CSV trong bộ nhớ (io.StringIO)
  └─ Trả về Response với Content-Disposition: attachment
  │
  ▼
Trình duyệt tự động tải file .csv
```

**Format file CSV xuất ra:**
```
Timestamp,Temperature (°C),Humidity (%),Lux,Fire,Gas,Rain
2026-03-09 08:00:01,24.5,62.0,280,No,No,No
2026-03-09 08:01:05,24.6,61.8,285,No,No,No
...
```

> **Lưu ý**: Nếu DB chưa có dữ liệu (Proteus chưa chạy), file CSV sẽ chỉ có header.

---

## 6. Polling và cập nhật giao diện

### Trang Index (`index.html`)

| Hàm JS | Interval | API gọi | Cập nhật |
|---|---|---|---|
| `updateUI()` | 2s | `GET /api/status` | Trạng thái nút thiết bị |
| `updateSensorDisplay()` | 3s | `GET /api/sensors` + `GET /api/lcd` | Nhiệt độ/ẩm/lux + header LCD + icon trạng thái |
| `updateMiniCharts()` | 60s | `GET /api/chart/today` | Mini chart Morning/Noon/Now |

### Trang History (`history.html`)

| Hàm JS | Khi nào | API gọi | Cập nhật |
|---|---|---|---|
| `fetchHistory(period)` | Load + 30s + đổi period | `GET /api/history` | Bảng thống kê max/min/avg |
| `updateMainChart(period)` | Load + 30s + đổi period | `GET /api/chart/timeline` | Biểu đồ đường 3 màu |

---

## 7. Cấu trúc file dự án

```
web/
├── app.py                  # Flask server chính
├── sensor_history.db       # SQLite DB (tạo tự động khi chạy)
├── DOCUMENTATION.md        # File này
│
├── templates/
│   ├── index.html          # Trang dashboard chính
│   └── history.html        # Trang lịch sử & biểu đồ
│
├── static/
│   ├── css/style.css       # Neumorphic styles
│   └── js/
│       ├── index.js        # Logic trang chính
│       └── history.js      # Logic trang lịch sử
│
└── protues_files/          # Code chạy trên Proteus/RPi
    ├── main.py             # Vòng lặp chính
    ├── api.py              # HTTP client (gọi Flask server)
    ├── motor_control.py    # Điều khiển motor cửa/cửa sổ
    ├── fan_toggle.py       # Điều khiển quạt
    ├── light_toggle.py     # Điều khiển đèn
    ├── alarms.py           # Còi + LED cảnh báo
    ├── lcd.py              # Điều khiển LCD I2C
    ├── read_sensor.py      # Đọc cảm biến (DHT, LDR, flame, gas, rain)
    └── config.py           # Cấu hình pin, địa chỉ server
```

---

## 8. Khởi động hệ thống

```bash
# 1. Cài đặt dependencies
pip install flask flask-cors

# 2. Chạy server
cd f:\IoT\do_an\web
python app.py

# Server khởi động tại http://localhost:5000
# DB được tạo tự động: sensor_history.db
```

Sau đó chạy Proteus simulation — thiết bị sẽ tự động kết nối với `http://localhost:5000`.

---

## 9. Trạng thái header (icon + LCD text)

Header trang index hiển thị icon + text theo trạng thái môi trường:

| Trạng thái | Điều kiện | Icon | Màu |
|---|---|---|---|
| **Danger** | Phát hiện lửa hoặc gas | `local_fire_department` | Đỏ |
| **Warning** | Mưa / nhiệt độ >35°C / độ ẩm >85% / lux ngoài ngưỡng | `warning` | Vàng cam |
| **Normal** | Tất cả bình thường | `grid_view` | Xanh (primary) |

Text hiển thị lấy từ LCD Proteus (`GET /api/lcd`), format: `"line1 | line2"`.
