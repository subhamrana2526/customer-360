const api = {
  customers: () => fetch('/api/customers').then(r => r.json()),
  customer: id => fetch(`/api/customers/${id}`).then(r => r.json()),
  brief: id => fetch(`/api/customers/${id}/brief`).then(r => r.ok ? r.json() : null),
  raw: id => fetch(`/api/customers/${id}/raw`).then(r => r.ok ? r.json() : {}),
  stage1: id => fetch(`/api/customers/${id}/stage1`).then(r => r.ok ? r.json() : null),
  refresh: id => fetch(`/api/customers/${id}/refresh`, { method: 'POST' }).then(r => r.json()),
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
  `).join('') || '<p>No customers seeded. Edit data/customers.json.</p>';
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
