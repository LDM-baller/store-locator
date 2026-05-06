/* LDM Locate — viewer (light theme, smart chips, manifest <-> detail flow). */
'use strict';

const RETAILERS = [
  { slug: 'lululemon', name: 'Lululemon', file: 'data/lululemon.json',  color: '#E30613' },
  { slug: 'alo-yoga',  name: 'Alo Yoga',  file: 'data/alo-yoga.json',   color: '#1a1a1a' },
  { slug: 'gucci',     name: 'Gucci',     file: 'data/gucci.json',      color: '#1F5230' },
];

const TYPE_STYLE = {
  flagship:     { radius: 6, weight: 1.5, opacity: 1.00 },
  regular:      { radius: 4, weight: 1.4, opacity: 0.95 },
  concession:   { radius: 4, weight: 1.4, opacity: 0.90 },
  outlet:       { radius: 4, weight: 1.4, opacity: 0.90 },
  popup:        { radius: 3, weight: 1.0, opacity: 0.65 },
  experiential: { radius: 4, weight: 1.4, opacity: 0.85 },
  showroom:     { radius: 3, weight: 1.0, opacity: 0.65 },
  other:        { radius: 3, weight: 1.0, opacity: 0.65 },
  null:         { radius: 4, weight: 1.4, opacity: 0.90 },
};

const COUNTRY_NAMES = {
  US: 'US', CA: 'Canada', MX: 'Mexico', GB: 'UK', IE: 'Ireland', FR: 'France',
  DE: 'Germany', ES: 'Spain', IT: 'Italy', NL: 'Netherlands', BE: 'Belgium',
  CH: 'Switzerland', SE: 'Sweden', NO: 'Norway', DK: 'Denmark', AT: 'Austria',
  AU: 'Australia', NZ: 'New Zealand',
  JP: 'Japan', KR: 'South Korea', CN: 'China', HK: 'Hong Kong', MO: 'Macau',
  TW: 'Taiwan', SG: 'Singapore', MY: 'Malaysia', TH: 'Thailand',
  AE: 'UAE', SA: 'Saudi Arabia', QA: 'Qatar', KW: 'Kuwait', BH: 'Bahrain',
  IL: 'Israel', TR: 'Turkey',
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
  manifestRetailer: null,  // slug currently shown in manifest
  detailFrom: null,        // 'manifest' | 'marker'
};

let map;

async function init() {
  map = L.map('map', { preferCanvas: true, worldCopyJump: true, zoomControl: false })
    .setView([39.5, -98.35], 4);   // continental US default

  L.tileLayer(
    'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      subdomains: 'abcd',
    }
  ).addTo(map);

  await Promise.all(RETAILERS.map(loadRetailer));

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
  document.getElementById('year-min').textContent = state.yearMin;
  document.getElementById('year-max').textContent = state.yearMax;
  document.getElementById('year-display').textContent = state.year;

  buildRetailerToggles();
  rebuildAllMarkers();
  wireUI();
  updateChips();

  document.getElementById('loading').classList.add('hidden');
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
    const btn = document.createElement('button');
    btn.className = 'retailer-toggle active';
    btn.dataset.slug = r.slug;
    btn.innerHTML =
      `<span class="swatch" style="background:${r.color}"></span>` +
      `<span>${r.name}</span>`;
    btn.addEventListener('click', () => {
      state.active[r.slug] = !state.active[r.slug];
      btn.classList.toggle('active', state.active[r.slug]);
      rebuildMarkers(r.slug);
      updateChips();
    });
    host.appendChild(btn);
  });
}

function isVisible(s, year) {
  if (s.status === 'closed') return false;
  if (s.lat == null || s.lng == null) return false;
  // Stores without a known opening year (e.g., a fresh scrape with no
  // year backfill yet) only show at the latest year — they're "currently
  // operating" but their place in the temporal simulation is unknown.
  if (s.year_opened == null) return year >= state.yearMax;
  return s.year_opened <= year;
}

function rebuildAllMarkers() {
  RETAILERS.forEach(r => rebuildMarkers(r.slug));
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
      color: '#ffffff',                 // white outline for contrast on light tiles
      weight: style.weight,
      fillColor: data._color,
      fillOpacity: style.opacity * (s.coord_is_estimated ? 0.6 : 1),
      opacity: 0.95,
    });
    m.on('click', () => openDetail(s, data, 'marker'));
    m.addTo(layer);
    state.markers[slug].set(s.id, m);
  });
}

/* ===== Smart chips (region-aware totals — independent of zoom level) =====
 *
 * The chips call out the current map's dominant country and show the TOTAL
 * stores in that country for each retailer (not just the in-view subset).
 * This way, zooming in on Manhattan still shows "476 US" for Lulu — not 5.
 */

