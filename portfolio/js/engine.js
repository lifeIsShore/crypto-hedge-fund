// ── ENGINE.JS — shared data layer ────────────────────
// All pages read window.engineData. Only this file writes it.

window.engineData = null;

// ── LOAD DATA ─────────────────────────────────────────
async function loadData() {
  try {
    const r = await fetch('data/engine_state.json?' + Date.now());
    if (!r.ok) throw new Error('engine_state.json not found');
    return await r.json();
  } catch (e) {
    showGlobalMsg('error', '⚠ ' + e.message + ' — run engine first');
    return null;
  }
}

// ── RENDER DASHBOARD (called on boot + auto-refresh) ──
async function renderDashboard() {
  const data = await loadData();
  if (!data) return;
  window.engineData = data;
  window._lastEngineRun = data.last_run;
  updateFooter(data);
  if (typeof window._pageInit === 'function') window._pageInit(data);
}

// ── CLOCK ─────────────────────────────────────────────
function tickClock() {
  const el = document.getElementById('timestamp');
  if (el) el.textContent = new Date().toLocaleTimeString('de-DE', { hour12: false });
}

// ── KPIs ──────────────────────────────────────────────
function renderKPIs(d) {
  const kpis = d.kpis || {};
  const val  = d.current_values || {};
  const total  = kpis.current_value || val.total_portfolio || 0;
  const netPnl = kpis.net_pnl || 0;
  const sharpe = kpis.sharpe_ratio || 0;
  const maxDD  = kpis.max_drawdown || 0;
  const info   = kpis.information_ratio || 0;

  const pnlColor = netPnl >= 0 ? 'c-green' : 'c-red';
  const shColor  = sharpe >= 1.0 ? 'c-green' : sharpe >= 0.5 ? 'c-amber' : 'c-red';
  const ddColor  = Math.abs(maxDD) < 0.15 ? 'c-green' : Math.abs(maxDD) < 0.30 ? 'c-amber' : 'c-red';
  const irColor  = info >= 0.2 ? 'c-green' : info >= 0 ? 'c-amber' : 'c-red';

  function kpiHtml(label, value, sub, badge, colorClass) {
    return `<div class="kpi ${colorClass}">
      <div class="kpi-label">${label}</div>
      <div class="kpi-value">${value}</div>
      <div class="kpi-sub">${sub}</div>
      <div class="kpi-badge">${badge}</div>
    </div>`;
  }

  const strip = document.getElementById('kpiStrip');
  if (!strip) return;
  strip.innerHTML =
    kpiHtml('TOTAL VALUE',  '€' + total.toFixed(2),  'Portfolio today', 'LIVE', 'c-blue') +
    kpiHtml('NET P&L',      (netPnl >= 0 ? '+' : '') + '€' + netPnl.toFixed(2), 'After fees', netPnl >= 0 ? 'POSITIVE' : 'NEGATIVE', pnlColor) +
    kpiHtml('SHARPE RATIO', sharpe.toFixed(2), 'Risk-adj. return', sharpe >= 1 ? 'EXCELLENT' : sharpe >= 0.5 ? 'WARMING' : 'LOW', shColor) +
    kpiHtml('MAX DRAWDOWN', (maxDD * 100).toFixed(1) + '%', 'Worst peak-trough', Math.abs(maxDD) < 0.15 ? 'MINIMAL' : Math.abs(maxDD) < 0.30 ? 'NOTABLE' : 'HIGH', ddColor) +
    kpiHtml('INFO RATIO',   info.toFixed(2), 'vs MSCI World', info >= 0.2 ? 'BEATING INDEX' : info >= 0 ? 'BUILDING' : 'LAGGING', irColor);
}

// ── SIGNAL ────────────────────────────────────────────
function renderSignal(d) {
  const signal = d.action_signal || '';
  const box    = document.getElementById('signalBox');
  if (!box) return;
  box.style.setProperty('--signal-color', signal.includes('✅') ? 'var(--accent)' : 'var(--amber)');
  document.getElementById('signalText').textContent = signal;
  const reasons = d.reasons || [];
  document.getElementById('signalReasons').innerHTML = reasons.length
    ? reasons.map(r => `<div class="signal-reason">· ${r}</div>`).join('') : '';
}

// ── HOLDINGS ──────────────────────────────────────────
const ASSET_COLORS = {
  'BTC/EUR':'#f7931a', 'ETH/EUR':'#627eea', 'SOL/EUR':'#14f195',
  'BNB/EUR':'#f3ba2f', 'XRP/EUR':'#23292f', 'DOGE/EUR':'#c2a633', 'ADA/EUR':'#0033ad',
  'TRX/EUR':'#ff0013', 'LINK/EUR':'#2a5ada', 'DOT/EUR':'#e6007a'
};

