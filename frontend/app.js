// ── Config ─────────────────────────────────────────────────────────────────────
const API_BASE = '/vehicles';

const STATUS = {
  ticket_opened: {
    label: 'Ticket Opened',
    dot:   'bg-gray-500',
    badge: 'bg-gray-50 text-gray-700 ring-1 ring-inset ring-gray-200',
  },
  mechanics: {
    label: 'Mechanics',
    dot:   'bg-orange-500',
    badge: 'bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-200',
  },
  in_test: {
    label: 'In Test',
    dot:   'bg-purple-500',
    badge: 'bg-purple-50 text-purple-700 ring-1 ring-inset ring-purple-200',
  },
  washing: {
    label: 'Washing',
    dot:   'bg-cyan-500',
    badge: 'bg-cyan-50 text-cyan-700 ring-1 ring-inset ring-cyan-200',
  },
  ready_for_payment: {
    label: 'Ready for Payment',
    dot:   'bg-amber-500',
    badge: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200',
  },
  ready: {
    label: 'Ready',
    dot:   'bg-green-500',
    badge: 'bg-green-50 text-green-700 ring-1 ring-inset ring-green-200',
  },
};

const REASONS = {
  annual:      'Annual',
  accident:    'Accident',
  bodywork:    'Bodywork',
  diagnostics: 'Diagnostics',
};

// ── Stats cards config ─────────────────────────────────────────────────────────
const STATS_META = [
  {
    key:   'all',
    label: 'Total Vehicles',
    icon:  'M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10l2 2h9a2 2 0 002-2z',
    color: 'text-blue-600 bg-blue-50',
  },
  {
    key:   'ticket_opened',
    label: 'Ticket Opened',
    icon:  'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
    color: 'text-gray-600 bg-gray-50',
  },
  {
    key:   'mechanics',
    label: 'Mechanics',
    icon:  'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z',
    color: 'text-orange-600 bg-orange-50',
  },
  {
    key:   'in_test',
    label: 'In Test',
    icon:  'M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10l2 2h9a2 2 0 002-2z',
    color: 'text-purple-600 bg-purple-50',
  },
  {
    key:   'ready_for_payment',
    label: 'Ready for Payment',
    icon:  'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z',
    color: 'text-amber-600 bg-amber-50',
  },
  {
    key:   'ready',
    label: 'Ready',
    icon:  'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
    color: 'text-green-600 bg-green-50',
  },
];

// ── State ──────────────────────────────────────────────────────────────────────
let vehicles     = [];
let activeFilter = 'all';
let searchQuery  = '';
let editingPlate = null;
let openDropdownId = null;

// ── API helpers ────────────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const send = () => {
    const apiKey = sessionStorage.getItem('apiKey');
    const headers = {
      'Content-Type': 'application/json',
      ...(apiKey ? { 'X-API-Key': apiKey } : {}),
      ...(options.headers || {}),
    };
    return fetch(path, { ...options, headers });
  };

  let res = await send();

  // Prompt for a key on 401 and retry. Loop so a wrong key can be corrected
  // without the user re-triggering the action.
  let hadKey = !!sessionStorage.getItem('apiKey');
  while (res.status === 401) {
    sessionStorage.removeItem('apiKey');
    const key = await promptApiKey(hadKey ? 'That key was rejected. Please try again.' : '');
    if (!key) {
      throw new Error('API key required');
    }
    sessionStorage.setItem('apiKey', key);
    hadKey = true;
    res = await send();
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  if (res.status === 204) return null;
  return res.json();
}

const api = {
  list:   ()            => apiFetch(`${API_BASE}/`),
  create: (data)        => apiFetch(`${API_BASE}/`,              { method: 'POST',  body: JSON.stringify(data) }),
  update: (plate, data) => apiFetch(`${API_BASE}/${enc(plate)}`, { method: 'PATCH', body: JSON.stringify(data) }),
  remove: (plate)       => apiFetch(`${API_BASE}/${enc(plate)}`, { method: 'DELETE' }),
};

function enc(plate) { return encodeURIComponent(plate); }

