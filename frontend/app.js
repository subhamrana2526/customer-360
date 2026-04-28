const api = {
  customers: () => fetch('/api/customers').then(r => r.json()),
  customer: id => fetch(`/api/customers/${id}`).then(r => r.json()),
  brief: id => fetch(`/api/customers/${id}/brief`).then(r => r.ok ? r.json() : null),
  raw: id => fetch(`/api/customers/${id}/raw`).then(r => r.ok ? r.json() : {}),
  stage1: id => fetch(`/api/customers/${id}/stage1`).then(r => r.ok ? r.json() : null),
  refresh: id => fetch(`/api/customers/${id}/refresh`, { method: 'POST' }).then(r => r.json()),
  miProducts: () => fetch('/api/mi/products').then(r => r.ok ? r.json() : []),
  addCustomer: (body) => fetch('/api/customers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e.detail || 'Failed'))),
};

function customerIdFromPath() {
  const m = window.location.pathname.match(/\/customers\/([^/]+)/);
  return m ? m[1] : null;
}

async function renderCustomerList() {
  const grid = document.getElementById('customer-grid');
  const customers = await api.customers();
  grid.innerHTML = customers.map(c => `
    <a class="card" href="/customers/${c.customer_id}">
      <h3>${c.company_name}</h3>
      <p class="industry">${c.industry}</p>
      <p class="geography">${c.geography} &middot; ${c.segment}</p>
    </a>
  `).join('') || '<p>No customers yet.</p>';

  document.getElementById('add-customer-btn').onclick = () => {
    document.getElementById('add-customer-modal').classList.add('open');
    document.getElementById('ac-company').focus();
  };
  document.getElementById('ac-cancel').onclick = _closeModal;
  document.getElementById('add-customer-modal').onclick = (e) => {
    if (e.target.id === 'add-customer-modal') _closeModal();
  };
  document.getElementById('add-customer-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = document.getElementById('ac-submit');
    const err = document.getElementById('ac-error');
    const status = document.getElementById('ac-status');
    btn.disabled = true;
    err.textContent = '';
    status.textContent = 'Inferring profile and running pipeline… this takes ~30s';
    try {
      const result = await api.addCustomer({
        company_name: document.getElementById('ac-company').value.trim(),
        hubspot_company_id: document.getElementById('ac-hubspot').value.trim(),
        elixir_customer_id: document.getElementById('ac-elixir').value.trim(),
      });
      _closeModal();
      window.location.href = `/customers/${result.customer_id}`;
    } catch (e) {
      err.textContent = typeof e === 'string' ? e : 'Something went wrong. Try again.';
      status.textContent = '';
      btn.disabled = false;
    }
  };
}

function _closeModal() {
  document.getElementById('add-customer-modal').classList.remove('open');
  document.getElementById('add-customer-form').reset();
  document.getElementById('ac-error').textContent = '';
  document.getElementById('ac-status').textContent = '';
  document.getElementById('ac-submit').disabled = false;
}

function _briefCard({ title, span = 1, body }) {
  return `
    <article class="brief-card brief-card-${span}">
      <div class="brief-card-header">
        <h2 class="brief-card-title">${title}</h2>
      </div>
      <div class="brief-card-body">${body}</div>
    </article>`;
}

// Normalize a product name for fuzzy matching against MI catalogue.
function _normalizeProductName(name) {
  return (name || '')
    .toLowerCase()
    .replace(/\([^)]*\)/g, '')   // strip parenthetical (e.g. "(DEP)", "(Almond Aldehyde)")
    .replace(/[^a-z0-9 ]+/g, ' ') // strip punctuation
    .replace(/\s+/g, ' ')
    .trim();
}

// Try to map a customer-facing product name to an MI product id.
// Returns the matching MI product, or null.
function _matchMIProduct(productName, miProducts) {
  if (!productName || !miProducts?.length) return null;
  const norm = _normalizeProductName(productName);
  if (!norm) return null;
  // Exact match on normalized MI product name first
  for (const mi of miProducts) {
    if (_normalizeProductName(mi.product_name) === norm) return mi;
  }
  // Substring match (MI product name appears inside the customer name)
  for (const mi of miProducts) {
    const miNorm = _normalizeProductName(mi.product_name);
    if (miNorm && norm.includes(miNorm)) return mi;
  }
  return null;
}

