const ARROW = { up: '↑', down: '↓', flat: '→' };
const DIR_COLOR = { up: '#2e7d32', down: '#ef4136', flat: '#ef7f18' };

function fmtPct(x) {
  const v = x * 100;
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}%`;
}

function deltaBadge(pct) {
  if (pct === null || pct === undefined) return '<span class="delta-na">—</span>';
  const cls = pct > 0.005 ? 'delta-up' : pct < -0.005 ? 'delta-dn' : 'delta-flat';
  return `<span class="${cls}">${fmtPct(pct)}</span>`;
}

/* ─── Dashboard ─────────────────────────────────────────── */

function signalCard(sig) {
  const factors = sig.factors || sig.top_drivers || [];
  const factorRows = factors.map(f => {
    const pct = f.pct_change;
    const cls = pct > 0.005 ? 'delta-up' : pct < -0.005 ? 'delta-dn' : 'delta-flat';
    return `<div class="mi-factor-row">
      <span class="mi-factor-name">${f.factor_name}</span>
      <span class="mi-factor-delta ${cls}">${fmtPct(pct)}</span>
    </div>`;
  }).join('');
  return `
    <a class="mi-card" href="/mi/products/${sig.product_id}">
      <div class="mi-card-header">
        <h3>${sig.product_name}</h3>
      </div>
      <div class="mi-factors">${factorRows || '<span class="muted">No factor data</span>'}</div>
    </a>`;
}

async function renderMIDashboard() {
  const root = document.getElementById('mi-dashboard');
  const btn  = document.getElementById('mi-refresh');
  const load = (url, opts) => fetch(url, opts).then(r => r.json());

  const draw = (signals) => {
    root.innerHTML = signals.length
      ? signals.map(signalCard).join('')
      : '<p class="empty">No products configured.</p>';
  };

  try { draw(await load('/api/mi/products')); }
  catch (e) { root.innerHTML = `<p class="empty">Failed to load: ${e.message}</p>`; }

  btn?.addEventListener('click', async () => {
    btn.disabled = true; btn.textContent = 'Refreshing…';
    try { draw((await load('/api/mi/refresh', { method: 'POST' })).signals || []); }
    catch (e) { alert('Refresh failed: ' + e.message); }
    finally { btn.disabled = false; btn.textContent = 'Refresh signals'; }
  });

  wireAddProductModal();
}

/* ─── Add Product modal (dashboard) ──────────────────────── */

function wireAddProductModal() {
  const modal  = document.getElementById('mi-add-modal');
  const openBtn = document.getElementById('mi-add-product');
  const cancel = document.getElementById('mi-add-cancel');
  const form   = document.getElementById('mi-add-form');
  const input  = document.getElementById('mi-add-name');
  const errEl  = document.getElementById('mi-add-error');
  if (!modal || !openBtn || !form) return;

  const close = () => {
    modal.classList.remove('open');
    form.reset();
    errEl.textContent = '';
  };

  openBtn.addEventListener('click', () => {
    modal.classList.add('open');
    setTimeout(() => input.focus(), 50);
  });
  cancel.addEventListener('click', close);
  modal.addEventListener('click', e => { if (e.target.id === 'mi-add-modal') close(); });

  form.addEventListener('submit', e => {
    e.preventDefault();
    const name = (input.value || '').trim();
    if (!name) {
      errEl.textContent = 'Product name is required';
      return;
    }
    // Send the user to the empty-state builder; the first factor add will
    // promote the product into the catalogue (existing flow).
    location.href = `/mi/products/new?name=${encodeURIComponent(name)}`;
  });
}

/* ─── Product detail state ───────────────────────────────── */

let _recipe    = [];   // [{factor_id, factor_name, category, unit, weight_pct, notes, pct_change}]
let _allSeries = {};   // factor_id → [{date, price}]
let _allFactors= [];   // full factor catalogue from /api/mi/factors
let _charts    = {};   // factor_id → Chart instance
let _productId = '';
let _isEmpty   = false;  // true when on /mi/products/new (preview mode, no persist)
let _emptyName = '';     // ?name=... query param for the preview product
let _saveTimer = null;
let _saveStatusEl = null;

function setSaveStatus(text, kind = 'idle') {
  if (!_saveStatusEl) _saveStatusEl = document.getElementById('save-status');
  if (!_saveStatusEl) return;
  _saveStatusEl.textContent = text;
  _saveStatusEl.className = `save-status save-${kind}`;
}

async function persistRecipe(immediate = false) {
  clearTimeout(_saveTimer);
  if (_isEmpty) {
    // First save: no backing product yet. As soon as there is at least one
    // factor in the recipe, promote this preview into a real catalogue entry.
    if (_recipe.length > 0) {
      await promoteToCatalogue();
      return;
    }
    updateSignalBanner(computeLocalSignal());
    setSaveStatus('Preview only', 'idle');
    return;
  }
  const doSave = async () => {
    setSaveStatus('Saving…', 'saving');
    try {
      const body = {
        recipe: _recipe.map(r => ({
          factor_id: r.factor_id,
          weight_pct: r.weight_pct,
          notes: r.notes || '',
        })),
      };
      const res = await fetch(`/api/mi/products/${_productId}/recipe`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      // Update signal banner with the freshly recomputed signal
      updateSignalBanner(data.signal || {});
      setSaveStatus('Saved', 'ok');
      setTimeout(() => setSaveStatus(''), 1500);
    } catch (e) {
      setSaveStatus('Save failed', 'err');
    }
  };
  if (immediate) return doSave();
  _saveTimer = setTimeout(doSave, 500);
}

/**
 * Promote a preview product into the catalogue. Called the first time the user
 * adds a factor while in `_isEmpty` mode. After this call, the page exits
 * preview mode and behaves like any other catalogue product.
 */
async function promoteToCatalogue() {
  setSaveStatus('Saving to catalogue…', 'saving');
  try {
    const res = await fetch('/api/mi/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: _emptyName,
        family: 'custom',
        recipe: _recipe.map(r => ({
          factor_id: r.factor_id,
          weight_pct: r.weight_pct,
          notes: r.notes || '',
        })),
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // Transition out of preview mode
    _productId = data.product_id;
    _isEmpty   = false;
    _emptyName = '';

    // Update URL without reload so refreshing reopens the saved product
    history.replaceState(null, '', `/mi/products/${data.product_id}`);

    // Refresh the meta line (drop the "Preview mode" badge)
    const product = data.product || {};
    const metaEl = document.getElementById('product-meta');
    if (metaEl) metaEl.innerHTML = product.description || '';

    updateSignalBanner(product.signal || {});
    setSaveStatus('Saved to catalogue', 'ok');
    setTimeout(() => setSaveStatus(''), 1800);
  } catch (e) {
    setSaveStatus('Save failed', 'err');
  }
}

/**
 * Compute a directional signal locally from the in-memory _recipe + _allSeries.
 * Used in preview mode where there's no server-side product to PUT against.
 * Mirrors backend `evaluate_additive` — additive weighted sum of pct changes
 * over the latest 90 days available in each factor's series.
 */
function computeLocalSignal() {
  const product_name = _emptyName || _productId;
  if (!_recipe.length) {
    return { product_name, direction: 'flat', pct_change: 0, window_days: 90,
      summary_line: 'Add factors to see a directional signal.' };
  }
  let predicted = 0;
  let topFactor = null, topAbs = -1, topPct = 0;
  let withData = 0;
  for (const r of _recipe) {
    const delta = computeDelta(_allSeries[r.factor_id] || []);
    if (delta == null) continue;
    withData++;
    const coef = (r.weight_pct || 0) / 100;
    const weighted = coef * delta;
    predicted += weighted;
    if (Math.abs(weighted) > topAbs) {
      topAbs = Math.abs(weighted);
      topFactor = r.factor_name;
      topPct = delta;
    }
  }
  let direction = 'flat';
  if (Math.abs(predicted) >= 0.01) direction = predicted > 0 ? 'up' : 'down';
  const summary = topFactor
    ? `${topFactor} ${topPct > 0 ? 'up' : 'down'} ${Math.abs(topPct * 100).toFixed(1)}% drove ${product_name} estimate ${direction === 'flat' ? 'flat' : direction} ${Math.abs(predicted * 100).toFixed(1)}%`
    : 'No factor data available for the selected recipe.';
  return { product_name, direction, pct_change: predicted, window_days: 90, summary_line: summary };
}

function updateSignalBanner(sig) {
  const sigEl = document.getElementById('signal-card');
  if (!sigEl) return;
  const dir = sig.direction || 'flat';
  sigEl.className = `signal-card signal-${dir}`;
  sigEl.innerHTML = `
    <div class="signal-main">
      <span class="signal-arrow">${ARROW[dir]}</span>
      <span class="signal-pct">${fmtPct(sig.pct_change || 0)}</span>
      <span class="signal-window">over ${sig.window_days || 90}d</span>
    </div>
    <p class="signal-line">${sig.summary_line || ''}</p>`;
}

/* ─── Chart helpers ──────────────────────────────────────── */

function computeDelta(series, windowDays = 90) {
  if (!series || series.length < 2) return null;
  const end   = series[series.length - 1].price;
  const cutoff = new Date(series[series.length - 1].date);
  cutoff.setDate(cutoff.getDate() - windowDays);
  const startPt = [...series].reverse().find(p => new Date(p.date) <= cutoff);
  const start = startPt ? startPt.price : series[0].price;
  return start === 0 ? null : (end - start) / start;
}

function buildChart(canvasId, series) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !series?.length) return null;
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: series.map(p => p.date),
      datasets: [{
        data: series.map(p => p.price),
        borderColor: '#ef4136',
        backgroundColor: 'rgba(239,65,54,0.08)',
        fill: true, tension: 0.25, pointRadius: 0, borderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          display: true,
          ticks: {
            font: { size: 10 }, color: '#888', maxTicksLimit: 6,
            callback(val) {
              const d = new Date(this.getLabelForValue(val));
              return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
            }
          },
          grid: { display: false }
        },
        y: { ticks: { font: { size: 10 } }, grid: { color: '#eee' } }
      }
    }
  });
}

function renderCharts() {
  const el = document.getElementById('factor-charts');

  // Destroy ALL existing charts before wiping the DOM — their canvases will
  // be removed by the innerHTML replace, so any cached Chart instances become
  // dangling references. We rebuild every chart fresh after the DOM is in.
  Object.values(_charts).forEach(c => c?.destroy());
  _charts = {};

  if (!_recipe.length) {
    el.innerHTML = `
      <div class="charts-empty">
        <p><strong>No factors selected yet.</strong></p>
        <p class="muted">Add input factors below to see their 90-day price history and compute a directional signal for this product.</p>
      </div>`;
    return;
  }

  el.innerHTML = _recipe.map(r => {
    const series = _allSeries[r.factor_id] || [];
    const delta  = computeDelta(series);
    const deltaStr = delta !== null ? fmtPct(delta) : '—';
    const deltaColor = delta > 0.005 ? '#2e7d32' : delta < -0.005 ? '#ef4136' : '#ef7f18';
    const latestPrice = series.length ? series[series.length - 1].price : null;
    return `
      <div class="factor-chart" id="fc-${r.factor_id}">
        <div class="factor-chart-header">
          <div>
            <strong>${r.factor_name}</strong>
            <span class="muted"> · ${r.unit || ''} · ${r.weight_pct}% weight</span>
          </div>
          <div style="text-align:right">
            ${latestPrice !== null ? `<div class="chart-latest">${latestPrice.toLocaleString()}</div>` : ''}
            <div class="chart-delta" style="color:${deltaColor}">${deltaStr} (90d)</div>
          </div>
        </div>
        <canvas id="chart-${r.factor_id}" height="110"></canvas>
      </div>`;
  }).join('');

  // Rebuild all charts now that the canvases exist in the DOM
  _recipe.forEach(r => {
    const series = _allSeries[r.factor_id] || [];
    _charts[r.factor_id] = buildChart(`chart-${r.factor_id}`, series);
  });
}

/* ─── Recipe table ───────────────────────────────────────── */

function renderRecipeTable() {
  const tbody = document.getElementById('recipe-body');
  if (!_recipe.length) {
    const hint = _isEmpty
      ? 'No recipe yet. Use <strong>+ Add factor…</strong> above to build a cost structure for this product and view its directional signal.'
      : 'No factors in recipe.';
    tbody.innerHTML = `<tr><td colspan="6" class="empty recipe-empty">${hint}</td></tr>`;
    return;
  }
  tbody.innerHTML = _recipe.map((r, i) => {
    const delta = computeDelta(_allSeries[r.factor_id] || []);
    return `
      <tr data-idx="${i}">
        <td><strong>${r.factor_name}</strong></td>
        <td><span class="cat-badge cat-${r.category || 'na'}">${r.category || '—'}</span></td>
        <td>
          <input type="number" class="weight-input" min="0" max="100" step="1"
            value="${r.weight_pct}" data-idx="${i}" />
        </td>
        <td>${deltaBadge(delta)}</td>
        <td class="muted">${r.notes || ''}</td>
        <td>
          <button class="del-btn" data-idx="${i}" title="Remove factor">✕</button>
        </td>
      </tr>`;
  }).join('');

  // Weight edits
  tbody.querySelectorAll('.weight-input').forEach(inp => {
    inp.addEventListener('change', e => {
      const idx = +e.target.dataset.idx;
      _recipe[idx].weight_pct = parseFloat(e.target.value) || 0;
      renderCharts(); // update weight label on chart headers
      persistRecipe();
    });
  });

  // Delete row
  tbody.querySelectorAll('.del-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      const idx = +e.target.dataset.idx;
      _recipe.splice(idx, 1);
      renderRecipeTable();
      renderCharts();
      refreshAddDropdown();
      persistRecipe(true);
    });
  });
}

/* ─── Add factor dropdown ────────────────────────────────── */

async function fetchMissingSeries(factorId) {
  // Always (re)fetch — `_allSeries[factorId]` may be a stale empty [] from
  // a prior failed fetch, or seeded only via the product/factors endpoint
  // which doesn't include factors not in the recipe.
  if (_allSeries[factorId] && _allSeries[factorId].length > 0) {
    console.log(`[mi] series for ${factorId} already cached (${_allSeries[factorId].length} pts)`);
    return;
  }
  try {
    const res = await fetch(`/api/mi/factors/${factorId}/series`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _allSeries[factorId] = data.series || [];
    console.log(`[mi] fetched ${factorId}: ${_allSeries[factorId].length} pts`);
  } catch (e) {
    console.error(`[mi] failed to fetch ${factorId}:`, e);
    _allSeries[factorId] = [];
  }
}

function refreshAddDropdown() {
  const sel = document.getElementById('add-factor-select');
  const inRecipe = new Set(_recipe.map(r => r.factor_id));
  sel.innerHTML = '<option value="">+ Add factor…</option>' +
    _allFactors
      .filter(f => !inRecipe.has(f.id))
      .map(f => `<option value="${f.id}">${f.name} (${f.category})</option>`)
      .join('');
}

/* ─── Main render ────────────────────────────────────────── */

async function renderMIProductDetail() {
  _productId = location.pathname.split('/').pop();
  _isEmpty   = _productId === 'new';
  _emptyName = _isEmpty ? (new URLSearchParams(location.search).get('name') || 'Custom product') : '';

  const nameEl = document.getElementById('product-name');
  const metaEl = document.getElementById('product-meta');
  const sigEl  = document.getElementById('signal-card');

  try {
    let product = null, factorsResp = { factors: [] };
    let allFactors = [];

    if (_isEmpty) {
      // Empty-state: skip the product fetch (would 404), just load factor catalogue
      allFactors = await fetch('/api/mi/factors').then(r => r.json());
    } else {
      [product, factorsResp, allFactors] = await Promise.all([
        fetch(`/api/mi/products/${_productId}`).then(r => r.json()),
        fetch(`/api/mi/products/${_productId}/factors`).then(r => r.json()),
        fetch('/api/mi/factors').then(r => r.json()),
      ]);
    }

    if (_isEmpty) {
      nameEl.textContent = _emptyName;
      metaEl.innerHTML = '<span class="preview-badge">Preview mode &middot; not yet in catalogue</span>';
    } else {
      nameEl.textContent = product.name;
      metaEl.textContent = product.description || '';
    }
    _allFactors = allFactors;

    // Seed series cache from product factors response (none in empty mode)
    (factorsResp.factors || []).forEach(f => { _allSeries[f.factor_id] = f.series || []; });

    // Build recipe with delta pre-computed
    _recipe = ((product && product.recipe) || []).map(r => ({
      factor_id:   r.factor_id,
      factor_name: r.factor_name,
      category:    r.category,
      unit:        r.unit,
      weight_pct:  r.weight_pct,
      notes:       r.notes || '',
    }));

    // Signal banner
    const sig = _isEmpty ? computeLocalSignal() : (product.signal || {});
    const dir = sig.direction || 'flat';
    sigEl.classList.remove('empty');
    sigEl.classList.add(`signal-${dir}`);
    sigEl.innerHTML = `
      <div class="signal-main">
        <span class="signal-arrow">${ARROW[dir]}</span>
        <span class="signal-pct">${fmtPct(sig.pct_change || 0)}</span>
        <span class="signal-window">over ${sig.window_days || 90}d</span>
      </div>
      <p class="signal-line">${sig.summary_line || ''}</p>`;

    renderCharts();
    renderRecipeTable();
    refreshAddDropdown();

    // Add factor handler
    document.getElementById('add-factor-select').addEventListener('change', async e => {
      const sel = e.target;
      const fid = sel.value;
      if (!fid) return;
      sel.value = '';
      sel.disabled = true;
      setSaveStatus('Loading factor…', 'saving');

      try {
        await fetchMissingSeries(fid);
        const factorMeta = _allFactors.find(f => f.id === fid) || {};
        _recipe.push({
          factor_id:   fid,
          factor_name: factorMeta.name || fid,
          category:    factorMeta.category || 'na',
          unit:        factorMeta.unit || '',
          weight_pct:  0,
          notes:       '',
        });

        renderCharts();
        renderRecipeTable();
        refreshAddDropdown();
        await persistRecipe(true);
      } finally {
        sel.disabled = false;
      }
    });

  } catch (e) {
    nameEl.textContent = _productId;
    sigEl.innerHTML = `<p class="empty">Failed to load: ${e.message}</p>`;
  }
}