// ── API key prompt ─────────────────────────────────────────────────────────────
// A single pending prompt is shared across concurrent apiFetch calls so we only
// ever show one modal at a time; every waiter resolves with the same key.
let pendingKeyPromise = null;
let pendingKeyResolve = null;

function promptApiKey(errorMsg = '') {
  if (pendingKeyPromise) {
    if (errorMsg) setApiKeyError(errorMsg);
    return pendingKeyPromise;
  }

  const overlay = document.getElementById('apikey-overlay');
  const card    = document.getElementById('apikey-card');
  const input   = document.getElementById('apikey-input');
  const submit  = document.getElementById('btn-apikey-submit');

  input.value = '';
  submit.disabled    = false;
  submit.textContent = 'Unlock';
  setApiKeyError(errorMsg);

  resetAnimation(card);
  overlay.classList.remove('hidden');
  setTimeout(() => input.focus(), 50);

  pendingKeyPromise = new Promise(resolve => { pendingKeyResolve = resolve; });
  return pendingKeyPromise;
}

function resolveApiKeyPrompt(value) {
  document.getElementById('apikey-overlay').classList.add('hidden');
  setApiKeyError('');
  const resolve = pendingKeyResolve;
  pendingKeyResolve = null;
  pendingKeyPromise = null;
  if (resolve) resolve(value);
}

function setApiKeyError(msg) {
  const box = document.getElementById('apikey-error');
  document.getElementById('apikey-error-msg').textContent = msg || '';
  box.classList.toggle('hidden', !msg);
}

// ── Load ───────────────────────────────────────────────────────────────────────
async function loadVehicles() {
  setLoadingVisible(true);
  try {
    vehicles = await api.list();
    render();
  } catch (e) {
    showToast(e.message, 'error');
    setLoadingVisible(false);
  }
}

function setLoadingVisible(on) {
  document.getElementById('loading-state').classList.toggle('hidden', !on);
  document.getElementById('vehicle-tbody').classList.toggle('hidden', on);
  document.getElementById('empty-state').classList.add('hidden');
}

// ── Filter ─────────────────────────────────────────────────────────────────────
function getFiltered() {
  const q = searchQuery.toLowerCase().trim();
  return vehicles.filter(v => {
    const matchStatus = activeFilter === 'all' || v.status === activeFilter;
    const matchSearch = !q
      || v.license_plate.toLowerCase().includes(q)
      || v.customer_name.toLowerCase().includes(q)
      || v.phone_number.includes(q);
    return matchStatus && matchSearch;
  });
}

// ── Render ─────────────────────────────────────────────────────────────────────
function render() {
  setLoadingVisible(false);
  renderStats();
  renderFilterTabs();
  renderTable();
}

function renderStats() {
  const counts = { all: vehicles.length };
  for (const key of Object.keys(STATUS)) {
    counts[key] = vehicles.filter(v => v.status === key).length;
  }

  // NOTE: onclick uses single-quoted HTML attribute to safely embed JSON.stringify values.
  document.getElementById('stats').innerHTML = STATS_META.map(s => {
    const active = activeFilter === s.key;
    return `
      <button onclick='setFilter(${q(s.key)})'
        class="bg-white rounded-xl border p-4 text-left hover:shadow-md transition-all
               ${active ? 'border-blue-400 ring-1 ring-blue-400' : 'border-gray-200 hover:border-blue-200'}">
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm font-medium text-gray-500">${s.label}</span>
          <div class="w-8 h-8 rounded-lg flex items-center justify-center ${s.color}">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${s.icon}" />
            </svg>
          </div>
        </div>
        <p class="text-2xl font-bold text-gray-900">${counts[s.key] ?? 0}</p>
      </button>`;
  }).join('');
}

function renderFilterTabs() {
  const tabs = [
    { key: 'all', label: 'All' },
    ...Object.entries(STATUS).map(([k, v]) => ({ key: k, label: v.label })),
  ];

  document.getElementById('filter-tabs').innerHTML = tabs.map(t => `
    <button onclick='setFilter(${q(t.key)})'
      class="px-3 py-1.5 text-sm font-medium rounded-lg transition-colors
             ${activeFilter === t.key
               ? 'bg-blue-600 text-white'
               : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'}">
      ${esc(t.label)}
    </button>`).join('');
}

