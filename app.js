/* LDM Locate — viewer.
 * Loads multiple retailer JSONs, renders a temporal Leaflet map,
 * and supports click-to-inspect with full provenance.
 */
'use strict';

const RETAILERS = [
  { slug: 'lululemon', name: 'Lululemon', file: 'data/lululemon.json',  color: '#E30613' },
  { slug: 'alo-yoga',  name: 'Alo Yoga',  file: 'data/alo-yoga.json',   color: '#111111' },
];

const TYPE_STYLE = {
  flagship:     { radius: 6, weight: 1.5, opacity: 1.00 },
  regular:      { radius: 4, weight: 1.0, opacity: 0.92 },
  concession:   { radius: 4, weight: 1.0, opacity: 0.85 },
  outlet:       { radius: 4, weight: 1.0, opacity: 0.85 },
  popup:        { radius: 3, weight: 0.6, opacity: 0.55 },
  experiential: { radius: 4, weight: 1.0, opacity: 0.75 },
  showroom:     { radius: 3, weight: 0.6, opacity: 0.55 },
  other:        { radius: 3, weight: 0.6, opacity: 0.55 },
  null:         { radius: 4, weight: 1.0, opacity: 0.85 },
};

const state = {
  data: {},        // slug -> { stores, ... }
  active: {},      // slug -> bool
  layers: {},      // slug -> L.LayerGroup
  markers: {},     // slug -> Map<id, marker>
  year: 2026,
  yearMin: 2000,
  yearMax: 2026,
  playing: false,
  selected: null,
  bloomLayer: null,
};

let map;

async function init() {
  map = L.map('map', { preferCanvas: true, worldCopyJump: true })
    .setView([28, 5], 2);
  L.tileLayer(
    'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    {
      maxZoom: 18,
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      subdomains: 'abcd',
    }
  ).addTo(map);
  state.bloomLayer = L.layerGroup().addTo(map);

  await Promise.all(RETAILERS.map(loadRetailer));

  // Derive year range from data (clamp slider).
  const years = [];
  Object.values(state.data).forEach(d => d.stores.forEach(s => {
    if (typeof s.year_opened === 'number') years.push(s.year_opened);
  }));
  if (years.length) {
    state.yearMin = Math.min(...years, state.yearMin);
    state.yearMax = Math.max(...years, state.yearMax);
  }
  const slider = document.getElementById('year-slider');
  slider.min = state.yearMin;
  slider.max = state.yearMax;
  slider.value = state.yearMax;
  state.year = state.yearMax;
  document.getElementById('year-display').textContent = state.year;

  buildRetailerToggles();
  rebuildAllMarkers();
  wireUI();

  document.getElementById('loading').classList.add('hidden');
  wireSheetGestures();
}

