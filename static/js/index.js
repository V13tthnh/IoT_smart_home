// ===== API Configuration =====
const API_BASE_URL = 'http://localhost:5000/api';

// ===== Device Control Functions =====

/**
 * Send command to the server
 * @param {string} command - Command to send (fan_on, fan_off, door_open, door_close, etc.)
 */
async function sendCommand(command) {
  try {
    const response = await fetch(`${API_BASE_URL}/command`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ command: command })
    });

    if (!response.ok) {
      console.error(`Error sending command: ${response.statusText}`);
      return false;
    }

    const data = await response.json();
    console.log(`Command '${command}' sent successfully`, data);
    return true;
  } catch (error) {
    console.error('Error sending command:', error);
    return false;
  }
}

/**
 * Fetch current system status
 */
async function getSystemStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/status`);
    if (!response.ok) {
      console.error(`Error fetching status: ${response.statusText}`);
      return null;
    }

    const data = await response.json();
    console.log('System Status:', data);
    return data;
  } catch (error) {
    console.error('Error fetching status:', error);
    return null;
  }
}

/**
 * Fetch sensor data
 */
async function getSensorData() {
  try {
    const response = await fetch(`${API_BASE_URL}/sensors`);
    if (!response.ok) {
      console.error(`Error fetching sensor data: ${response.statusText}`);
      return null;
    }

    const data = await response.json();
    console.log('Sensor Data:', data);
    return data;
  } catch (error) {
    console.error('Error fetching sensor data:', error);
    return null;
  }
}

// ===== Device Configuration =====

const DEVICE_CONFIG = {
  fan:    { onCmd: 'fan_on',      offCmd: 'fan_off',      onText: 'On • Low Speed', offText: 'Off'    },
  door:   { onCmd: 'door_open',   offCmd: 'door_close',   onText: 'Open',           offText: 'Locked' },
  window: { onCmd: 'window_open', offCmd: 'window_close', onText: 'Open',           offText: 'Closed' },
  light:  { onCmd: 'light_on',    offCmd: 'light_off',    onText: 'On • 100%',      offText: 'Off'    },
};

// Local device states – source of truth for button click direction
const deviceStates = { fan: false, door: false, window: false, light: false };

/**
 * Apply visual pressed/released state to a button and update its status text.
 * @param {Element} btn       - the .neumorphic-button element
 * @param {string}  device    - 'fan' | 'door' | 'window' | 'light'
 * @param {boolean} isOn      - true = pressed/active, false = released
 */
function applyButtonState(btn, device, isOn) {
  const cfg   = DEVICE_CONFIG[device];
  const theme = document.documentElement.className;

  if (isOn) {
    btn.style.boxShadow = 'inset 6px 6px 12px #d1d9e6, inset -6px -6px 12px #ffffff';
    btn.style.transform = 'scale(0.98)';
    btn.classList.add('active');
  } else {
    btn.style.boxShadow = theme === 'dark'
      ? '6px 6px 12px #0a0f17, -6px -6px 12px #2c3645'
      : '6px 6px 12px #d1d9e6, -6px -6px 12px #ffffff';
    btn.style.transform = 'scale(1)';
    btn.classList.remove('active');
  }

  const statusEl = btn.querySelector('p:nth-child(2)');
  if (statusEl) statusEl.textContent = isOn ? cfg.onText : cfg.offText;
}

// ===== UI Update Functions =====

/**
 * Update UI based on current system status
 */
async function updateUI() {
  const status = await getSystemStatus();
  if (!status) {
    console.error('Unable to update UI - could not get status');
    return;
  }

  updateDeviceButtons(status);
}

/**
 * Sync all device buttons with the server status.
 * Also keeps deviceStates in sync so subsequent clicks go the right direction.
 */
function updateDeviceButtons(status) {
  const serverStates = {
    fan:    !!status.fan,
    door:   status.door   === 'open',
    window: status.window === 'open',
    light:  !!status.light,
  };

  Object.entries(serverStates).forEach(([device, isOn]) => {
    const btn = document.querySelector(`[data-device="${device}"]`);
    if (btn) {
      deviceStates[device] = isOn;
      applyButtonState(btn, device, isOn);
    }
  });
}

// ===== Real-time Status Updates =====

/**
 * Poll system status and update UI every 2 seconds
 */
let statusPollingInterval = null;

function startStatusPolling(interval = 2000) {
  if (statusPollingInterval) {
    clearInterval(statusPollingInterval);
  }

  statusPollingInterval = setInterval(() => {
    updateUI();
  }, interval);
}

function stopStatusPolling() {
  if (statusPollingInterval) {
    clearInterval(statusPollingInterval);
    statusPollingInterval = null;
  }
}

// ===== Mini Charts (Morning / Noon / Now) =====

/** Tạo SVG path mượt qua các điểm [[x, y], ...] bằng cubic bezier */
function smoothPath(pts) {
  if (!pts || pts.length === 0) return '';
  if (pts.length === 1) return `M ${pts[0][0]},${pts[0][1]}`;
  let d = `M ${pts[0][0].toFixed(2)},${pts[0][1].toFixed(2)}`;
  for (let i = 1; i < pts.length; i++) {
    const cpx = ((pts[i - 1][0] + pts[i][0]) / 2).toFixed(2);
    d += ` C ${cpx},${pts[i-1][1].toFixed(2)} ${cpx},${pts[i][1].toFixed(2)} ${pts[i][0].toFixed(2)},${pts[i][1].toFixed(2)}`;
  }
  return d;
}

/** Tính dải min/max từ mảng giá trị, thêm 15% padding */
function computeRange(values) {
  const valid = values.filter(v => v != null);
  if (valid.length === 0) return { min: 0, max: 1 };
  let min = Math.min(...valid), max = Math.max(...valid);
  if (min === max) { min -= 5; max += 5; }
  const pad = (max - min) * 0.15;
  return { min: min - pad, max: max + pad };
}

/** Chuyển giá trị sang tọa độ Y trong SVG viewBox (0 = trên, viewH = dưới) */
function toMiniY(value, min, max, viewH = 40, pad = 3) {
  const range = max - min || 1;
  const clamped = Math.max(0, Math.min(1, (value - min) / range));
  return viewH - pad - clamped * (viewH - 2 * pad);
}

/** Cập nhật một mini chart SVG từ mảng điểm [[x, value], ...] */
function renderMiniChart(lineId, areaId, points, min, max) {
  const lineEl = document.getElementById(lineId);
  const areaEl = document.getElementById(areaId);
  if (!lineEl) return;

  const mapped = points
    .filter(([, v]) => v != null)
    .map(([x, v]) => [x, toMiniY(v, min, max)]);

  if (mapped.length === 0) return;

  // Nếu chỉ có 1 điểm → vẽ đường ngang
  let linePath;
  if (mapped.length === 1) {
    linePath = `M 0,${mapped[0][1].toFixed(2)} L 100,${mapped[0][1].toFixed(2)}`;
  } else {
    linePath = smoothPath(mapped);
  }

  const last = mapped[mapped.length - 1];
  const areaPath = `${linePath} L ${last[0].toFixed(2)},40 L 0,40 Z`;

  lineEl.setAttribute('d', linePath);
  if (areaEl) areaEl.setAttribute('d', areaPath);
}

async function fetchTodayChart() {
  try {
    const r = await fetch(`${API_BASE_URL}/chart/today`);
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

async function updateMiniCharts() {
  const data = await fetchTodayChart();
  if (!data) return;

  const { morning, noon, now } = data;

  // Nhiệt độ  (x: 0=morning, 50=noon, 100=now)
  const tempPts = [[0, morning?.temp ?? null], [50, noon?.temp ?? null], [100, now?.temp ?? null]];
  const tempR   = computeRange(tempPts.map(([, v]) => v));
  renderMiniChart('chart-temp-line', 'chart-temp-area', tempPts, tempR.min, tempR.max);

  // Độ ẩm
  const humPts = [[0, morning?.humidity ?? null], [50, noon?.humidity ?? null], [100, now?.humidity ?? null]];
  const humR   = computeRange(humPts.map(([, v]) => v));
  renderMiniChart('chart-hum-line', 'chart-hum-area', humPts, humR.min, humR.max);

  // Cường độ ánh sáng
  const luxPts = [[0, morning?.lux ?? null], [50, noon?.lux ?? null], [100, now?.lux ?? null]];
  const luxR   = computeRange(luxPts.map(([, v]) => v));
  renderMiniChart('chart-lux-line', 'chart-lux-area', luxPts, luxR.min, luxR.max);
}

// ===== LCD Text =====

async function getLcdText() {
  try {
    const response = await fetch(`${API_BASE_URL}/lcd`);
    if (!response.ok) return null;
    const data = await response.json();
    return data.lcd_text || null;
  } catch {
    return null;
  }
}

// ===== Status Header (icon + LCD text) =====

const STATUS_PRESETS = {
  danger: {
    icon:      'local_fire_department',
    iconColor: 'text-red-500',
    textColor: 'text-red-600',
  },
  warning: {
    icon:      'warning',
    iconColor: 'text-amber-500',
    textColor: 'text-amber-600',
  },
  normal: {
    icon:      'grid_view',
    iconColor: 'text-primary',
    textColor: 'text-slate-900',
  },
};

/**
 * Resolve current system state from sensor data.
 * Priority: danger > warning > normal
 */
function resolveSystemState(sensors) {
  if (sensors.fire || sensors.gas) return 'danger';
  if (
    sensors.rain        ||
    sensors.temperature > 35  ||
    sensors.humidity    > 85  ||
    sensors.lux         >= 1000 ||
    (sensors.lux > 0 && sensors.lux < 100)
  ) return 'warning';
  return 'normal';
}

/**
 * Update the header icon and LCD text based on current sensor state.
 */
async function updateStatusHeader(sensors) {
  const state   = resolveSystemState(sensors);
  const preset  = STATUS_PRESETS[state];

  const container = document.getElementById('status-icon-container');
  const iconEl    = document.getElementById('status-icon');
  const textEl    = document.getElementById('status-text');

  if (iconEl) {
    iconEl.textContent = preset.icon;
    iconEl.className   = `material-symbols-outlined text-2xl ${preset.iconColor}`;
  }
  if (container) {
    container.className = container.className
      .replace(/text-\S+/g, '')
      .trim() + ` ${preset.iconColor}`;
  }
  if (textEl) {
    textEl.className = textEl.className
      .replace(/text-(?:slate-900|red-\d+|amber-\d+)/g, '')
      .trim() + ` ${preset.textColor}`;

    // Update text from LCD
    const lcd = await getLcdText();
    if (lcd) {
      textEl.textContent = lcd;
    } else {
      const fallback = { danger: 'DANGER!', warning: 'WARNING!', normal: 'Environmental Monitoring' };
      textEl.textContent = fallback[state];
    }
  }
}

// ===== Sensor Data Update =====

/**
 * Update sensor data display and status header
 */
async function updateSensorDisplay() {
  const sensors = await getSensorData();
  if (!sensors) {
    console.error('Unable to get sensor data');
    return;
  }

  // Update Temperature
  const tempElement = document.querySelector('[data-sensor="temperature"]');
  if (tempElement) {
    tempElement.textContent = sensors.temperature.toFixed(1);
  }

  // Update Humidity
  const humElement = document.querySelector('[data-sensor="humidity"]');
  if (humElement) {
    humElement.textContent = sensors.humidity.toFixed(1);
  }

  // Update Lux
  const luxElement = document.querySelector('[data-sensor="lux"]');
  if (luxElement) {
    luxElement.textContent = sensors.lux;
  }

  // Update status header icon + LCD text
  await updateStatusHeader(sensors);
}

// ===== Theme Management =====

/**
 * Initialize theme from localStorage
 */
function initializeTheme() {
  const htmlElement = document.documentElement;
  const savedTheme = localStorage.getItem('theme') || 'light';
  htmlElement.className = savedTheme;
  return savedTheme;
}

/**
 * Update theme buttons active states
 */
function updateThemeButtons(theme) {
  document.querySelectorAll('button').forEach(btn => {
    const innerHTML = btn.innerHTML;

    if (innerHTML.includes('light_mode')) {
      if (theme === 'light') {
        btn.classList.add('!bg-slate-200', '!text-primary');
      } else {
        btn.classList.remove('!bg-slate-200', '!text-primary');
      }
    }
    if (innerHTML.includes('dark_mode')) {
      if (theme === 'dark') {
        btn.classList.add('!bg-slate-700', '!text-slate-100');
      } else {
        btn.classList.remove('!bg-slate-700', '!text-slate-100');
      }
    }
  });
}

// ===== (deviceStates and applyButtonState are defined above near DEVICE_CONFIG) =====

// ===== Initialize on Page Load =====

document.addEventListener('DOMContentLoaded', function() {
  console.log('IoT Dashboard initialized');

  const htmlElement = document.documentElement;
  const savedTheme = initializeTheme();

  // Initial UI update
  updateUI();

  // Start polling for status updates
  startStatusPolling(2000);

  // Start updating sensor display
  let sensorInterval = setInterval(updateSensorDisplay, 3000);

  // Mini charts: tải ngay lúc đầu rồi cập nhật mỗi 60s
  updateMiniCharts();
  setInterval(updateMiniCharts, 60000);

  // Add button event listeners
  setupButtonListeners();

  // Setup theme buttons
  setupThemeButtons(savedTheme);
});

/**
 * Setup theme toggle buttons
 */
function setupThemeButtons(currentTheme) {
  document.querySelectorAll('button').forEach(btn => {
    const innerHTML = btn.innerHTML;

    // Light Mode Button
    if (innerHTML.includes('light_mode')) {
      console.log('Found light mode button');
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        document.documentElement.className = 'light';
        localStorage.setItem('theme', 'light');
        updateThemeButtons('light');
        console.log('Switched to light theme');
      });
      if (currentTheme === 'light') {
        btn.classList.add('!bg-slate-200', '!text-primary');
      }
    }

    // Dark Mode Button
    if (innerHTML.includes('dark_mode')) {
      console.log('Found dark mode button');
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        document.documentElement.className = 'dark';
        localStorage.setItem('theme', 'dark');
        updateThemeButtons('dark');
        console.log('Switched to dark theme');
      });
      if (currentTheme === 'dark') {
        btn.classList.add('!bg-slate-700', '!text-slate-100');
      }
    }

    // View History Button
    if (btn.textContent.trim() === 'View History') {
      console.log('Found view history button');
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        console.log('Navigating to history page');
        window.location.href = '/history';
      });
    }
  });
}

/**
 * Setup event listeners for device control buttons.
 * Uses local deviceStates (not server) to decide the command direction,
 * so the button is always responsive regardless of server polling lag.
 */
function setupButtonListeners() {
  const keywordMap = [
    { keyword: 'Living Fan',    device: 'fan'    },
    { keyword: 'Main Entrance', device: 'door'   },
    { keyword: 'Patio Windows', device: 'window' },
    { keyword: 'Dining Lights', device: 'light'  },
  ];

  document.querySelectorAll('.neumorphic-button').forEach(btn => {
    const text = btn.textContent.trim();

    keywordMap.forEach(({ keyword, device }) => {
      if (text.includes(keyword)) {
        // Set data-device so updateDeviceButtons() selector works
        btn.dataset.device = device;

        btn.addEventListener('click', async function(e) {
          e.preventDefault();

          // Determine new state from local (not server) – avoids race condition
          const willBeOn = !deviceStates[device];
          const cfg      = DEVICE_CONFIG[device];
          const command  = willBeOn ? cfg.onCmd : cfg.offCmd;

          // Optimistic UI update immediately
          deviceStates[device] = willBeOn;
          applyButtonState(btn, device, willBeOn);
          console.log(`${device} → ${command}`);

          // Send command; rollback on failure
          const success = await sendCommand(command);
          if (!success) {
            deviceStates[device] = !willBeOn;
            applyButtonState(btn, device, !willBeOn);
            console.error(`${device} command failed, rolled back`);
          }
        });
      }
    });
  });
}

// ===== Cleanup on Page Unload =====

window.addEventListener('beforeunload', function() {
  stopStatusPolling();
});