function renderTable() {
  const filtered = getFiltered();
  const tbody = document.getElementById('vehicle-tbody');
  const empty  = document.getElementById('empty-state');

  if (filtered.length === 0) {
    tbody.innerHTML = '';
    empty.classList.remove('hidden');
    const hasData = vehicles.length > 0;
    document.getElementById('empty-title').textContent = hasData
      ? (searchQuery ? `No vehicles match "${searchQuery}"` : `No vehicles with status "${STATUS[activeFilter]?.label}"`)
      : 'No vehicles yet';
    document.getElementById('empty-sub').textContent = hasData
      ? 'Try adjusting your search or filter.'
      : 'Click "Add Vehicle" to get started.';
    return;
  }

  empty.classList.add('hidden');
  tbody.innerHTML = filtered.map(renderRow).join('');
}

function renderRow(v) {
  const sc    = STATUS[v.status] || STATUS.ticket_opened;
  const plate = v.license_plate;

  const reason = REASONS[v.reason] || '—';
  const added = fmtDate(v.created_at, { day: '2-digit', month: 'short', year: '2-digit' });

  // All onclick attributes use single-quoted HTML attribute delimiters so that the
  // JSON.stringify'd values (which contain double quotes) don't break attribute parsing.
  return `
    <tr class="border-b border-gray-50 last:border-0 hover:bg-gray-50/70 transition-colors group">
      <td class="px-5 py-3.5">
        <span class="font-mono font-semibold text-gray-900 text-sm tracking-wide">${esc(plate)}</span>
      </td>
      <td class="px-5 py-3.5 text-gray-700 font-medium">${esc(v.customer_name)}</td>
      <td class="px-5 py-3.5 text-gray-500">${esc(v.phone_number)}</td>
      <td class="px-5 py-3.5">
        <div class="relative inline-block">
          <button
            onclick='toggleDropdown(event, ${q(plate)})'
            class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium
                   ${sc.badge} hover:opacity-80 transition-opacity cursor-pointer">
            <span class="w-1.5 h-1.5 rounded-full flex-shrink-0 ${sc.dot}"></span>
            ${esc(sc.label)}
            <svg class="w-3 h-3 opacity-50 ml-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <div id="dd-${plate}" class="hidden absolute left-0 top-full mt-1 w-44
               bg-white border border-gray-200 rounded-xl shadow-lg z-20 py-1.5 overflow-hidden">
            ${Object.entries(STATUS).map(([k, c]) => `
              <button onclick='quickStatus(${q(plate)}, ${q(k)})'
                class="w-full text-left flex items-center gap-2.5 px-3 py-2 text-sm
                       hover:bg-gray-50 transition-colors
                       ${v.status === k ? 'text-blue-600 font-semibold bg-blue-50/50' : 'text-gray-700'}">
                <span class="w-2 h-2 rounded-full flex-shrink-0 ${c.dot}"></span>
                ${esc(c.label)}
                ${v.status === k ? `<svg class="w-3.5 h-3.5 ml-auto text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>` : ''}
              </button>`).join('')}
          </div>
        </div>
      </td>
      <td class="px-5 py-3.5 text-gray-600 text-sm">${esc(reason)}</td>
      <td class="px-5 py-3.5 text-gray-400 text-xs">${esc(added)}</td>
      <td class="px-5 py-3.5">
        <button onclick='openModal(${q(plate)})'
          class="opacity-0 group-hover:opacity-100 transition-opacity px-3 py-1.5 text-xs
                 font-medium text-gray-500 hover:text-blue-600 hover:bg-blue-50
                 rounded-lg transition-colors">
          Edit
        </button>
      </td>
    </tr>`;
}

// ── Status dropdown ────────────────────────────────────────────────────────────
function toggleDropdown(e, plate) {
  e.stopPropagation();
  // Capture whether this exact dropdown was already open before closing it.
  const wasOpen = openDropdownId === plate;
  closeOpenDropdown();
  if (!wasOpen) {
    const dd = document.getElementById(`dd-${plate}`);
    if (!dd) return;
    dd.classList.remove('hidden');
    openDropdownId = plate;
  }
}