async function loadRetailer(r) {
  try {
    const resp = await fetch(r.file, { cache: 'no-cache' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();
    json._color = r.color;
    json._slug = r.slug;
    json._name = r.name;
    state.data[r.slug] = json;
    state.active[r.slug] = true;
    state.layers[r.slug] = L.layerGroup().addTo(map);
    state.markers[r.slug] = new Map();
  } catch (e) {
    console.warn(`Could not load ${r.file}: ${e.message}`);
  }
}

function buildRetailerToggles() {
  const host = document.getElementById('retailers');
  host.innerHTML = '';
  RETAILERS.forEach(r => {
    if (!state.data[r.slug]) return;
    const total = state.data[r.slug].stores.length;
    const btn = document.createElement('button');
    btn.className = 'retailer-toggle active';
    btn.dataset.slug = r.slug;
    btn.innerHTML =
      `<span class="swatch" style="background:${r.color}"></span>` +
      `<span>${r.name}</span>` +
      `<span class="count" data-count></span>`;
    btn.addEventListener('click', () => {
      state.active[r.slug] = !state.active[r.slug];
      btn.classList.toggle('active', state.active[r.slug]);
      rebuildMarkers(r.slug);
      updateActiveCount();
    });
    host.appendChild(btn);
  });
}

function isVisible(s, year) {
  if (s.status === 'closed') return false;
  if (s.lat == null || s.lng == null) return false;
  if (s.year_opened == null) return false;
  return s.year_opened <= year;
}

function rebuildAllMarkers() {
  RETAILERS.forEach(r => rebuildMarkers(r.slug));
  updateActiveCount();
}

function rebuildMarkers(slug) {
  const layer = state.layers[slug];
  if (!layer) return;
  layer.clearLayers();
  state.markers[slug].clear();
  if (!state.active[slug]) return;

  const data = state.data[slug];
  if (!data) return;

  data.stores.forEach(s => {
    if (!isVisible(s, state.year)) return;
    const style = TYPE_STYLE[s.store_type] || TYPE_STYLE.null;
    const m = L.circleMarker([s.lat, s.lng], {
      radius: style.radius,
      color: data._color,
      weight: style.weight,
      fillColor: data._color,
      fillOpacity: style.opacity * (s.coord_is_estimated ? 0.55 : 1),
      opacity: 1,
    });
    m.on('click', () => openDetail(s, data));
    m.addTo(layer);
    state.markers[slug].set(s.id, m);
  });
}

function updateActiveCount() {
  let total = 0;
  RETAILERS.forEach(r => {
    if (!state.data[r.slug]) return;
    const count = state.active[r.slug]
      ? state.data[r.slug].stores.filter(s => isVisible(s, state.year)).length
      : 0;
    total += count;
    const btn = document.querySelector(`.retailer-toggle[data-slug="${r.slug}"] [data-count]`);
    if (btn) btn.textContent = count;
  });
  document.getElementById('active-count').textContent = total.toLocaleString();
}

function setYear(y, animateBloom) {
  const prevYear = state.year;
  state.year = y;
  document.getElementById('year-display').textContent = y;
  document.getElementById('year-slider').value = y;

  RETAILERS.forEach(r => {
    if (state.active[r.slug]) rebuildMarkers(r.slug);
  });
  updateActiveCount();

  if (animateBloom && y > prevYear) {
    RETAILERS.forEach(r => {
      const data = state.data[r.slug];
      if (!data || !state.active[r.slug]) return;
      data.stores.forEach(s => {
        if (s.year_opened === y && s.lat != null && s.lng != null && s.status !== 'closed') {
          spawnBloom(s.lat, s.lng, data._color);
        }
      });
    });
  }
}

function spawnBloom(lat, lng, color) {
  const point = map.latLngToLayerPoint([lat, lng]);
  const div = document.createElement('div');
  div.className = 'bloom-marker';
  div.style.cssText = `
    position:absolute;
    left:${point.x}px; top:${point.y}px;
    width:14px; height:14px;
    background:${color};
    box-shadow:0 0 0 2px ${color}40;
  `;
  const pane = map.getPane('overlayPane');
  pane.appendChild(div);
  setTimeout(() => div.remove(), 850);
}

let playInterval = null;
function play() {
  if (state.playing) return;
  state.playing = true;
  document.getElementById('playpause').textContent = '⏸';
  document.getElementById('playpause').setAttribute('aria-label','Pause');
  if (state.year >= state.yearMax) state.year = state.yearMin;
  playInterval = setInterval(() => {
    if (state.year >= state.yearMax) { pause(); return; }
    setYear(state.year + 1, true);
  }, 800);
}
function pause() {
  state.playing = false;
  if (playInterval) clearInterval(playInterval);
  playInterval = null;
  document.getElementById('playpause').textContent = '▶';
  document.getElementById('playpause').setAttribute('aria-label','Play');
}

function wireUI() {
  document.getElementById('year-slider').addEventListener('input', e => {
    pause();
    setYear(parseInt(e.target.value, 10), false);
  });
  document.getElementById('playpause').addEventListener('click', () => state.playing ? pause() : play());
  document.getElementById('detail-close').addEventListener('click', closeDetail);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeDetail();
    if (e.key === ' ' && e.target === document.body) { e.preventDefault(); state.playing ? pause() : play(); }
  });
}

