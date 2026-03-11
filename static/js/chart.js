// ===== chart.js – SVG line chart rendering engine =====
// Xử lý toàn bộ vẽ biểu đồ SVG: đường, vùng fill, chấm dữ liệu, tooltip hover.
// Không phụ thuộc API_BASE_URL – chỉ thao tác DOM/SVG thuần túy.

// ────────────────────────────────────────────────
// SVG PATH HELPERS
// ────────────────────────────────────────────────

/** Cubic-bezier smooth path qua các điểm [[x, y], ...] */
function smoothPath(pts) {
  if (!pts || pts.length === 0) return '';
  if (pts.length === 1) return `M ${pts[0][0]},${pts[0][1]}`;
  let d = `M ${pts[0][0].toFixed(2)},${pts[0][1].toFixed(2)}`;
  for (let i = 1; i < pts.length; i++) {
    const cpx = ((pts[i - 1][0] + pts[i][0]) / 2).toFixed(2);
    d += ` C ${cpx},${pts[i - 1][1].toFixed(2)} ${cpx},${pts[i][1].toFixed(2)} ${pts[i][0].toFixed(2)},${pts[i][1].toFixed(2)}`;
  }
  return d;
}

/** Min/max từ mảng giá trị với 15% padding để đường không chạm viền */
function computeRange(values) {
  const valid = values.filter(v => v != null);
  if (valid.length === 0) return { min: 0, max: 1 };
  let min = Math.min(...valid), max = Math.max(...valid);
  if (min === max) { min -= 5; max += 5; }
  const pad = (max - min) * 0.15;
  return { min: min - pad, max: max + pad };
}

/** Chuyển value sang tọa độ Y trong viewBox 0 0 1000 300 (Y tăng từ trên xuống) */
function toHistY(value, min, max) {
  const viewH = 300, pad = 15;
  const range = max - min || 1;
  const clamped = Math.max(0, Math.min(1, (value - min) / range));
  return viewH - pad - clamped * (viewH - 2 * pad);
}

// ────────────────────────────────────────────────
// RENDER LINES + AREAS
// ────────────────────────────────────────────────

/**
 * Vẽ đường line + area fill cho một series.
 * viewBox cố định: 0 0 1000 300, các điểm trải đều trên trục X.
 * @param {string} lineId  - id của <path> line
 * @param {string} areaId  - id của <path> area fill
 * @param {Array}  slots   - mảng { label, temp, humidity, lux }
 * @param {string} key     - 'temp' | 'humidity' | 'lux'
 * @param {number} min     - giá trị min của trục Y
 * @param {number} max     - giá trị max của trục Y
 */
function renderHistLine(lineId, areaId, slots, key, min, max) {
  const lineEl = document.getElementById(lineId);
  const areaEl = document.getElementById(areaId);
  if (!lineEl) return;

  const W    = 1000;
  const n    = slots.length;
  const step = n > 1 ? W / (n - 1) : 0;

  const mapped = slots
    .map((s, i) => [i * step, s[key]])
    .filter(([, v]) => v != null)
    .map(([x, v]) => [x, toHistY(v, min, max)]);

  if (mapped.length === 0) return;

  const linePath = mapped.length === 1
    ? `M 0,${mapped[0][1].toFixed(2)} L ${W},${mapped[0][1].toFixed(2)}`
    : smoothPath(mapped);

  const firstX   = mapped[0][0].toFixed(2);
  const lastX    = mapped[mapped.length - 1][0].toFixed(2);
  const areaPath = `${linePath} L ${lastX},290 L ${firstX},290 Z`;

  lineEl.setAttribute('d', linePath);
  if (areaEl) areaEl.setAttribute('d', areaPath);
}

/** Cập nhật nhãn trục X từ mảng slots */
function updateXLabels(slots) {
  const container = document.getElementById('chart-x-labels');
  if (!container) return;
  const spans = container.querySelectorAll('span');
  slots.forEach((s, i) => { if (spans[i]) spans[i].textContent = s.label; });
}

// ────────────────────────────────────────────────
// DATA POINT DOTS
// ────────────────────────────────────────────────

/**
 * Vẽ chấm tròn tại mỗi điểm dữ liệu trên cả 3 đường.
 * @param {Array}  slots  - mảng slots
 * @param {object} tempR  - { min, max } của temperature
 * @param {object} humR   - { min, max } của humidity
 * @param {object} luxR   - { min, max } của lux
 */
