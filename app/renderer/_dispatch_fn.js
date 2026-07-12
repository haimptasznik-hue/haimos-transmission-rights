
// ── Digital Twin — BESS Dispatch Algorithm Overlay ───────────────────────────
function initDispatchAlgorithm() {
  const runBtn = document.getElementById('dispatch-run-btn');
  if (!runBtn) return;

  runBtn.addEventListener('click', runDispatch);

  async function runDispatch() {
    const region    = document.querySelector('.nem-region-btn.active')?.dataset.region || 'VIC1';
    const bessMw    = parseFloat(document.getElementById('dp-mw').value)       || 5;
    const bessMwh   = parseFloat(document.getElementById('dp-mwh').value)      || 10;
    const charge    = parseFloat(document.getElementById('dp-charge').value)   || 50;
    const discharge = parseFloat(document.getElementById('dp-discharge').value) || 100;
    const fcas      = document.getElementById('dp-fcas').checked;

    const badge = document.getElementById('dispatch-status');
    badge.textContent = 'Running...';
    badge.className = 'dispatch-status-badge running';
    runBtn.disabled = true;

    try {
      const params = new URLSearchParams({
        region, bess_mw: bessMw, bess_mwh: bessMwh,
        charge_thresh: charge, discharge_thresh: discharge,
        enable_fcas: fcas,
      });
      const res = await fetch('http://127.0.0.1:' + API_PORT + '/api/nem/dispatch?' + params);
      if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
      const data = await res.json();
      renderDispatchResult(data);
      badge.textContent = 'Done — ' + (data.intervals ? data.intervals.length : 0) + ' intervals';
      badge.className = 'dispatch-status-badge done';
    } catch (err) {
      badge.textContent = 'Error: ' + err.message;
      badge.className = 'dispatch-status-badge error';
    } finally {
      runBtn.disabled = false;
    }
  }

  function renderDispatchResult(data) {
    const s = data.summary || {};
    function fmt(v) { return v == null ? '—' : (typeof v === 'number' ? v.toLocaleString('en-AU', {maximumFractionDigits:0}) : v); }
    document.getElementById('dk-total').textContent = '$' + fmt(s.total_revenue_aud);
    document.getElementById('dk-arb').textContent   = '$' + fmt(s.arb_revenue_aud);
    document.getElementById('dk-fcas').textContent  = '$' + fmt(s.fcas_revenue_aud);
    document.getElementById('dk-dis').textContent   = fmt(s.intervals_dispatched);
    document.getElementById('dk-chg').textContent   = fmt(s.intervals_charged);
    document.getElementById('dk-soc').textContent   = s.peak_soc_pct != null ? s.peak_soc_pct + '%' : '—';
    document.getElementById('dispatch-kpi-row').classList.remove('hidden');
    document.getElementById('dispatch-chart-row').classList.remove('hidden');
    document.getElementById('dispatch-table-wrap').classList.remove('hidden');
    renderDispatchSOCChart(data.intervals || []);
    renderDispatchRevChart(data.intervals || []);
    renderDispatchTable(data.intervals || []);
  }

  function renderDispatchSOCChart(intervals) {
    var el = document.getElementById('dispatch-soc-chart');
    if (!el || !intervals.length) return;
    var W = el.parentElement.clientWidth || 520, H = 180;
    var pad = {t:14, r:16, b:36, l:44};
    var iW = W-pad.l-pad.r, iH = H-pad.t-pad.b;
    var socs = intervals.map(function(iv){ return iv.soc_pct || 0; });
    var maxSOC = Math.max.apply(null, socs.concat([100]));
    function xS(i){ return pad.l + (i/(intervals.length-1||1))*iW; }
    function yS(v){ return pad.t + (1-v/maxSOC)*iH; }
    var AC = {discharge:'#4ade80', charge:'#60a5fa', idle:'#4b5563'};
    var html = '<svg width="' + W + '" height="' + H + '" xmlns="http://www.w3.org/2000/svg">';
    [0,25,50,75,100].forEach(function(p) {
      var y = yS(p);
      html += '<line x1="' + pad.l + '" y1="' + y + '" x2="' + (W-pad.r) + '" y2="' + y + '" stroke="#2a2a2a" stroke-width="1"/>';
      html += '<text x="' + (pad.l-6) + '" y="' + (y+4) + '" text-anchor="end" font-size="9" fill="#666">' + p + '%</text>';
    });
    var bW = Math.max(1, iW/intervals.length-0.5);
    intervals.forEach(function(iv,i) {
      html += '<rect x="' + (xS(i)-bW/2) + '" y="' + (H-pad.b-8) + '" width="' + bW + '" height="8" fill="' + (AC[iv.action]||'#4b5563') + '" opacity="0.7"/>';
    });
    var pts = intervals.map(function(iv,i){ return xS(i) + ',' + yS(iv.soc_pct||0); }).join(' ');
    html += '<polyline points="' + pts + '" fill="none" stroke="#f59e0b" stroke-width="2"/>';
    var step = Math.max(1, Math.floor(intervals.length/8));
    intervals.forEach(function(iv,i) {
      if (i%step===0) {
        var t = iv.timestamp ? iv.timestamp.substring(11,16) : '';
        html += '<text x="' + xS(i) + '" y="' + (H-pad.b+12) + '" text-anchor="middle" font-size="9" fill="#666">' + t + '</text>';
      }
    });
    ['discharge','charge','idle'].forEach(function(a,j) {
      html += '<rect x="' + (pad.l+j*80) + '" y="2" width="10" height="8" fill="' + AC[a] + '"/>';
      html += '<text x="' + (pad.l+j*80+13) + '" y="10" font-size="9" fill="#aaa">' + a + '</text>';
    });
    html += '</svg>';
    el.outerHTML = html;
  }

  function renderDispatchRevChart(intervals) {
    var el = document.getElementById('dispatch-rev-chart');
    if (!el || !intervals.length) return;
    var W = el.parentElement.clientWidth || 520, H = 180;
    var pad = {t:14, r:16, b:36, l:54};
    var iW = W-pad.l-pad.r, iH = H-pad.t-pad.b;
    var revs = intervals.map(function(iv){ return iv.cumulative_revenue_aud || 0; });
    var minR = Math.min.apply(null, revs.concat([0]));
    var maxR = Math.max.apply(null, revs.concat([1]));
    var span = maxR-minR || 1;
    function xS(i){ return pad.l + (i/(intervals.length-1||1))*iW; }
    function yS(v){ return pad.t + (1-(v-minR)/span)*iH; }
    var html = '<svg width="' + W + '" height="' + H + '" xmlns="http://www.w3.org/2000/svg">';
    html += '<line x1="' + pad.l + '" y1="' + yS(0) + '" x2="' + (W-pad.r) + '" y2="' + yS(0) + '" stroke="#555" stroke-width="1" stroke-dasharray="4,3"/>';
    var area = 'M ' + xS(0) + ' ' + yS(0);
    intervals.forEach(function(iv,i){ area += ' L ' + xS(i) + ' ' + yS(iv.cumulative_revenue_aud||0); });
    area += ' L ' + xS(intervals.length-1) + ' ' + yS(0) + ' Z';
    html += '<path d="' + area + '" fill="#4ade80" opacity="0.15"/>';
    var pts = intervals.map(function(iv,i){ return xS(i) + ',' + yS(iv.cumulative_revenue_aud||0); }).join(' ');
    html += '<polyline points="' + pts + '" fill="none" stroke="#4ade80" stroke-width="2"/>';
    [minR, (minR+maxR)/2, maxR].forEach(function(v) {
      var y = yS(v);
      var lab = v >= 0 ? ('$' + Math.round(v)) : ('-$' + Math.round(Math.abs(v)));
      html += '<text x="' + (pad.l-6) + '" y="' + (y+4) + '" text-anchor="end" font-size="9" fill="#666">' + lab + '</text>';
    });
    var step = Math.max(1, Math.floor(intervals.length/8));
    intervals.forEach(function(iv,i) {
      if (i%step===0) {
        var t = iv.timestamp ? iv.timestamp.substring(11,16) : '';
        html += '<text x="' + xS(i) + '" y="' + (H-pad.b+12) + '" text-anchor="middle" font-size="9" fill="#666">' + t + '</text>';
      }
    });
    html += '</svg>';
    el.outerHTML = html;
  }

  function renderDispatchTable(intervals) {
    var tbody = document.getElementById('dispatch-table-body');
    if (!tbody) return;
    var AC = {discharge:'price-spike', charge:'price-neg', idle:''};
    tbody.innerHTML = intervals.slice(-96).reverse().map(function(iv) {
      var t   = iv.timestamp ? iv.timestamp.substring(11,16) : '—';
      var sp  = iv.spot_aud_per_mwh != null ? ('$' + iv.spot_aud_per_mwh.toFixed(0)) : '—';
      var mw  = iv.dispatch_mw != null ? ((iv.dispatch_mw > 0 ? '+' : '') + iv.dispatch_mw.toFixed(2)) : '—';
      var soc = iv.soc_pct != null ? (iv.soc_pct.toFixed(1) + '%') : '—';
      var rev = iv.interval_revenue_aud != null ? ('$' + iv.interval_revenue_aud.toFixed(2)) : '—';
      var cum = iv.cumulative_revenue_aud != null ? ('$' + iv.cumulative_revenue_aud.toFixed(0)) : '—';
      var action = iv.action || 'idle';
      return '<tr class="' + (AC[action]||'') + '">' +
        '<td>' + t + '</td><td>' + sp + '</td>' +
        '<td><span class="action-pill action-' + action + '">' + action + '</span></td>' +
        '<td>' + mw + '</td><td>' + soc + '</td><td>' + (iv.fcas_service||'—') + '</td>' +
        '<td>' + rev + '</td><td>' + cum + '</td></tr>';
    }).join('');
  }
}