function closeOpenDropdown() {
  if (openDropdownId) {
    const dd = document.getElementById(`dd-${openDropdownId}`);
    if (dd) dd.classList.add('hidden');
    openDropdownId = null;
  }
}

async function quickStatus(plate, newStatus) {
  closeOpenDropdown();
  try {
    const updated = await api.update(plate, { status: newStatus });
    patchLocal(updated);
    render();
    showToast(`Status → ${STATUS[newStatus].label}`);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ── Modal ──────────────────────────────────────────────────────────────────────
function openModal(plate = null) {
  editingPlate = plate;
  const isEdit = plate !== null;

  document.getElementById('modal-title').textContent = isEdit ? 'Edit Vehicle'  : 'Add Vehicle';
  document.getElementById('btn-submit').textContent  = isEdit ? 'Save Changes'  : 'Add Vehicle';
  document.getElementById('btn-delete').classList.toggle('hidden', !isEdit);
  clearFormError();

  const fPlate = document.getElementById('f-plate');
  fPlate.disabled = isEdit;

  if (isEdit) {
    const v = vehicles.find(x => x.license_plate === plate);
    if (!v) return;
    fPlate.value                              = v.license_plate;
    document.getElementById('f-name').value   = v.customer_name;
    document.getElementById('f-phone').value  = v.phone_number;
    document.getElementById('f-status').value = v.status;
    document.getElementById('f-reason').value = v.reason;
  } else {
    document.getElementById('vehicle-form').reset();
    document.getElementById('f-status').value = 'ticket_opened';
    document.getElementById('f-reason').value = 'annual';
    fPlate.disabled = false;
  }

  resetAnimation(document.getElementById('modal-card'));
  document.getElementById('modal-overlay').classList.remove('hidden');
  setTimeout(() => (isEdit ? document.getElementById('f-name') : fPlate).focus(), 50);
}

// Restart a CSS keyframe animation by clearing it, forcing a reflow, and
// reapplying the class' declared animation. Without this, `modalIn` only plays
// the first time the element becomes visible.
function resetAnimation(el) {
  if (!el) return;
  el.style.animation = 'none';
  // eslint-disable-next-line no-unused-expressions
  el.offsetHeight;
  el.style.animation = '';
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  editingPlate = null;
}

// ── Form validation ────────────────────────────────────────────────────────────
function validateForm(plate, name, phone, reason, isNew) {
  if (isNew) {
    if (!plate) return 'License plate is required.';
    const stripped = plate.replace(/[\s\-]/g, '');
    if (!/^\d{7,8}$/.test(stripped))
      return 'License plate must be exactly 7 or 8 digits.';
  }

  if (!name) return 'Customer name is required.';
  if (!/^[A-Za-z\u0590-\u05FF]+ [A-Za-z\u0590-\u05FF]+$/.test(name))
    return 'Customer name must be exactly two words (Hebrew or English letters) separated by a single space.';

  if (!phone) return 'Phone number is required.';
  const digits = phone.replace(/[\s\-]/g, '');
  if (!/^05[023458]\d{7}$/.test(digits))
    return "Phone must be exactly 10 digits, start with '05', and the 3rd digit must be 0, 2, 3, 4, 5, or 8.";

  if (!reason || !Object.prototype.hasOwnProperty.call(REASONS, reason))
    return 'Please select a valid reason.';

  return null;
}

async function handleFormSubmit(e) {
  e.preventDefault();
  clearFormError();

  const plateRaw = document.getElementById('f-plate').value.trim();
  const plate    = plateRaw.replace(/[\s\-]/g, '');
  const name     = document.getElementById('f-name').value.trim();
  const phoneRaw = document.getElementById('f-phone').value.trim();
  const phone    = phoneRaw.replace(/[\s\-]/g, '');
  const status   = document.getElementById('f-status').value;
  const reason   = document.getElementById('f-reason').value;

  const error = validateForm(plate, name, phone, reason, !editingPlate);
  if (error) { showFormError(error); return; }

  const payload = {
    customer_name: name,
    phone_number:  phone,
    status,
    reason,
  };

  const isEdit = !!editingPlate;
  const btn = document.getElementById('btn-submit');
  btn.disabled    = true;
  btn.textContent = isEdit ? 'Saving…' : 'Adding…';

  try {
    if (isEdit) {
      const updated = await api.update(editingPlate, payload);
      patchLocal(updated);
      showToast('Vehicle updated');
    } else {
      const created = await api.create({ ...payload, license_plate: plate });
      vehicles.unshift(created);
      showToast('Vehicle added');
    }
    closeModal();
    render();
  } catch (err) {
    showFormError(err.message);
  } finally {
    btn.disabled    = false;
    btn.textContent = isEdit ? 'Save Changes' : 'Add Vehicle';
  }
}

async function handleDelete() {
  if (!editingPlate) return;
  const plate = editingPlate;
  if (!confirm(`Delete vehicle "${plate}"?\nThis cannot be undone.`)) return;

  const btn = document.getElementById('btn-delete');
  btn.disabled    = true;
  btn.textContent = 'Deleting…';

  try {
    await api.remove(plate);
    vehicles = vehicles.filter(v => v.license_plate !== plate);
    closeModal();
    render();
    showToast('Vehicle deleted');
  } catch (err) {
    showFormError(err.message);
    btn.disabled    = false;
    btn.textContent = 'Delete Vehicle';
  }
}

function showFormError(msg) {
  document.getElementById('form-error').classList.remove('hidden');
  document.getElementById('form-error-msg').textContent = msg;
}

function clearFormError() {
  document.getElementById('form-error').classList.add('hidden');
  document.getElementById('form-error-msg').textContent = '';
}

// ── Filter control ─────────────────────────────────────────────────────────────
function setFilter(key) {
  activeFilter = key;
  render();
}

// ── Toast ──────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast     = document.createElement('div');
  const isError   = type === 'error';

  toast.className = [
    'toast-enter pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg',
    'text-sm font-medium text-white max-w-xs',
    isError ? 'bg-red-500' : 'bg-gray-900',
  ].join(' ');

  const iconPath = isError
    ? 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
    : 'M5 13l4 4L19 7';

  toast.innerHTML = `
    <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${iconPath}" />
    </svg>
    <span>${esc(msg)}</span>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.replace('toast-enter', 'toast-leave');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  }, 3200);
}

// ── Utility ────────────────────────────────────────────────────────────────────
function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Produces a JS string literal safe for use inside single-quoted HTML attributes.
function q(str) { return JSON.stringify(String(str)); }

function fmtDate(iso, opts) {
  try { return new Date(iso).toLocaleDateString('en-GB', opts); }
  catch { return iso; }
}

function patchLocal(updated) {
  const idx = vehicles.findIndex(v => v.license_plate === updated.license_plate);
  if (idx !== -1) vehicles[idx] = updated;
}

// ── Event wiring ───────────────────────────────────────────────────────────────
document.getElementById('btn-add-vehicle').addEventListener('click', () => openModal());
document.getElementById('btn-modal-close').addEventListener('click', closeModal);
document.getElementById('btn-modal-cancel').addEventListener('click', closeModal);
document.getElementById('btn-delete').addEventListener('click', handleDelete);
document.getElementById('vehicle-form').addEventListener('submit', handleFormSubmit);

document.getElementById('modal-overlay').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeModal();
});

document.getElementById('apikey-form').addEventListener('submit', e => {
  e.preventDefault();
  const value = document.getElementById('apikey-input').value.trim();
  if (!value) {
    setApiKeyError('Please enter a key.');
    return;
  }
  resolveApiKeyPrompt(value);
});

document.getElementById('btn-apikey-cancel').addEventListener('click', () => {
  resolveApiKeyPrompt(null);
});

document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  const apikeyOpen = !document.getElementById('apikey-overlay').classList.contains('hidden');
  if (apikeyOpen) {
    resolveApiKeyPrompt(null);
    return;
  }
  closeModal();
});

document.getElementById('search').addEventListener('input', e => {
  searchQuery = e.target.value;
  renderTable();
});

document.addEventListener('click', closeOpenDropdown);

// ── Boot ───────────────────────────────────────────────────────────────────────
loadVehicles();
