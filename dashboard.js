/* Dashboard — analytics on top of the same retailer JSONs the map uses. */
'use strict';

const RETAILERS = [
  { slug: 'lululemon', name: 'Lululemon', file: 'data/lululemon.json',  color: '#E30613' },
  { slug: 'alo-yoga',  name: 'Alo Yoga',  file: 'data/alo-yoga.json',   color: '#1a1a1a' },
  { slug: 'gucci',     name: 'Gucci',     file: 'data/gucci.json',      color: '#1FA055' },
];

const COUNTRY_NAMES = {
  US: 'US', CA: 'Canada', MX: 'Mexico', BR: 'Brazil', AR: 'Argentina', CL: 'Chile',
  GB: 'UK', IE: 'Ireland', FR: 'France', DE: 'Germany', ES: 'Spain', IT: 'Italy',
  NL: 'Netherlands', BE: 'Belgium', CH: 'Switzerland', SE: 'Sweden', NO: 'Norway',
  DK: 'Denmark', AT: 'Austria', PT: 'Portugal',
  AU: 'Australia', NZ: 'New Zealand',
  JP: 'Japan', KR: 'South Korea', CN: 'China', HK: 'Hong Kong', MO: 'Macau',
  TW: 'Taiwan', SG: 'Singapore', MY: 'Malaysia', TH: 'Thailand',
  AE: 'UAE', SA: 'Saudi Arabia', QA: 'Qatar', KW: 'Kuwait', BH: 'Bahrain',
  IL: 'Israel', TR: 'Turkey',
};

const state = {
  data: {},        // slug -> { stores, ... }
  active: {},      // slug -> bool
  yearMin: 2000,
  yearMax: 2026,
  snapYear: 2026,
};

async function init() {
  await Promise.all(RETAILERS.map(loadRetailer));

  // Derive year range
  const years = [];
  Object.values(state.data).forEach(d => d.stores.forEach(s => {
    if (typeof s.year_opened === 'number') years.push(s.year_opened);
  }));
  if (years.length) {
    state.yearMin = Math.min(...years, state.yearMin);
    state.yearMax = Math.max(...years, state.yearMax);
  }
  state.snapYear = state.yearMax;

  buildRetailerToggles();
  wireSnapshotSlider();
  renderAll();
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
      renderAll();
    });
    host.appendChild(btn);
  });
}

function wireSnapshotSlider() {
  const slider = document.getElementById('snap-year-slider');
  slider.min = state.yearMin;
  slider.max = state.yearMax;
  slider.value = state.snapYear;
  document.getElementById('snap-year-display').textContent = state.snapYear;
  slider.addEventListener('input', e => {
    state.snapYear = parseInt(e.target.value, 10);
    document.getElementById('snap-year-display').textContent = state.snapYear;
    renderSnapshot();
  });
}

function activeStoresAt(retailerSlug, year) {
  const data = state.data[retailerSlug];
  if (!data) return [];
  return data.stores.filter(s => {
    if (s.status === 'closed') return false;
    if (s.year_opened == null) return year >= state.yearMax;
    return s.year_opened <= year;
  });
}

function activeRetailers() {
  return RETAILERS.filter(r => state.data[r.slug] && state.active[r.slug]);
}

/* ===== Render ===== */

function renderAll() {
  renderHeadline();
  renderFleetOverTime();
  renderAnnualOpenings();
  renderTopMarkets();
  renderTypeMix();
  renderSnapshot();
}

function renderHeadline() {
  const host = document.getElementById('headline');
  const active = activeRetailers();
  if (!active.length) { host.innerHTML = '<div class="stat"><div class="num">0</div><div class="lbl">Active retailers</div></div>'; return; }

  const allStores = active.flatMap(r => activeStoresAt(r.slug, state.yearMax));
  const total = allStores.length;
  const countries = new Set(allStores.map(s => s.country).filter(Boolean)).size;
  const newestYear = state.yearMax;
  const newestThisYear = allStores.filter(s => s.year_opened === newestYear).length;
  const flagshipCount = allStores.filter(s => s.store_type === 'flagship').length;

  const stats = [
    { num: total.toLocaleString(),        lbl: 'Active stores', sub: active.map(r => r.name).join(' + ') },
    { num: countries.toLocaleString(),    lbl: 'Countries',     sub: '' },
    { num: '+' + newestThisYear,          lbl: `Opened in ${newestYear}`, sub: '' },
    { num: flagshipCount.toLocaleString(),lbl: 'Flagships',     sub: '' },
  ];
  host.innerHTML = stats.map(st =>
    `<div class="stat"><div class="num">${st.num}</div><div class="lbl">${escapeHtml(st.lbl)}</div>${st.sub ? `<div class="sub">${escapeHtml(st.sub)}</div>` : ''}</div>`
  ).join('');
}

