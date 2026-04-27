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

function renderBrief(brief) {
  if (!brief) return '<p>No brief yet. Click <strong>Refresh Brief</strong>.</p>';
  const angles = (brief.pitch_angles || [])
    .map(p => `<li><strong>${p.product_name}</strong>: ${p.rationale}</li>`)
    .join('');
  const starters = (brief.conversation_starters || [])
    .map(s => `<li>${s}</li>`)
    .join('');
  return `
    <h2>Conversation recap</h2><p>${brief.conversation_recap}</p>
    <h2>Customer snapshot</h2><p>${brief.customer_snapshot}</p>
    <h2>What's new</h2><p>${brief.whats_new}</p>
    <h2>Market context</h2><p>${brief.market_context}</p>
    <h2>Pitch angles</h2><ul>${angles}</ul>
    <h2>Conversation starters</h2><ul>${starters}</ul>
  `;
}

async function renderCustomerDetail() {
  const id = customerIdFromPath();
  if (!id) return;

  const customer = await api.customer(id);
  document.getElementById('company-name').textContent = customer.company_name;
  document.getElementById('meta').textContent =
    `${customer.industry} · ${customer.geography} · ${customer.segment}`;

  const brief = await api.brief(id);
  document.getElementById('brief').innerHTML = renderBrief(brief);

  const raw = await api.raw(id);
  document.getElementById('raw-hubspot').textContent = JSON.stringify(raw.hubspot || {}, null, 2);
  document.getElementById('raw-elixir').textContent = JSON.stringify(raw.elixir || {}, null, 2);
  document.getElementById('raw-news').textContent = JSON.stringify(raw.news || {}, null, 2);

  const s1 = await api.stage1(id);
  document.getElementById('stage1').textContent = JSON.stringify(s1 || {}, null, 2);
  const link = document.getElementById('stage1-detail-link');
  if (link) link.href = `/customers/${id}/stage1`;

  document.getElementById('refresh').onclick = async () => {
    const btn = document.getElementById('refresh');
    btn.disabled = true;
    btn.textContent = 'Refreshing…';
    try {
      const fresh = await api.refresh(id);
      document.getElementById('brief').innerHTML = renderBrief(fresh);
    } catch (e) {
      alert('Refresh failed: ' + e);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Refresh Brief';
    }
  };
}