function renderHoldings(d) {
  const val      = d.current_values || {};
  const weights  = d.current_weights || {};
  const holdings = val.holdings || {};

  function rows(tbodyId, cashId) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    if (!Object.keys(holdings).length) {
      tbody.innerHTML = '<tr><td colspan="4" style="color:var(--muted)">No holdings yet</td></tr>';
    } else {
      tbody.innerHTML = Object.entries(holdings).map(([t, v]) => {
        const w    = ((weights[t] || 0) * 100).toFixed(1);
        const col  = ASSET_COLORS[t] || 'var(--text)';
        const diff = (weights[t] || 0) - (1 / Object.keys(holdings).length);
        const badge = diff > 0.05 ? '<span class="tag tag-amber">OVER</span>'
                    : diff < -0.05 ? '<span class="tag tag-red">UNDER</span>'
                    : '<span class="tag tag-green">OK</span>';
        return `<tr>
          <td style="color:${col};font-weight:500">${t}</td>
          <td>€${parseFloat(v).toFixed(2)}</td>
          <td>${w}%</td>
          <td>${badge}</td>
        </tr>`;
      }).join('');
    }
    const cashEl = document.getElementById(cashId);
    if (cashEl) cashEl.textContent = (val.cash || 0).toFixed(2);
  }

  rows('holdingsBody',  'cashValue');
  rows('holdingsBody2', 'cashValue2');

  const n = Object.keys(holdings).length;
  const nrt = document.getElementById('nextRebalTag');
  if (nrt) nrt.textContent = 'REBALANCE ' + (d.next_rebalance || '—');
  const ht = document.getElementById('holdingsTag');
  if (ht)  ht.textContent  = n + ' POSITIONS';
  const fa = document.getElementById('ftAssets');
  if (fa)  fa.textContent  = n + ' HELD';
}

// ── PRICES ────────────────────────────────────────────
function renderPrices(d) {
  const prices  = d.latest_prices || {};
  const updated = d.last_run || '—';
  function rows(tbodyId) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    tbody.innerHTML = Object.keys(prices).length
      ? Object.entries(prices).map(([t, p]) =>
          `<tr><td>${t}</td><td>€${parseFloat(p).toFixed(2)}</td><td style="color:var(--muted)">${updated}</td></tr>`
        ).join('')
      : '<tr><td colspan="3" style="color:var(--muted)">No data</td></tr>';
  }
  rows('pricesBody');
  rows('pricesBody2');
}

// ── WEIGHTS CHART ─────────────────────────────────────
let _weightsChart = null;
function renderWeightsChart(d) {
  const ctx = document.getElementById('weightsChart');
  if (!ctx) return;
  const cur    = d.current_weights || {};
  const opt    = d.optimal_weights || {};
  const labels = [...new Set([...Object.keys(cur), ...Object.keys(opt)])].filter(t => t !== 'CASH');
  if (_weightsChart) _weightsChart.destroy();
  _weightsChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Current', data: labels.map(t => ((cur[t] || 0) * 100).toFixed(1)), backgroundColor: 'rgba(74,158,255,0.65)', borderWidth: 0 },
        { label: 'Optimal', data: labels.map(t => ((opt[t] || 0) * 100).toFixed(1)), backgroundColor: 'rgba(0,229,160,0.5)',   borderWidth: 0 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: true, position: 'top', labels: { boxWidth: 10, padding: 10 } } },
      scales: { x: { grid: { display: false } }, y: { ticks: { callback: v => v + '%' } } }
    }
  });
}