function detectRegion() {
  // Worldwide when zoomed out far enough to see multiple continents.
  const zoom = map.getZoom();
  if (zoom <= 3) return null;
  const bounds = map.getBounds();
  if (bounds.getEast() - bounds.getWest() >= 180) return null;

  // Otherwise: country = country of the visible store nearest the map center.
  // Simple, deterministic, and matches user intuition ("what am I looking at?").
  const center = map.getCenter();
  let best = null, bestDsq = Infinity;
  Object.values(state.data).forEach(d => {
    if (!state.active[d._slug]) return;
    d.stores.forEach(s => {
      if (!isVisible(s, state.year)) return;
      const dy = s.lat - center.lat;
      const dx = s.lng - center.lng;
      const dsq = dy * dy + dx * dx;
      if (dsq < bestDsq) { bestDsq = dsq; best = s; }
    });
  });
  return best ? (best.country || null) : null;
}

function storesInRegion(slug, region) {
  const data = state.data[slug];
  if (!data) return [];
  return data.stores.filter(s => {
    if (!isVisible(s, state.year)) return false;
    if (!region) return true;          // worldwide
    return s.country === region;
  });
}

function updateChips() {
  const host = document.getElementById('chips');
  host.innerHTML = '';
  const region = detectRegion();
  const regionLabel = region ? (COUNTRY_NAMES[region] || region) : 'Worldwide';

  RETAILERS.forEach(r => {
    if (!state.data[r.slug] || !state.active[r.slug]) return;
    const stores = storesInRegion(r.slug, region);
    if (stores.length === 0) return;
    const chip = document.createElement('button');
    chip.className = 'chip';
    chip.dataset.slug = r.slug;
    chip.innerHTML =
      `<span class="swatch" style="background:${r.color}"></span>` +
      `<span class="count">${stores.length.toLocaleString()}</span>` +
      `<span class="region">${escapeHtml(r.name)} · ${escapeHtml(regionLabel)}</span>` +
      `<span class="arrow">›</span>`;
    chip.addEventListener('click', () => openManifest(r.slug, region));
    host.appendChild(chip);
  });
}

/* ===== Manifest sheet ===== */

function openManifest(slug, region) {
  state.manifestRetailer = slug;
  const data = state.data[slug];
  if (region === undefined) region = detectRegion();
  const stores = storesInRegion(slug, region);
  const regionLabel = region ? (COUNTRY_NAMES[region] || region) : 'Worldwide';

  document.getElementById('manifest-title').textContent =
    `${data._name} · ${regionLabel}`;
  document.getElementById('manifest-sub').textContent =
    `${stores.length.toLocaleString()} ${stores.length === 1 ? 'store' : 'stores'} as of ${state.year}`;

  const list = document.getElementById('manifest-list');
  list.innerHTML = '';
  // Sort: by city then name for readability
  const sorted = stores.slice().sort((a, b) =>
    (a.city || '').localeCompare(b.city || '') ||
    (a.name || '').localeCompare(b.name || '')
  );
  sorted.forEach(s => {
    const item = document.createElement('div');
    item.className = 'manifest-item';
    const where = [s.city, s.state].filter(Boolean).join(', ');
    item.innerHTML =
      `<span class="pin" style="background:${data._color}"></span>` +
      `<div class="body">` +
        `<div class="name">${escapeHtml(s.name || '(unnamed)')}</div>` +
        `<div class="meta">${escapeHtml(where)}${s.address ? ' · ' + escapeHtml(s.address) : ''}</div>` +
      `</div>` +
      `<span class="yr">${s.year_opened ?? ''}</span>`;
    item.addEventListener('click', () => openDetail(s, data, 'manifest'));
    list.appendChild(item);
  });

  showSheet('manifest');
}

/* ===== Detail sheet (minimal) ===== */

function openDetail(s, data, from) {
  state.selected = s.id;
  state.detailFrom = from;
  const retailerEl = document.getElementById('detail-retailer');
  const body = document.getElementById('detail-body');
  const back = document.getElementById('detail-back');

  retailerEl.innerHTML =
    `<span class="swatch" style="background:${data._color}"></span>` +
    `${escapeHtml(data._name)}`;

  back.classList.toggle('hidden', from !== 'manifest');

  const estimated = s.coord_is_estimated || (s.raw && s.raw._year_opened_estimated);
  const where = [s.city, s.state, s.country].filter(Boolean).join(', ');
  const addr = s.address || '';
  body.innerHTML =
    `<div class="detail-name">${escapeHtml(s.name || '(unnamed)')}</div>` +
    `<div class="detail-meta-row">` +
      `<span class="item"><span class="k">Type</span><span class="v">${escapeHtml(s.store_type || '—')}</span></span>` +
      `<span class="item"><span class="k">Year</span><span class="v ${estimated ? 'estimated' : ''}">${s.year_opened ?? '—'}</span></span>` +
    `</div>` +
    `<div class="detail-address ${(!addr && !where) ? 'empty' : ''}">` +
      (addr ? escapeHtml(addr) + (where ? `<br>${escapeHtml(where)}` : '') :
        (where ? escapeHtml(where) : 'No address available')) +
      (s.postal_code ? ' ' + escapeHtml(s.postal_code) : '') +
    `</div>`;

  showSheet('detail');
}