function _miLink(mi, productName) {
  if (mi) {
    return `<a class="mi-jump" href="/mi/products/${mi.product_id}">View Market Intelligence &rarr;</a>`;
  }
  // No MI match — link to the empty-state builder so the user can configure
  // a recipe for this product on the fly.
  const q = encodeURIComponent(productName || '');
  return `<a class="mi-jump mi-jump-empty" href="/mi/products/new?name=${q}">View Market Intelligence &rarr;</a>`;
}

function _relatedProductsBody(brief, miProducts) {
  const angles = brief.pitch_angles || [];
  if (!angles.length) return '<p class="brief-empty-text">No related products surfaced.</p>';
  return `<ul class="pitch-list">${angles.map(p => {
    const mi = _matchMIProduct(p.product_name, miProducts);
    return `
      <li>
        <div class="pitch-product">${p.product_name}</div>
        <div class="pitch-rationale">${p.rationale}</div>
        ${_miLink(mi, p.product_name)}
      </li>`;
  }).join('')}</ul>`;
}

function _openInquiriesBody(rawHubspot, miProducts) {
  const inquiries = (rawHubspot?.inquired_products || []).filter(i => i.is_open_deal);
  if (!inquiries.length) return '<p class="brief-empty-text">No open inquiries on file.</p>';
  // De-dupe by product name (HubSpot can list the same product across multiple deals)
  const seen = new Set();
  const unique = inquiries.filter(i => {
    const key = (i.name || '').toLowerCase().trim();
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  return `<ul class="inquiry-list">${unique.map(i => {
    const mi = _matchMIProduct(i.name, miProducts);
    return `
      <li>
        <div class="inquiry-product">${i.name}</div>
        <div class="inquiry-meta">
          ${i.deal_name ? `<span class="inquiry-deal">${i.deal_name}</span>` : ''}
          ${i.quantity ? `<span class="inquiry-qty">Qty: ${i.quantity}</span>` : ''}
          ${i.deal_date ? `<span class="inquiry-date">${i.deal_date}</span>` : ''}
        </div>
        ${_miLink(mi, i.name)}
      </li>`;
  }).join('')}</ul>`;
}

function renderBrief(brief, opts = {}) {
  if (!brief) {
    return '<div class="brief-empty">No brief yet. Click <strong>Refresh Brief</strong> to generate.</div>';
  }
  const { miProducts = [], rawHubspot = null } = opts;

  const starters = (brief.conversation_starters || []).length
    ? `<ul class="starter-list">${brief.conversation_starters.map(s => `<li>${s}</li>`).join('')}</ul>`
    : '<p class="brief-empty-text">No conversation starters yet.</p>';

  return [
    _briefCard({ title: 'Conversation recap',    span: 2, body: `<p>${brief.conversation_recap || '—'}</p>` }),
    _briefCard({ title: 'Customer snapshot',     span: 1, body: `<p>${brief.customer_snapshot || '—'}</p>` }),
    _briefCard({ title: "What's new",            span: 1, body: `<p>${brief.whats_new || '—'}</p>` }),
    _briefCard({ title: 'Market context',        span: 2, body: `<p>${brief.market_context || '—'}</p>` }),
    _briefCard({ title: 'Related products',      span: 1, body: _relatedProductsBody(brief, miProducts) }),
    _briefCard({ title: 'Open inquiries',        span: 1, body: _openInquiriesBody(rawHubspot, miProducts) }),
    _briefCard({ title: 'Conversation starters', span: 2, body: starters }),
  ].join('');
}

function _statCard(value, label) {
  return `
    <div class="stat-card">
      <div class="stat-value">${value}</div>
      <div class="stat-label">${label}</div>
    </div>`;
}

function _formatCurrency(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 1_000)     return Math.round(n).toLocaleString();
  return Math.round(n).toString();
}

function _daysBetween(isoDate) {
  if (!isoDate) return null;
  const d = new Date(isoDate);
  const now = new Date();
  return Math.max(0, Math.floor((now - d) / (1000 * 60 * 60 * 24)));
}

function renderStatsStrip(stage1, raw) {
  const root = document.getElementById('stats-strip');
  if (!root) return;

  const oa = stage1?.order_aggregate || {};
  const summarizedThreads = (stage1?.thread_summaries || []).length;
  const news = (stage1?.filtered_news || []).length;
  const inquiredCount = (raw?.hubspot?.inquired_products || []).length;

  // Stage 1 caps thread summaries at 10. To know the true count, derive it
  // from raw HubSpot emails — if the underlying count exceeds what's shown,
  // append a "+" so the user knows there's more behind the cap.
  const emails = raw?.hubspot?.emails || [];
  const trueThreadCount = new Set(emails.map(e => e?.thread_id).filter(Boolean)).size;
  const threadDisplay = trueThreadCount > summarizedThreads
    ? `${summarizedThreads}+`
    : (summarizedThreads || '—');

  // Last activity = newer of last_order_date and most-recent thread date_end
  const threadEnds = (stage1?.thread_summaries || []).map(t => t.date_end).filter(Boolean);
  const lastThread = threadEnds.length ? threadEnds.sort().slice(-1)[0] : null;
  const lastOrder = oa.last_order_date || null;
  const lastActivityDate = [lastThread, lastOrder].filter(Boolean).sort().slice(-1)[0] || null;
  const daysSince = _daysBetween(lastActivityDate);

  root.innerHTML = [
    _statCard(oa.total_orders ?? '—',                                    'Total Orders'),
    _statCard(oa.total_value_ytd != null ? _formatCurrency(oa.total_value_ytd) : '—', 'Value YTD'),
    _statCard(daysSince != null ? `${daysSince}d` : '—',                 'Since Last Activity'),
    _statCard(threadDisplay,                                             'Email Threads'),
    _statCard(inquiredCount || '—',                                      'Inquired Products'),
    _statCard(news || '—',                                               'Recent News'),
  ].join('');
}

function _copyRaw(btn) {
  const pre = document.getElementById(btn.dataset.target);
  const text = pre ? pre.textContent : '';
  if (!text || text === '—') return;
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.textContent;
    btn.textContent = 'Copied!';
    btn.classList.add('ds-copy-ok');
    setTimeout(() => { btn.textContent = orig; btn.classList.remove('ds-copy-ok'); }, 1800);
  });
}