// ── ANALYTICS ─────────────────────────────────────────
function renderAnalytics(d) {
  const k        = d.kpis || {};
  const v        = d.current_values || {};
  const total    = k.current_value  || v.total_portfolio || 0;
  const invested = k.initial_investment || 0;
  const grossPnl = k.gross_pnl || 0;
  const fees     = k.total_fees || 0;
  const netPnl   = k.net_pnl || 0;
  const retNet   = invested > 0 ? (netPnl / invested * 100) : 0;
  const col      = x => x >= 0 ? 'var(--accent)' : 'var(--red)';

  function set(id, text, color) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text;
    if (color) el.style.color = color;
  }

  set('s-sharpe',    (k.sharpe_ratio   || 0).toFixed(2));
  set('s-calmar',    (k.calmar_ratio   || 0).toFixed(2));
  set('s-maxdd',     ((k.max_drawdown  || 0) * 100).toFixed(2) + '%');
  set('s-info',      (k.information_ratio || 0).toFixed(2));
  set('s-profit',    (k.profit_factor  || 0).toFixed(2));
  set('s-return',    (k.real_return_pct || 0).toFixed(2) + '% (real)');
  set('s-current',   '€' + total.toFixed(2));
  set('s-invested',  '€' + invested.toFixed(2));
  set('s-grosspnl',  (grossPnl >= 0 ? '+' : '') + '€' + grossPnl.toFixed(2), col(grossPnl));
  set('s-fees',      '€' + fees.toFixed(2));
  set('s-netpnl',    (netPnl  >= 0 ? '+' : '') + '€' + netPnl.toFixed(2),   col(netPnl));
  set('s-returnnet', (retNet  >= 0 ? '+' : '') + retNet.toFixed(2) + '%',    col(retNet));

  const sr = document.getElementById('s-return');
  if (sr) sr.dataset.backtest = (k.portfolio_return_pct || 0).toFixed(2) + '%';
}

// ── WEIGHTS TABLE ─────────────────────────────────────
function renderWeightsTable(d) {
  const tbody = document.getElementById('weightsBody');
  if (!tbody) return;
  const cur = d.current_weights || {};
  const opt = d.optimal_weights || {};
  const labels = [...new Set([...Object.keys(cur), ...Object.keys(opt)])].filter(t => t !== 'CASH');
  tbody.innerHTML = labels.map(t => {
    const cw = (cur[t] || 0) * 100;
    const ow = (opt[t] || 0) * 100;
    const drift = cw - ow;
    const driftStr = (drift >= 0 ? '+' : '') + drift.toFixed(1) + '%';
    const dColor = Math.abs(drift) > 7 ? 'var(--red)' : Math.abs(drift) > 5 ? 'var(--amber)' : 'var(--accent)';
    const action = ow === 0 && cw > 0  ? '<span class="tag tag-amber">HOLD / SELL</span>'
                 : ow > 0  && cw === 0 ? '<span class="tag tag-green">BUY</span>'
                 : Math.abs(drift) > 7 ? '<span class="tag tag-red">REBALANCE</span>'
                 : '<span class="tag tag-muted">WITHIN BOUNDS</span>';
    return `<tr>
      <td>${t}</td>
      <td>${cw.toFixed(1)}%</td>
      <td>${ow.toFixed(1)}%</td>
      <td style="color:${dColor}">${driftStr}</td>
      <td>${action}</td>
    </tr>`;
  }).join('');
}

// ── FOOTER ────────────────────────────────────────────
function updateFooter(d) {
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  set('ftEngine',    d.last_run || '—');
  set('ftRebalance', d.next_rebalance || '—');
  set('ftFxRate',    d.fx_rate_usd_eur ? d.fx_rate_usd_eur.toFixed(4) : '—');
}

// ── REFRESH ENGINE ────────────────────────────────────
async function refreshData() {
  const btn = document.getElementById('refreshBtn');
  if (btn) { btn.disabled = true; btn.textContent = '⟳ CALCULATING...'; }
  try {
    const r = await fetch('api/refresh_engine', { method: 'POST' });
    const data = await r.json();
    if (r.ok) {
      await new Promise(res => setTimeout(res, 800));
      await renderDashboard();
      showGlobalMsg('success', '✓ Engine recalculated — all metrics updated');
    } else {
      showGlobalMsg('error', '⚠ ' + (data.error || 'Refresh failed'));
    }
  } catch (err) {
    showGlobalMsg('error', '⚠ ' + err.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '⟳ REFRESH'; }
  }
}

// ── MESSAGE HELPERS ───────────────────────────────────
function showGlobalMsg(type, text) {
  const el = document.getElementById('msgGlobal');
  if (!el) return;
  el.innerHTML = `<div class="msg msg-${type}" style="margin:8px 0 0">${text}</div>`;
  setTimeout(() => el.innerHTML = '', 5000);
}

function showTradeMsg(type, text) {
  const el = document.getElementById('msgTrade');
  if (!el) return;
  el.innerHTML = `<div class="msg msg-${type}">${text}</div>`;
  setTimeout(() => el.innerHTML = '', 5000);
}

