// ===== history.js – History page logic =====
// Data fetching, statistics display, period/theme/export UI.
// Chart rendering được xử lý bởi chart.js (load trước file này).

const API_BASE_URL    = 'http://localhost:5000/api';
const REFRESH_INTERVAL = 30000; // 30 giây

let currentPeriod = 'today';
let refreshTimer  = null;

// ────────────────────────────────────────────────
// DATA FETCH
// ────────────────────────────────────────────────

async function fetchHistory(period) {
  try {
    const r = await fetch(`${API_BASE_URL}/history?period=${period}`);
    if (!r.ok) { console.error('History API error:', r.statusText); return null; }
    return await r.json();
  } catch (err) {
    console.error('fetchHistory failed:', err);
    return null;
  }
}

async function fetchChartTimeline(period) {
  try {
    const r = await fetch(`${API_BASE_URL}/chart/timeline?period=${period}`);
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

// ────────────────────────────────────────────────
// STATISTICS DOM
// ────────────────────────────────────────────────

function updateStatistics(data) {
  if (!data) return;

  setEl('trends-title',    data.title    || '');
  setEl('trends-subtitle', data.subtitle || '');
  setEl('period-label',    data.label    || '');

  if (data.total_records === 0) {
    showNoDataMessage(true);
    return;
  }
  showNoDataMessage(false);

  const fmt  = (v, d = 1) => v == null ? '--' : Number(v).toFixed(d);
  const fmtI = v           => v == null ? '--' : Math.round(v).toString();

  setEl('temp-highest',     fmt(data.highest?.temp));
  setEl('humidity-highest', fmt(data.highest?.humidity));
  setEl('light-highest',    fmtI(data.highest?.light));

  setEl('temp-lowest',     fmt(data.lowest?.temp));
  setEl('humidity-lowest', fmt(data.lowest?.humidity));
  setEl('light-lowest',    fmtI(data.lowest?.light));

  setEl('temp-average',     fmt(data.average?.temp));
  setEl('humidity-average', fmt(data.average?.humidity));
  setEl('light-average',    fmtI(data.average?.light));

  setEl('total-records', data.total_records ?? 0);
}

function setEl(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function showNoDataMessage(show) {
  const msg = document.getElementById('no-data-msg');
  if (msg) msg.style.display = show ? 'block' : 'none';
}

// ────────────────────────────────────────────────
// CHART ORCHESTRATION  (dùng hàm từ chart.js)
// ────────────────────────────────────────────────

async function updateMainChart(period) {
  const data = await fetchChartTimeline(period);
  if (!data || !data.slots || data.slots.length < 2) return;

  const { slots } = data;

  const tempR = computeRange(slots.map(s => s.temp));
  const humR  = computeRange(slots.map(s => s.humidity));
  const luxR  = computeRange(slots.map(s => s.lux));

  renderHistLine('hist-temp-line', 'hist-temp-area', slots, 'temp',     tempR.min, tempR.max);
  renderHistLine('hist-hum-line',  'hist-hum-area',  slots, 'humidity', humR.min,  humR.max);
  renderHistLine('hist-lux-line',  'hist-lux-area',  slots, 'lux',      luxR.min,  luxR.max);

  updateXLabels(slots);
  hideChartTooltip();
  renderChartDots(slots, tempR, humR, luxR);
  renderChartHitAreas(slots);
}

// ────────────────────────────────────────────────
// PERIOD BUTTONS
// ────────────────────────────────────────────────

function updatePeriodButtons(active) {
  document.querySelectorAll('[data-period]').forEach(btn => {
    const isActive = btn.dataset.period === active;
    btn.classList.toggle('neumorphic-tab-active', isActive);
    btn.classList.toggle('text-slate-500',        !isActive);
    btn.classList.toggle('hover:text-slate-700',  !isActive);
  });
}

// ────────────────────────────────────────────────
// THEME
// ────────────────────────────────────────────────

function updateThemeButtons(theme) {
  document.querySelectorAll('button').forEach(btn => {
    const html = btn.innerHTML;
    if (html.includes('light_mode')) {
      btn.classList.toggle('!bg-slate-200', theme === 'light');
      btn.classList.toggle('!text-primary',  theme === 'light');
    }
    if (html.includes('dark_mode')) {
      btn.classList.toggle('!bg-slate-700',   theme === 'dark');
      btn.classList.toggle('!text-slate-100', theme === 'dark');
    }
  });
}

// ────────────────────────────────────────────────
// AUTO REFRESH
// ────────────────────────────────────────────────

function startAutoRefresh() {
  stopAutoRefresh();
  refreshTimer = setInterval(async () => {
    const data = await fetchHistory(currentPeriod);
    updateStatistics(data);
    await updateMainChart(currentPeriod);
  }, REFRESH_INTERVAL);
}

function stopAutoRefresh() {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
}

// ────────────────────────────────────────────────
// EXPORT CSV
// ────────────────────────────────────────────────

function exportCSV() {
  window.location.href = `${API_BASE_URL}/history/export?period=${currentPeriod}`;
}

// ────────────────────────────────────────────────
// INIT
// ────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async function () {
  const html = document.documentElement;

  // Theme
  const savedTheme = localStorage.getItem('theme') || 'light';
  html.className = savedTheme;
  updateThemeButtons(savedTheme);

  // Buttons
  document.querySelectorAll('button').forEach(btn => {
    const inner = btn.innerHTML;
    const text  = btn.textContent.trim();

    if (inner.includes('arrow_back')) {
      btn.addEventListener('click', (e) => { e.preventDefault(); window.location.href = '/'; });
    }
    if (inner.includes('light_mode')) {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        html.className = 'light';
        localStorage.setItem('theme', 'light');
        updateThemeButtons('light');
      });
    }
    if (inner.includes('dark_mode')) {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        html.className = 'dark';
        localStorage.setItem('theme', 'dark');
        updateThemeButtons('dark');
      });
    }
    if (text.includes('Export CSV')) {
      btn.addEventListener('click', (e) => { e.preventDefault(); exportCSV(); });
    }
  });

  // Period tabs
  document.querySelectorAll('[data-period]').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      currentPeriod = btn.dataset.period;
      updatePeriodButtons(currentPeriod);
      const data = await fetchHistory(currentPeriod);
      updateStatistics(data);
      await updateMainChart(currentPeriod);
    });
  });

  // Initial load
  updatePeriodButtons(currentPeriod);
  const initialData = await fetchHistory(currentPeriod);
  updateStatistics(initialData);
  await updateMainChart(currentPeriod);

  startAutoRefresh();
});

window.addEventListener('beforeunload', stopAutoRefresh);
