function customerIdFromPath() {
  const m = window.location.pathname.match(/\/customers\/([^/]+)\/stage1/);
  return m ? m[1] : null;
}

function fmtNum(n) {
  if (n == null) return '—';
  return Number(n).toLocaleString();
}

function sentimentBadge(s) {
  const map = {
    positive: ['#22c55e', '✓ Positive'],
    neutral:  ['#94a3b8', '– Neutral'],
    cooling:  ['#f59e0b', '↓ Cooling'],
    cold:     ['#ef4444', '✗ Cold'],
  };
  const [color, label] = map[s] || ['#94a3b8', s || 'unknown'];
  return `<span class="sentiment-badge" style="background:${color}">${label}</span>`;
}

function renderOrders(agg) {
  if (!agg) return '<p class="empty-state">No order data.</p>';

  const stats = `
    <div class="s1-stats-row">
      <div class="s1-stat"><div class="s1-stat-val">${agg.total_orders ?? '—'}</div><div class="s1-stat-label">Total Orders</div></div>
      <div class="s1-stat"><div class="s1-stat-val">${fmtNum(agg.total_value_ytd)}</div><div class="s1-stat-label">Value YTD</div></div>
      <div class="s1-stat"><div class="s1-stat-val">${agg.days_since_last_order != null ? agg.days_since_last_order + 'd' : '—'}</div><div class="s1-stat-label">Since Last Order</div></div>
      <div class="s1-stat"><div class="s1-stat-val">${agg.inquiry_count ?? 0}</div><div class="s1-stat-label">Inquiries</div></div>
    </div>`;

  const rows = (agg.top_products || []).map(p => `
    <tr>
      <td><strong>${p.name}</strong></td>
      <td>${fmtNum(p.qty)}</td>
      <td>${fmtNum(p.value)}</td>
      <td>${p.last_ordered || '—'}</td>
    </tr>`).join('');
  const table = rows ? `
    <table class="s1-table">
      <thead><tr><th>Product</th><th>Qty</th><th>Value</th><th>Last Ordered</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>` : '<p class="empty-state">No products on file.</p>';

  const gaps = agg.products_inquired_not_ordered || [];
  const gapsHtml = gaps.length
    ? `<div class="s1-gaps-row">
        <span class="s1-gaps-label">Inquired but not ordered:</span>
        ${gaps.map(g => `<span class="gap-tag">${g}</span>`).join('')}
      </div>`
    : '';

  return stats + table + gapsHtml;
}

function renderThreads(threads) {
  if (!threads || !threads.length) return '<p class="empty-state">No email threads in the period.</p>';
  return threads.map(t => `
    <div class="s1-thread">
      <div class="s1-thread-header">
        <span class="s1-thread-dates">${t.date_start} → ${t.date_end}</span>
        ${sentimentBadge(t.sentiment)}
      </div>
      <p class="s1-thread-summary">${t.summary || ''}</p>
      ${(t.key_products_discussed || []).length ? `
        <div class="s1-thread-products">
          ${t.key_products_discussed.map(p => `<span class="product-tag">${p}</span>`).join('')}
        </div>` : ''}
      ${(t.open_items || []).length ? `
        <div class="s1-open-items">
          <span class="s1-open-label">Open items</span>
          <ul>${t.open_items.map(i => `<li>${i}</li>`).join('')}</ul>
        </div>` : ''}
      ${(t.participants || []).length ? `
        <div class="s1-thread-participants">${t.participants.join(', ')}</div>` : ''}
    </div>`).join('');
}

function renderNews(news) {
  if (!news || !news.length) return '<p class="empty-state">No news items passed the relevance filter.</p>';
  return news.map(n => `
    <div class="s1-news-item">
      <div class="s1-news-header">
        <span class="news-cat news-cat-${n.category}">${n.category}</span>
        <span class="s1-news-date">${n.date}</span>
        ${n.source ? `<span class="s1-news-source">${n.source}</span>` : ''}
      </div>
      <p class="s1-news-title">${n.url ? `<a href="${n.url}" target="_blank">${n.title}</a>` : n.title}</p>
      ${n.why_it_matters ? `<p class="s1-news-why">${n.why_it_matters}</p>` : ''}
    </div>`).join('');
}

async function renderStage1Page() {
  const id = customerIdFromPath();
  if (!id) return;
  document.getElementById('back-link').href = `/customers/${id}`;

  const [customerResp, s1Resp] = await Promise.all([
    fetch(`/api/customers/${id}`),
    fetch(`/api/customers/${id}/stage1`),
  ]);

  if (customerResp.ok) {
    const customer = await customerResp.json();
    document.getElementById('company-name').textContent = customer.company_name;
  }

  if (!s1Resp.ok) {
    document.getElementById('orders-content').innerHTML = '<p class="empty-state">Stage 1 not generated yet.</p>';
    document.getElementById('threads-content').innerHTML = '';
    document.getElementById('news-content').innerHTML = '';
    return;
  }
  const s1 = await s1Resp.json();

  if (s1.generated_at) {
    document.getElementById('generated-at').textContent = `Generated ${new Date(s1.generated_at).toLocaleString()}`;
  }
  document.getElementById('orders-content').innerHTML = renderOrders(s1.order_aggregate);
  document.getElementById('threads-content').innerHTML = renderThreads(s1.thread_summaries);
  document.getElementById('news-content').innerHTML = renderNews(s1.filtered_news);
}
