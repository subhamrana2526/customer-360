const ARROW = { up: '↑', down: '↓', flat: '→' };

function fmtPct(x) {
  const v = (x * 100);
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}%`;
}

function signalCard(sig) {
  const dir = sig.direction || 'flat';
  const top = (sig.top_drivers && sig.top_drivers[0]) || null;
  const topLine = top
    ? `${top.factor_name} ${fmtPct(top.pct_change)}`
    : 'No driver data';
  return `
    <a class="mi-card mi-card-${dir}" href="/mi/products/${sig.product_id}">
      <div class="mi-card-header">
        <h3>${sig.product_name}</h3>
        <span class="mi-arrow">${ARROW[dir]}</span>
      </div>
      <div class="mi-pct">${fmtPct(sig.pct_change)}</div>
      <div class="mi-window">over ${sig.window_days}d</div>
      <div class="mi-driver">Top driver: <strong>${topLine}</strong></div>
      <div class="mi-summary">${sig.summary_line || ''}</div>
    </a>
  `;
}

async function renderMIDashboard() {
  const root = document.getElementById('mi-dashboard');
  const btn = document.getElementById('mi-refresh');
  const load = async (url, opts) => fetch(url, opts).then(r => r.json());

  const draw = (signals) => {
    if (!signals.length) {
      root.innerHTML = '<p class="empty">No products configured.</p>';
      return;
    }
    root.innerHTML = signals.map(signalCard).join('');
  };

  try {
    draw(await load('/api/mi/products'));
  } catch (e) {
    root.innerHTML = `<p class="empty">Failed to load: ${e.message}</p>`;
  }

  btn?.addEventListener('click', async () => {
    btn.disabled = true;
    btn.textContent = 'Refreshing…';
    try {
      const res = await load('/api/mi/refresh', { method: 'POST' });
      draw(res.signals || []);
    } catch (e) {
      alert('Refresh failed: ' + e.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Refresh signals';
    }
  });
}

async function renderMIProductDetail() {
  const id = location.pathname.split('/').pop();
  const nameEl = document.getElementById('product-name');
  const metaEl = document.getElementById('product-meta');
  const sigEl = document.getElementById('signal-card');
  const recipeBody = document.getElementById('recipe-body');
  const chartsEl = document.getElementById('factor-charts');

  try {
    const [product, factors] = await Promise.all([
      fetch(`/api/mi/products/${id}`).then(r => r.json()),
      fetch(`/api/mi/products/${id}/factors`).then(r => r.json()),
    ]);

    nameEl.textContent = product.name;
    metaEl.textContent = product.description || '';

    const sig = product.signal || {};
    const dir = sig.direction || 'flat';
    sigEl.classList.remove('empty');
    sigEl.classList.add(`signal-${dir}`);
    sigEl.innerHTML = `
      <div class="signal-main">
        <span class="signal-arrow">${ARROW[dir]}</span>
        <span class="signal-pct">${fmtPct(sig.pct_change || 0)}</span>
        <span class="signal-window">over ${sig.window_days || 30}d</span>
      </div>
      <p class="signal-line">${sig.summary_line || ''}</p>
    `;

    recipeBody.innerHTML = (product.recipe || []).map(r => `
      <tr>
        <td><strong>${r.factor_name}</strong></td>
        <td><span class="cat-badge cat-${r.category || 'na'}">${r.category || '—'}</span></td>
        <td>${r.weight_pct}%</td>
        <td class="muted">${r.notes || ''}</td>
      </tr>
    `).join('');

    chartsEl.innerHTML = (factors.factors || []).map(f => `
      <div class="factor-chart">
        <div class="factor-chart-header">
          <strong>${f.factor_name}</strong>
          <span class="muted">${f.unit || ''} · ${f.weight_pct}% weight</span>
        </div>
        <canvas id="chart-${f.factor_id}" height="120"></canvas>
      </div>
    `).join('');

    (factors.factors || []).forEach(f => {
      const ctx = document.getElementById(`chart-${f.factor_id}`);
      if (!ctx || !f.series.length) return;
      new Chart(ctx, {
        type: 'line',
        data: {
          labels: f.series.map(p => p.date),
          datasets: [{
            data: f.series.map(p => p.price),
            borderColor: '#ef4136',
            backgroundColor: 'rgba(239,65,54,0.08)',
            fill: true,
            tension: 0.25,
            pointRadius: 0,
            borderWidth: 2,
          }]
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              display: true,
              ticks: {
                font: { size: 10 },
                color: '#888',
                maxTicksLimit: 6,
                callback: function(val) {
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
    });
  } catch (e) {
    nameEl.textContent = id;
    sigEl.innerHTML = `<p class="empty">Failed to load: ${e.message}</p>`;
  }
}
