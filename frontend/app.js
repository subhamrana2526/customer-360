const api = {
  customers: () => fetch('/api/customers').then(r => r.json()),
  customer: id => fetch(`/api/customers/${id}`).then(r => r.json()),
  brief: id => fetch(`/api/customers/${id}/brief`).then(r => r.ok ? r.json() : null),
  raw: id => fetch(`/api/customers/${id}/raw`).then(r => r.ok ? r.json() : {}),
  stage1: id => fetch(`/api/customers/${id}/stage1`).then(r => r.ok ? r.json() : null),
  refresh: id => fetch(`/api/customers/${id}/refresh`, { method: 'POST' }).then(r => r.json()),
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

function renderBrief(brief) {
  if (!brief) {
    return '<div class="brief-empty">No brief yet. Click <strong>Refresh Brief</strong> to generate.</div>';
  }

  const angles = (brief.pitch_angles || []).length
    ? `<ul class="pitch-list">${brief.pitch_angles.map(p => `
        <li>
          <div class="pitch-product">${p.product_name}</div>
          <div class="pitch-rationale">${p.rationale}</div>
        </li>`).join('')}</ul>`
    : '<p class="brief-empty-text">No pitch angles surfaced.</p>';

  const starters = (brief.conversation_starters || []).length
    ? `<ul class="starter-list">${brief.conversation_starters.map(s => `<li>${s}</li>`).join('')}</ul>`
    : '<p class="brief-empty-text">No conversation starters yet.</p>';

  return [
    _briefCard({ title: 'Conversation recap',    span: 2, body: `<p>${brief.conversation_recap || '—'}</p>` }),
    _briefCard({ title: 'Customer snapshot',     span: 1, body: `<p>${brief.customer_snapshot || '—'}</p>` }),
    _briefCard({ title: "What's new",            span: 1, body: `<p>${brief.whats_new || '—'}</p>` }),
    _briefCard({ title: 'Market context',        span: 2, body: `<p>${brief.market_context || '—'}</p>` }),
    _briefCard({ title: 'Pitch angles',          span: 2, body: angles }),
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
  const threads = (stage1?.thread_summaries || []).length;
  const news = (stage1?.filtered_news || []).length;
  const inquiredCount = (raw?.hubspot?.inquired_products || []).length;

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
    _statCard(threads || '—',                                            'Email Threads'),
    _statCard(inquiredCount || '—',                                      'Inquired Products'),
    _statCard(news || '—',                                               'Recent News'),
  ].join('');
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

  const [brief, raw, stage1] = await Promise.all([
    api.brief(id),
    api.raw(id),
    api.stage1(id),
  ]);

  renderStatsStrip(stage1, raw);
  document.getElementById('brief').innerHTML = renderBrief(brief);
  document.getElementById('raw-hubspot').textContent = JSON.stringify(raw.hubspot || {}, null, 2);
  document.getElementById('raw-elixir').textContent = JSON.stringify(raw.elixir || {}, null, 2);
  document.getElementById('raw-news').textContent = JSON.stringify(raw.news || {}, null, 2);

  document.getElementById('refresh').onclick = async () => {
    const btn = document.getElementById('refresh');
    btn.disabled = true;
    btn.textContent = 'Refreshing…';
    try {
      const fresh = await api.refresh(id);
      document.getElementById('brief').innerHTML = renderBrief(fresh);
      // Re-pull stage1 + raw to refresh stats
      const [s1New, rawNew] = await Promise.all([api.stage1(id), api.raw(id)]);
      renderStatsStrip(s1New, rawNew);
    } catch (e) {
      alert('Refresh failed: ' + e);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Refresh Brief';
    }
  };
}
