/* Team page — roster grid + filters + detail drawer.
 * MVP: feature #8 (roster grid with filters) + #9 (where they came from drawer).
 * #1 (hire bloom scrubber), #3 (function-fill heatmap), #6 (recruiting heatmap)
 * are layered in later.
 */
'use strict';

const DATA_FILE = 'data/team-alo.json';

const state = {
  retailerName: 'Alo Yoga',
  parent: '',
  people: [],
  filters: { function: null, year: null, prior: null },
};

const LEVEL_ORDER = { founder: 0, 'C-suite': 1, EVP: 2, SVP: 3, VP: 4, Director: 5, 'Sr Director': 5, Head: 6, Other: 7 };

async function init() {
  try {
    const r = await fetch(DATA_FILE, { cache: 'no-cache' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    state.people = d.people || [];
    state.retailerName = d.retailer || 'Team';
    state.parent = d.parent_company || '';
  } catch (e) {
    document.getElementById('loading').textContent = 'ERROR: ' + e.message;
    return;
  }
  document.getElementById('loading').classList.add('hidden');

  // Lede
  const el = document.getElementById('team-lede');
  const sourceCount = state.people.length;
  el.innerHTML = `${sourceCount} named people. Compiled from public LinkedIn snippets, press releases, and company bios. Reporting lines inferred from titles, not confirmed.${state.parent ? ` Parent company: <strong>${escapeHtml(state.parent)}</strong>.` : ''}`;

  buildFilters();
  renderGrid();
  wire();
}

function visiblePeople() {
  return state.people.filter(p => {
    if (state.filters.function && p.function !== state.filters.function) return false;
    if (state.filters.year != null && p.joined !== state.filters.year) return false;
    if (state.filters.prior) {
      const has = (p.history || []).some(h => h.company === state.filters.prior);
      if (!has) return false;
    }
    return true;
  });
}

function buildFilters() {
  // Function chips
  const fnHost = document.getElementById('filter-functions');
  const fnCounts = {};
  state.people.forEach(p => { if (p.function) fnCounts[p.function] = (fnCounts[p.function] || 0) + 1; });
  const fnOrder = Object.entries(fnCounts).sort((a, b) => b[1] - a[1]);
  fnHost.innerHTML = '';
  fnHost.appendChild(makeChip('All', null, 'function', state.people.length, true));
  fnOrder.forEach(([fn, n]) => fnHost.appendChild(makeChip(fn, fn, 'function', n)));

  // Year chips
  const yrHost = document.getElementById('filter-years');
  const yrCounts = {};
  state.people.forEach(p => { if (p.joined) yrCounts[p.joined] = (yrCounts[p.joined] || 0) + 1; });
  const yrOrder = Object.keys(yrCounts).map(Number).sort((a, b) => a - b);
  yrHost.innerHTML = '';
  yrHost.appendChild(makeChip('All', null, 'year', state.people.length, true));
  yrOrder.forEach(y => yrHost.appendChild(makeChip(String(y), y, 'year', yrCounts[y])));

  // Prior-company chips (top 12)
  const prHost = document.getElementById('filter-prior');
  const prCounts = {};
  state.people.forEach(p => {
    const seen = new Set();
    (p.history || []).forEach(h => {
      if (!h.company || seen.has(h.company)) return;
      seen.add(h.company);
      prCounts[h.company] = (prCounts[h.company] || 0) + 1;
    });
  });
  const prOrder = Object.entries(prCounts).sort((a, b) => b[1] - a[1]).slice(0, 14);
  prHost.innerHTML = '';
  prHost.appendChild(makeChip('All', null, 'prior', state.people.length, true));
  prOrder.forEach(([co, n]) => prHost.appendChild(makeChip(co, co, 'prior', n)));
}

function makeChip(label, value, dim, count, active) {
  const btn = document.createElement('button');
  btn.className = 'chip-filter' + (active ? ' active' : '');
  btn.dataset.dim = dim;
  btn.dataset.value = value == null ? '' : String(value);
  btn.innerHTML = `<span>${escapeHtml(label)}</span>` + (count != null ? ` <span class="n">${count}</span>` : '');
  btn.addEventListener('click', () => {
    state.filters[dim] = value;
    document.querySelectorAll(`.chips [data-dim="${dim}"]`).forEach(el => el.classList.remove('active'));
    btn.classList.add('active');
    renderGrid();
  });
  return btn;
}

function renderGrid() {
  const host = document.getElementById('roster-grid');
  host.innerHTML = '';
  const ppl = visiblePeople().slice().sort((a, b) => {
    const la = LEVEL_ORDER[a.level] ?? 9;
    const lb = LEVEL_ORDER[b.level] ?? 9;
    if (la !== lb) return la - lb;
    return (a.name || '').localeCompare(b.name || '');
  });
  if (ppl.length === 0) {
    host.innerHTML = '<div class="card-sub" style="grid-column:1/-1;text-align:center;padding:32px">No matches.</div>';
    return;
  }
  ppl.forEach(p => host.appendChild(personCard(p)));
}

function personCard(p) {
  const card = document.createElement('button');
  card.className = 'person-card';
  card.dataset.id = p.id;
  const priorCompanies = (p.history || []).map(h => h.company).filter(Boolean);
  const priorChips = priorCompanies.slice(0, 4);
  const priorRest = priorCompanies.length - priorChips.length;
  card.innerHTML = `
    <div class="lvl">${escapeHtml(p.level || '—')}${p.function ? ' · ' + escapeHtml(p.function) : ''}</div>
    <div class="name">${escapeHtml(p.name)}</div>
    <div class="title">${escapeHtml(p.title || '')}</div>
    <div class="meta">
      ${p.joined ? `<span class="badge joined">Joined ${p.joined}${p.joined_month ? '·' + monthAbbr(p.joined_month) : ''}</span>` : ''}
      ${p.based_in ? `<span class="badge">${escapeHtml(p.based_in)}</span>` : ''}
    </div>
    ${priorChips.length ? `<div class="prior"><strong>From:</strong> ${priorChips.map(escapeHtml).join(' · ')}${priorRest > 0 ? ` <span style="opacity:0.7">+${priorRest}</span>` : ''}</div>` : ''}
  `;
  card.addEventListener('click', () => openPerson(p));
  return card;
}

function monthAbbr(m) {
  return ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m - 1] || '';
}

function openPerson(p) {
  document.getElementById('person-name').textContent = p.name;
  document.getElementById('person-title').textContent = p.title || '';
  const body = document.getElementById('person-body');
  let html = '';

  // Meta
  const metaParts = [];
  if (p.joined) metaParts.push(`<strong>Joined Alo:</strong> ${p.joined}${p.joined_month ? ' · ' + monthAbbr(p.joined_month) : ''}`);
  if (p.level) metaParts.push(`<strong>Level:</strong> ${escapeHtml(p.level)}`);
  if (p.function) metaParts.push(`<strong>Function:</strong> ${escapeHtml(p.function)}`);
  if (p.based_in) metaParts.push(`<strong>Based in:</strong> ${escapeHtml(p.based_in)}`);
  if (p.education) metaParts.push(`<strong>Education:</strong> ${escapeHtml(p.education)}`);
  if (p.reports_to) {
    const m = state.people.find(x => x.id === p.reports_to);
    if (m) metaParts.push(`<strong>Reports to:</strong> ${escapeHtml(m.name)}`);
  }
  if (metaParts.length) {
    html += `<div class="detail-section"><div class="detail-meta-line">${metaParts.join('<br>')}</div></div>`;
  }

  // Career history
  if (p.history && p.history.length) {
    const sorted = [...p.history].sort((a, b) => {
      const af = a.from || a.to || 0;
      const bf = b.from || b.to || 0;
      return bf - af;
    });
    html += `<div class="detail-section"><h3>Career history</h3>`;
    sorted.forEach(h => {
      const range = h.from || h.to ? `${h.from || '?'}${h.to ? '–' + h.to : (h.from ? '–present' : '')}` : '—';
      html += `<div class="detail-history-row">
        <div class="when">${escapeHtml(range)}</div>
        <div class="what"><span class="co">${escapeHtml(h.company || '?')}</span><span class="role">${escapeHtml(h.role || '')}</span></div>
      </div>`;
    });
    html += `</div>`;
  }

  // Notes
  if (p.notes) {
    html += `<div class="detail-section"><h3>Notes</h3><div class="detail-notes">${escapeHtml(p.notes)}</div></div>`;
  }

  body.innerHTML = html;

  document.getElementById('person-detail').classList.remove('hidden');
  document.getElementById('person-detail').setAttribute('aria-hidden', 'false');
  document.getElementById('sheet-backdrop').classList.remove('hidden');
}

function closePerson() {
  document.getElementById('person-detail').classList.add('hidden');
  document.getElementById('person-detail').setAttribute('aria-hidden', 'true');
  document.getElementById('sheet-backdrop').classList.add('hidden');
}

function wire() {
  document.getElementById('person-close').addEventListener('click', closePerson);
  document.getElementById('sheet-backdrop').addEventListener('click', closePerson);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closePerson(); });

  // Close nav-menu on outside click
  document.addEventListener('click', (e) => {
    const menu = document.getElementById('nav-menu');
    if (menu && !menu.contains(e.target) && menu.open) menu.open = false;
  });
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

window.addEventListener('DOMContentLoaded', init);