/* ----- Fleet over time (cumulative line chart) ----- */
function renderFleetOverTime() {
  const host = document.getElementById('chart-fleet');
  host.innerHTML = '';
  const active = activeRetailers();
  if (!active.length) { host.innerHTML = '<div class="card-sub">Toggle on a retailer.</div>'; return; }

  const years = [];
  for (let y = state.yearMin; y <= state.yearMax; y++) years.push(y);

  const series = active.map(r => {
    const counts = years.map(y => activeStoresAt(r.slug, y).length);
    return { name: r.name, color: r.color, slug: r.slug, counts };
  });

  const w = 600, h = 220, pad = { l: 36, r: 12, t: 10, b: 26 };
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const maxY = Math.max(1, ...series.flatMap(s => s.counts));
  const niceMax = niceCeil(maxY);
  const xFor = i => pad.l + (i / (years.length - 1)) * innerW;
  const yFor = v => pad.t + innerH - (v / niceMax) * innerH;

  const ticks = niceTicks(0, niceMax, 4);
  const yearTicks = pickYearTicks(years);

  let svg = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet">`;
  // grid
  ticks.forEach(t => {
    const yy = yFor(t);
    svg += `<line class="grid-line" x1="${pad.l}" x2="${w - pad.r}" y1="${yy}" y2="${yy}"/>`;
    svg += `<text class="axis-text" x="${pad.l - 4}" y="${yy + 3}" text-anchor="end">${t.toLocaleString()}</text>`;
  });
  // year labels
  yearTicks.forEach(y => {
    const xx = xFor(years.indexOf(y));
    svg += `<text class="axis-text" x="${xx}" y="${h - 8}" text-anchor="middle">${y}</text>`;
  });
  // lines
  series.forEach(s => {
    const path = s.counts.map((c, i) => `${i === 0 ? 'M' : 'L'}${xFor(i).toFixed(1)},${yFor(c).toFixed(1)}`).join(' ');
    svg += `<path d="${path}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
    // last-point dot
    const last = s.counts.length - 1;
    svg += `<circle cx="${xFor(last)}" cy="${yFor(s.counts[last])}" r="3" fill="${s.color}"/>`;
  });
  svg += `</svg>`;

  host.innerHTML = svg + renderLegend(series.map(s => ({ color: s.color, name: s.name, val: s.counts[s.counts.length - 1].toLocaleString() })));
}

/* ----- Annual openings (stacked bar by retailer) ----- */
function renderAnnualOpenings() {
  const host = document.getElementById('chart-annual');
  host.innerHTML = '';
  const active = activeRetailers();
  if (!active.length) { host.innerHTML = '<div class="card-sub">Toggle on a retailer.</div>'; return; }

  const years = [];
  for (let y = state.yearMin; y <= state.yearMax; y++) years.push(y);

  // Per-year, per-retailer additions (year_opened == y && active)
  const series = active.map(r => {
    const data = state.data[r.slug];
    const counts = years.map(y =>
      data.stores.filter(s => s.status !== 'closed' && s.year_opened === y).length
    );
    return { name: r.name, color: r.color, slug: r.slug, counts };
  });

  const w = 600, h = 200, pad = { l: 36, r: 12, t: 10, b: 26 };
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const stackedTotals = years.map((_, i) => series.reduce((s, sr) => s + sr.counts[i], 0));
  const maxY = Math.max(1, ...stackedTotals);
  const niceMax = niceCeil(maxY);
  const yearTicks = pickYearTicks(years);
  const ticks = niceTicks(0, niceMax, 4);
  const slotW = innerW / years.length;
  const barW = Math.max(2, slotW * 0.7);
  const xFor = i => pad.l + i * slotW + (slotW - barW) / 2;
  const hFor = v => (v / niceMax) * innerH;

  let svg = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet">`;
  ticks.forEach(t => {
    const yy = pad.t + innerH - hFor(t);
    svg += `<line class="grid-line" x1="${pad.l}" x2="${w - pad.r}" y1="${yy}" y2="${yy}"/>`;
    svg += `<text class="axis-text" x="${pad.l - 4}" y="${yy + 3}" text-anchor="end">${t.toLocaleString()}</text>`;
  });
  yearTicks.forEach(y => {
    const idx = years.indexOf(y);
    const xx = xFor(idx) + barW / 2;
    svg += `<text class="axis-text" x="${xx}" y="${h - 8}" text-anchor="middle">${y}</text>`;
  });
  // bars (stacked)
  years.forEach((_, i) => {
    let stack = 0;
    series.forEach(sr => {
      const c = sr.counts[i];
      if (!c) return;
      const x = xFor(i);
      const y = pad.t + innerH - hFor(stack + c);
      const hh = hFor(c);
      svg += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${hh.toFixed(1)}" fill="${sr.color}" opacity="0.95"><title>${sr.name} ${years[i]}: ${c}</title></rect>`;
      stack += c;
    });
  });
  svg += `</svg>`;

  host.innerHTML = svg + renderLegend(series.map(s => ({ color: s.color, name: s.name, val: s.counts.reduce((a,b)=>a+b,0).toLocaleString() })));
}

/* ----- Top markets (HTML horizontal bars) ----- */
function renderTopMarkets() {
  const host = document.getElementById('chart-markets');
  host.innerHTML = '';
  const active = activeRetailers();
  if (!active.length) { host.innerHTML = '<div class="card-sub">Toggle on a retailer.</div>'; return; }

  // Aggregate: country -> { count, breakdown: {slug: count} }
  const map = new Map();
  active.forEach(r => {
    activeStoresAt(r.slug, state.yearMax).forEach(s => {
      const c = s.country || '?';
      if (!map.has(c)) map.set(c, { count: 0, by: {} });
      const ent = map.get(c);
      ent.count += 1;
      ent.by[r.slug] = (ent.by[r.slug] || 0) + 1;
    });
  });
  const sorted = [...map.entries()].sort((a, b) => b[1].count - a[1].count).slice(0, 10);
  const max = sorted.length ? sorted[0][1].count : 1;

  let html = '';
  sorted.forEach(([c, info]) => {
    const label = COUNTRY_NAMES[c] || c;
    const pct = (info.count / max) * 100;
    // Stacked-fill colors by retailer
    const segments = active.filter(r => info.by[r.slug])
      .map(r => ({ color: r.color, w: (info.by[r.slug] / info.count) * pct }));
    let cumX = 0;
    const fills = segments.map(seg => {
      const sty = `left:${cumX}%;width:${seg.w}%;background:${seg.color};opacity:0.95`;
      cumX += seg.w;
      return `<div class="bar-fill" style="${sty}"></div>`;
    }).join('');
    html += `<div class="market-row"><div class="country" title="${escapeHtml(label)}">${escapeHtml(label)}</div><div class="bar-wrap">${fills}</div><div class="count">${info.count.toLocaleString()}</div></div>`;
  });

  host.innerHTML = html;
}

/* ----- Store type mix (donut) ----- */
function renderTypeMix() {
  const host = document.getElementById('chart-types');
  host.innerHTML = '';
  const active = activeRetailers();
  if (!active.length) { host.innerHTML = '<div class="card-sub">Toggle on a retailer.</div>'; return; }

  const counts = new Map();
  active.forEach(r => {
    activeStoresAt(r.slug, state.yearMax).forEach(s => {
      const t = s.store_type || 'unknown';
      counts.set(t, (counts.get(t) || 0) + 1);
    });
  });
  const total = [...counts.values()].reduce((a, b) => a + b, 0);
  const slices = [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => ({ key: k, val: v, pct: v / total }));

  const palette = ['#0f172a','#475569','#94a3b8','#cbd5e1','#1FA055','#E30613','#f59e0b','#8b5cf6'];
  slices.forEach((s, i) => { s.color = palette[i % palette.length]; });

  // Build donut paths
  const cx = 70, cy = 70, r = 56, ir = 36;
  let angle = -Math.PI / 2;
  let paths = '';
  slices.forEach(sl => {
    const sweep = sl.pct * 2 * Math.PI;
    const a1 = angle, a2 = angle + sweep;
    const large = sweep > Math.PI ? 1 : 0;
    const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    const x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
    const x3 = cx + ir * Math.cos(a2), y3 = cy + ir * Math.sin(a2);
    const x4 = cx + ir * Math.cos(a1), y4 = cy + ir * Math.sin(a1);
    paths += `<path d="M${x1.toFixed(2)},${y1.toFixed(2)} A${r},${r} 0 ${large} 1 ${x2.toFixed(2)},${y2.toFixed(2)} L${x3.toFixed(2)},${y3.toFixed(2)} A${ir},${ir} 0 ${large} 0 ${x4.toFixed(2)},${y4.toFixed(2)} Z" fill="${sl.color}"><title>${sl.key}: ${sl.val} (${(sl.pct*100).toFixed(1)}%)</title></path>`;
    angle = a2;
  });

  const svg = `<svg class="donut-svg" viewBox="0 0 140 140">${paths}</svg>`;
  const center = `<div class="donut-center">${svg}<div class="num">${total.toLocaleString()}</div></div>`;
  const legend = `<div class="donut-legend">${slices.map(sl =>
    `<div class="li"><span class="sw" style="background:${sl.color}"></span><span class="nm">${escapeHtml(sl.key)}</span><span class="v">${sl.val.toLocaleString()} · ${(sl.pct*100).toFixed(0)}%</span></div>`).join('')}</div>`;
  host.innerHTML = `<div class="donut-wrap">${center}${legend}</div>`;
}

/* ----- Year snapshot card (always cross-retailer) ----- */
function renderSnapshot() {
  const host = document.getElementById('snap-grid');
  host.innerHTML = '';
  RETAILERS.forEach(r => {
    if (!state.data[r.slug]) return;
    const stores = activeStoresAt(r.slug, state.snapYear);
    const total = stores.length;
    const countries = new Set(stores.map(s => s.country).filter(Boolean));
    // Top market
    const cc = {};
    stores.forEach(s => { cc[s.country || '?'] = (cc[s.country || '?'] || 0) + 1; });
    const topMarket = Object.entries(cc).sort((a,b)=>b[1]-a[1])[0];

    host.innerHTML += `
      <div class="snap-card">
        <div class="head"><span class="sw" style="background:${r.color}"></span>${escapeHtml(r.name)}</div>
        <div class="row"><span class="k">Stores</span><span class="v">${total.toLocaleString()}</span></div>
        <div class="row"><span class="k">Countries</span><span class="v">${countries.size}</span></div>
        ${topMarket ? `<div class="top-mkt">Top market: <strong>${escapeHtml(COUNTRY_NAMES[topMarket[0]] || topMarket[0])}</strong> (${topMarket[1]})</div>` : ''}
      </div>`;
  });
}

/* ===== helpers ===== */

function renderLegend(items) {
  return `<div class="legend">${items.map(i =>
    `<span class="li"><span class="sw" style="background:${i.color}"></span><span class="nm">${escapeHtml(i.name)}</span><span class="v">${i.val}</span></span>`
  ).join('')}</div>`;
}

function niceCeil(x) {
  if (x <= 10) return Math.ceil(x);
  const exp = Math.pow(10, Math.floor(Math.log10(x)));
  const norm = x / exp;
  let nice;
  if (norm <= 1) nice = 1;
  else if (norm <= 2) nice = 2;
  else if (norm <= 5) nice = 5;
  else nice = 10;
  return nice * exp;
}
function niceTicks(min, max, count) {
  const step = (max - min) / count;
  const out = [];
  for (let i = 0; i <= count; i++) out.push(Math.round(min + i * step));
  return out;
}
function pickYearTicks(years) {
  const span = years[years.length - 1] - years[0];
  const stride = span > 20 ? 5 : span > 10 ? 2 : 1;
  return years.filter(y => (y - years[0]) % stride === 0);
}
function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

window.addEventListener('DOMContentLoaded', () => {
  init().catch(e => {
    document.getElementById('loading').textContent = 'ERROR: ' + e.message;
  });
});