function openDetail(s, data) {
  state.selected = s.id;
  const el = document.getElementById('detail');
  const backdrop = document.getElementById('detail-backdrop');
  const body = document.getElementById('detail-body');
  const fmt = (v) => (v == null || v === '') ? '—' : v;
  const validation = s.year_opened_validation || '—';
  const estimated = s.coord_is_estimated || (s.raw && s.raw._year_opened_estimated);
  const status = s.status || 'active';
  const statusLabel = status === 'coming_soon' ? 'Coming soon' : status[0].toUpperCase() + status.slice(1);
  body.innerHTML = `
    <div class="detail-retailer">
      <span class="swatch" style="background:${data._color}"></span>
      ${data._name}
    </div>
    <div class="detail-name">${escapeHtml(s.name || '(no name)')}</div>
    <div class="detail-address">
      ${escapeHtml(fmt(s.address))}<br>
      ${escapeHtml([s.city, s.state, s.country].filter(Boolean).join(', '))} ${escapeHtml(s.postal_code || '')}
    </div>
    <div class="detail-grid">
      <div><div class="k">Year opened</div><div class="v ${estimated ? 'estimated' : ''}">${fmt(s.year_opened)}</div></div>
      <div><div class="k">Type</div><div class="v">${fmt(s.store_type)}</div></div>
      <div><div class="k">Status</div><div class="v">${statusLabel}</div></div>
      <div><div class="k">Phone</div><div class="v">${escapeHtml(fmt(s.phone))}</div></div>
    </div>
    ${s.hours ? `
      <div class="detail-section-title">Hours</div>
      <div class="detail-hours">${escapeHtml(s.hours)}</div>` : ''}
    <div class="detail-section-title">Provenance</div>
    <div class="detail-validation">year_opened_validation: ${escapeHtml(validation)}</div>
    ${s.url ? `<div class="detail-section-title">Source</div>
      <a class="detail-source" href="${escapeAttr(s.url)}" target="_blank" rel="noopener">${escapeHtml(s.url)}</a>` : ''}
  `;
  el.classList.remove('hidden');
  el.setAttribute('aria-hidden','false');
  backdrop.classList.remove('hidden');
  backdrop.setAttribute('aria-hidden','false');
  el.scrollTop = 0;
}
function closeDetail() {
  state.selected = null;
  const el = document.getElementById('detail');
  const backdrop = document.getElementById('detail-backdrop');
  el.classList.add('hidden');
  el.setAttribute('aria-hidden','true');
  backdrop.classList.add('hidden');
  backdrop.setAttribute('aria-hidden','true');
}

function wireSheetGestures() {
  const sheet = document.getElementById('detail');
  const handle = document.getElementById('detail-handle');
  const backdrop = document.getElementById('detail-backdrop');
  backdrop.addEventListener('click', closeDetail);

  // Drag-to-dismiss only on touch (mobile)
  let startY = null;
  let dragging = false;
  let translateY = 0;

  const onStart = (e) => {
    if (window.matchMedia('(min-width: 720px)').matches) return;
    const t = e.touches ? e.touches[0] : e;
    startY = t.clientY;
    dragging = true;
    sheet.style.transition = 'none';
  };
  const onMove = (e) => {
    if (!dragging) return;
    const t = e.touches ? e.touches[0] : e;
    translateY = Math.max(0, t.clientY - startY);
    sheet.style.transform = `translateY(${translateY}px)`;
  };
  const onEnd = () => {
    if (!dragging) return;
    dragging = false;
    sheet.style.transition = '';
    if (translateY > 80) closeDetail();
    sheet.style.transform = '';
    translateY = 0;
  };

  handle.addEventListener('touchstart', onStart, { passive: true });
  handle.addEventListener('touchmove', onMove, { passive: true });
  handle.addEventListener('touchend', onEnd);
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function escapeAttr(s) { return escapeHtml(s); }

window.addEventListener('DOMContentLoaded', init);