// ── METRIC MODAL DEFINITIONS ──────────────────────────
window.METRICS = {
  sharpe:    { title:'Sharpe Ratio',             formula:'(Annualised Return − Risk-Free Rate)\n÷ Annualised Volatility\n\nRF Rate: 2.0% p.a.\nAnnualisation: √252',   meaning:'How much return you earn per unit of total risk.',                                              importance:'Separates skill from luck.',           target:'> 1.0 Good · > 2.0 Excellent' },
  calmar:    { title:'Calmar Ratio',              formula:'Annualised Return\n÷ |Maximum Drawdown|',                                                                      meaning:'Return earned per 1% of maximum loss endured.',                                                importance:'Critical for psychological resilience.', target:'> 0.5 Acceptable · > 1.0 Strong' },
  maxdd:     { title:'Maximum Drawdown',          formula:'(Trough Value − Peak Value)\n÷ Peak Value × 100',                                                              meaning:'Largest % drop from an all-time high before recovering.',                                       importance:'Most psychologically important metric.', target:'< −15% Acceptable · < −10% Excellent' },
  info:      { title:'Information Ratio',         formula:'(Portfolio Return − Benchmark Return)\n÷ Tracking Error\n\nBenchmark: Bitcoin (BTC/EUR)',                   meaning:'Whether active rebalancing beats a passive index hold.',                                        importance:'Answers: "Am I better than just buying BTC/EUR?"', target:'> 0.2 Beating benchmark · > 0.5 Strong alpha' },
  profit:    { title:'Profit Factor',             formula:'Σ Winning Trades\n÷ |Σ Losing Trades|',                                                                       meaning:'Euros made per euro lost on closed trades.',                                                    importance:'Simple edge measurement.',             target:'> 1.5 Winning edge · > 2.0 Professional' },
  return:    { title:'Portfolio Return % (Real)', formula:'Net P&L / Total Deposited × 100\n\nBased on actual ledger cash flows',                                        meaning:'Your honest % gain or loss on capital deposited, after all fees.',                              importance:'This is your true return.',            target:'> 5% annually · > 10% Strong' },
  current:   { title:'Current Value',             formula:'Cash + Σ (Shares × Current Price)',                                                                            meaning:'Total market value of your portfolio right now.',                                               importance:'Your actual wealth number.',           target:'Track month-on-month growth.' },
  invested:  { title:'Total Invested',            formula:'Σ Deposits + Σ Purchase Totals',                                                                               meaning:'All cash you have ever put into the portfolio.',                                                importance:'Cost basis for all P&L calculations.', target:'Growing over time.' },
  grosspnl:  { title:'Gross P&L',                 formula:'(Current Value + Total Fees) − Total Invested',                                                                meaning:'Pure trading profit before any broker fees.',                                                   importance:'Separates trading skill from fee drag.', target:'> €0 profitable trades' },
  fees:      { title:'Total Fees Paid',           formula:'Σ All Fee Ledger Entries',                                                                                     meaning:'Total broker fees paid since account opened.',                                                  importance:'Hidden wealth erosion.',               target:'< 0.5% of portfolio annually' },
  netpnl:    { title:'Net P&L',                   formula:'Current Value − Total Invested',                                                                               meaning:'True profit/loss after all fees.',                                                              importance:'The only number that matters.',        target:'> €0 and growing' },
  returnnet: { title:'Return % (Net)',             formula:'(Net P&L / Total Invested) × 100',                                                                            meaning:'True percentage return after fees.',                                                            importance:'Reality check on gross return.',       target:'> 5% annually above savings rate' }
};

function showModal(key) {
  const def = window.METRICS[key];
  if (!def) return;
  const valMap = { sharpe:'s-sharpe', calmar:'s-calmar', maxdd:'s-maxdd', info:'s-info', profit:'s-profit', return:'s-return', current:'s-current', invested:'s-invested', grosspnl:'s-grosspnl', fees:'s-fees', netpnl:'s-netpnl', returnnet:'s-returnnet' };
  const valEl = document.getElementById(valMap[key]);
  document.getElementById('modalTitle').textContent      = def.title;
  document.getElementById('modalValue').textContent      = valEl ? valEl.textContent : '—';
  document.getElementById('modalFormula').textContent    = def.formula;
  document.getElementById('modalMeaning').textContent    = def.meaning;
  document.getElementById('modalImportance').textContent = def.importance;
  document.getElementById('modalTarget').textContent     = def.target;
  document.getElementById('metricModal').classList.add('active');
}

function closeMetricInfo() { document.getElementById('metricModal').classList.remove('active'); }
function closeModal(e)      { if (e.target === document.getElementById('metricModal')) closeMetricInfo(); }