function renderChartDots(slots, tempR, humR, luxR) {
  const g = document.getElementById('chart-dots');
  if (!g) return;
  g.innerHTML = '';

  const n    = slots.length;
  const W    = 1000;
  const step = n > 1 ? W / (n - 1) : 0;

  const series = [
    { key: 'temp',     color: '#135bec', min: tempR.min, max: tempR.max },
    { key: 'humidity', color: '#60a5fa', min: humR.min,  max: humR.max  },
    { key: 'lux',      color: '#fbbf24', min: luxR.min,  max: luxR.max  },
  ];

  slots.forEach((slot, i) => {
    const cx = i * step;
    series.forEach(({ key, color, min, max }) => {
      const val = slot[key];
      if (val == null) return;
      const cy = toHistY(val, min, max);

      const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      c.setAttribute('cx',           cx.toFixed(2));
      c.setAttribute('cy',           cy.toFixed(2));
      c.setAttribute('r',            '5');
      c.setAttribute('fill',         color);
      c.setAttribute('stroke',       'rgba(255,255,255,0.85)');
      c.setAttribute('stroke-width', '2.5');
      g.appendChild(c);
    });
  });
}

// ────────────────────────────────────────────────
// TOOLTIP
// ────────────────────────────────────────────────

/**
 * Hiển thị tooltip + đường dọc khi hover vào một mốc thời gian.
 * Temp và Humidity hiển thị 2 số thập phân; Lux là số nguyên.
 */
function showChartTooltip(slot, slotIdx, n) {
  const tooltip   = document.getElementById('chart-tooltip');
  const hoverLine = document.getElementById('chart-hover-line');
  const svg       = document.getElementById('history-chart-svg');
  const container = document.getElementById('chart-container');
  if (!tooltip || !svg || !container) return;

  const fmt2 = v => v != null ? Number(v).toFixed(1) : '--';
  const fmtI = v => v != null ? String(Math.round(v)) : '--';

  document.getElementById('tt-label').textContent = slot.label                  || '';
  document.getElementById('tt-temp').textContent  = slot.temp     != null ? `${fmt2(slot.temp)}°C`     : '--';
  document.getElementById('tt-hum').textContent   = slot.humidity != null ? `${fmt2(slot.humidity)}%`  : '--';
  document.getElementById('tt-lux').textContent   = slot.lux      != null ? `${fmtI(slot.lux)} lux`    : '--';

  // Tọa độ X trong SVG viewBox
  const W    = 1000;
  const svgX = n > 1 ? (slotIdx * W) / (n - 1) : 0;

  // Hiện đường dọc
  if (hoverLine) {
    hoverLine.setAttribute('x1', svgX);
    hoverLine.setAttribute('x2', svgX);
    hoverLine.setAttribute('opacity', '1');
  }

  // Chuyển tọa độ SVG → px so với container để đặt tooltip
  const svgRect       = svg.getBoundingClientRect();
  const containerRect = container.getBoundingClientRect();
  const leftPx        = (svgRect.left - containerRect.left) + (svgX / W) * svgRect.width;

  // Clamp để tooltip không vượt ra ngoài cạnh
  const tooltipW    = 148;
  const clampedLeft = Math.min(
    Math.max(tooltipW / 2, leftPx),
    containerRect.width - tooltipW / 2 - 8
  );

  tooltip.style.left = `${clampedLeft}px`;
  tooltip.classList.remove('hidden');
}

function hideChartTooltip() {
  const tooltip   = document.getElementById('chart-tooltip');
  const hoverLine = document.getElementById('chart-hover-line');
  if (tooltip)   tooltip.classList.add('hidden');
  if (hoverLine) hoverLine.setAttribute('opacity', '0');
}

// ────────────────────────────────────────────────
// HIT AREAS (vùng hover trong suốt)
// ────────────────────────────────────────────────

/**
 * Vẽ <rect> trong suốt bao phủ mỗi mốc thời gian để bắt sự kiện hover.
 * Mỗi rect ôm nửa khoảng trái + nửa khoảng phải quanh điểm đó.
 */
function renderChartHitAreas(slots) {
  const g = document.getElementById('chart-hit-areas');
  if (!g) return;
  g.innerHTML = '';

  const n = slots.length;
  const W = 1000, H = 300;
  if (n === 0) return;

  const step = n > 1 ? W / (n - 1) : W;

  slots.forEach((slot, i) => {
    const cx        = i * step;
    const halfLeft  = i === 0     ? 0 : step / 2;
    const halfRight = i === n - 1 ? 0 : step / 2;
    const x = cx - halfLeft;
    const w = halfLeft + halfRight || step;

    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('x',      Math.max(0, x).toFixed(2));
    rect.setAttribute('y',      '0');
    rect.setAttribute('width',  w.toFixed(2));
    rect.setAttribute('height', H);
    rect.setAttribute('fill',   'transparent');
    rect.style.cursor = 'crosshair';

    rect.addEventListener('mouseenter', () => showChartTooltip(slot, i, n));
    rect.addEventListener('mouseleave', hideChartTooltip);
    rect.addEventListener('touchstart', (e) => {
      e.preventDefault();
      showChartTooltip(slot, i, n);
    }, { passive: false });

    g.appendChild(rect);
  });
}