/* ===== Sheet machinery ===== */

function showSheet(name) {
  const detail = document.getElementById('detail');
  const manifest = document.getElementById('manifest');
  const backdrop = document.getElementById('sheet-backdrop');

  if (name === 'manifest') {
    manifest.classList.remove('hidden');
    manifest.setAttribute('aria-hidden','false');
    detail.classList.add('hidden');
    detail.setAttribute('aria-hidden','true');
  } else if (name === 'detail') {
    detail.classList.remove('hidden');
    detail.setAttribute('aria-hidden','false');
    if (state.detailFrom !== 'manifest') {
      manifest.classList.add('hidden');
      manifest.setAttribute('aria-hidden','true');
    }
  }
  backdrop.classList.remove('hidden');
  backdrop.setAttribute('aria-hidden','false');
}

function closeSheet() {
  document.getElementById('detail').classList.add('hidden');
  document.getElementById('detail').setAttribute('aria-hidden','true');
  document.getElementById('manifest').classList.add('hidden');
  document.getElementById('manifest').setAttribute('aria-hidden','true');
  document.getElementById('sheet-backdrop').classList.add('hidden');
  document.getElementById('sheet-backdrop').setAttribute('aria-hidden','true');
  state.selected = null;
  state.detailFrom = null;
  state.manifestRetailer = null;
}

function backFromDetail() {
  document.getElementById('detail').classList.add('hidden');
  document.getElementById('detail').setAttribute('aria-hidden','true');
  if (state.detailFrom === 'manifest') {
    document.getElementById('manifest').classList.remove('hidden');
    document.getElementById('manifest').setAttribute('aria-hidden','false');
  } else {
    closeSheet();
  }
  state.selected = null;
  state.detailFrom = null;
}

/* ===== Time slider / play ===== */

function setYear(y, animateBloom) {
  const prevYear = state.year;
  state.year = y;
  document.getElementById('year-display').textContent = y;
  document.getElementById('year-slider').value = y;

  RETAILERS.forEach(r => {
    if (state.active[r.slug]) rebuildMarkers(r.slug);
  });
  updateChips();

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
    left:${point.x}px; top:${point.y}px;
    width:14px; height:14px;
    background:${color};
    box-shadow:0 0 0 2px ${color}40;
  `;
  map.getPane('overlayPane').appendChild(div);
  setTimeout(() => div.remove(), 850);
}

let playInterval = null;
function play() {
  if (state.playing) return;
  state.playing = true;
  document.getElementById('playpause').textContent = '⏸';
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
}

function wireUI() {
  document.getElementById('year-slider').addEventListener('input', e => {
    pause();
    setYear(parseInt(e.target.value, 10), false);
  });
  document.getElementById('playpause').addEventListener('click', () => state.playing ? pause() : play());

  document.querySelectorAll('[data-close]').forEach(btn => {
    btn.addEventListener('click', closeSheet);
  });
  document.getElementById('detail-back').addEventListener('click', backFromDetail);
  document.getElementById('sheet-backdrop').addEventListener('click', closeSheet);

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeSheet();
    if (e.key === ' ' && e.target === document.body) { e.preventDefault(); state.playing ? pause() : play(); }
  });

  // Recompute chips whenever the user pans/zooms
  map.on('moveend', updateChips);
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function showFatalError(msg) {
  const el = document.getElementById('loading');
  if (el) {
    el.textContent = 'ERROR: ' + msg;
    el.style.maxWidth = '90vw';
    el.style.color = '#c0392b';
    el.style.whiteSpace = 'pre-wrap';
    el.style.fontFamily = 'ui-monospace, monospace';
    el.style.fontSize = '11px';
  }
}
window.addEventListener('error', e => showFatalError((e.error && e.error.message) || e.message));
window.addEventListener('unhandledrejection', e => showFatalError('promise: ' + ((e.reason && e.reason.message) || String(e.reason))));
window.addEventListener('DOMContentLoaded', () => {
  init().catch(e => showFatalError(e.message + '\n' + (e.stack || '').split('\n').slice(0,3).join('\n')));
});