async function renderCustomerDetail() {
  const id = customerIdFromPath();
  if (!id) return;

  const customer = await api.customer(id);
  document.getElementById('company-name').textContent = customer.company_name;
  document.getElementById('meta').innerHTML = `
    <span class="meta-pill">${customer.industry}</span>
    <span class="meta-pill">${customer.geography}</span>
    <span class="meta-pill">${customer.segment}</span>`;

  // Detail-analysis link (replaces the old "Stage 1 output" CTA)
  const detailLink = document.getElementById('detail-link');
  if (detailLink) {
    detailLink.href = `/customers/${id}/stage1`;
    detailLink.target = '_blank';
    detailLink.rel = 'noopener';
  }

  const [brief, raw, stage1, miProducts] = await Promise.all([
    api.brief(id),
    api.raw(id),
    api.stage1(id),
    api.miProducts(),
  ]);

  renderStatsStrip(stage1, raw);
  document.getElementById('brief').innerHTML = renderBrief(brief, {
    miProducts,
    rawHubspot: raw.hubspot,
  });
  document.getElementById('raw-hubspot').textContent = JSON.stringify(raw.hubspot || {}, null, 2);
  document.getElementById('raw-elixir').textContent = JSON.stringify(raw.elixir || {}, null, 2);
  document.getElementById('raw-news').textContent = JSON.stringify(raw.news || {}, null, 2);

  document.getElementById('refresh').onclick = async () => {
    const btn = document.getElementById('refresh');
    btn.disabled = true;
    btn.textContent = 'Refreshing…';
    try {
      const fresh = await api.refresh(id);
      const [s1New, rawNew, miNew] = await Promise.all([
        api.stage1(id),
        api.raw(id),
        api.miProducts(),
      ]);
      document.getElementById('brief').innerHTML = renderBrief(fresh, {
        miProducts: miNew,
        rawHubspot: rawNew.hubspot,
      });
      renderStatsStrip(s1New, rawNew);
    } catch (e) {
      alert('Refresh failed: ' + e);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Refresh Brief';
    }
  };
}
