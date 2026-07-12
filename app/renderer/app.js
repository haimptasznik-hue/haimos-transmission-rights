/**
 * app.js — HaimOS renderer logic
 * Tab navigation, vault chat, agent runners, VS Code panel, quick capture.
 */

let API_PORT = 8765;
let _trRefreshTimer = null;

// ── Fetch API port from main process ─────────────────────────────────────────
async function initApiPort() {
  if (window.haimos?.getApiPort) {
    API_PORT = await window.haimos.getApiPort();
  }
}

// ── Tab navigation ────────────────────────────────────────────────────────────
function initTabs() {
  const btns = document.querySelectorAll('.nav-btn');
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.tab').forEach(t => {
        t.classList.remove('active');
        t.classList.add('hidden');
      });
      const panel = document.getElementById(`tab-${tab}`);
      if (panel) {
        panel.classList.remove('hidden');
        panel.classList.add('active');
      }
      if (tab === 'tr') {
        const projectsPanel = document.getElementById('tab-projects');
        if (projectsPanel) {
          projectsPanel.classList.remove('hidden');
          projectsPanel.classList.add('active');
        }
        openTransmissionRightsDashboard();
        return;
      }
      if (tab === 'graph') HaimGraph.load(API_PORT, currentFolder());
      if (tab === 'todos') initTodos();
      if (tab === 'nna') initNNAMap();
      if (tab === 'social') initSocial();
      if (tab === 'weekly') renderWeeklyReview();
    });
  });
}

function currentFolder() {
  return document.getElementById('graph-folder-filter')?.value || '';
}

// ── Vault stats ───────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const res  = await fetch(`http://127.0.0.1:${API_PORT}/api/vault/stats`);
    const data = await res.json();
    document.getElementById('stat-total').textContent   = (data.total || 0).toLocaleString();
    document.getElementById('stat-indexed').textContent = '26,642';
    document.getElementById('stat-backend').textContent = '●';
    document.getElementById('stat-backend').classList.remove('offline');

    const ul = document.getElementById('recent-list');
    if (!ul) return;
    ul.innerHTML = '';
    (data.recent || []).slice(0, 8).forEach(n => {
      const li = document.createElement('li');
      li.textContent = n.name;
      li.title       = n.path;
      li.addEventListener('click', () => window.haimos?.openInObsidian(n.path));
      ul.appendChild(li);
    });
  } catch {
    document.getElementById('stat-backend').textContent = '●';
    document.getElementById('stat-backend').classList.add('offline');
  }
}

// ── Vault Chat ────────────────────────────────────────────────────────────────
function initChat() {
  const input  = document.getElementById('chat-input');
  const btn    = document.getElementById('chat-send');
  const msgs   = document.getElementById('chat-messages');
  const srcs   = document.getElementById('chat-sources');

  if (!input || !btn) return;

  function addMsg(text, role) {
    const div = document.createElement('div');
    div.className = `msg ${role}`;
    div.textContent = text;
    if (!msgs) return div;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return div;
  }

  async function sendChat() {
    const query = input.value.trim();
    if (!query) return;
    input.value = '';
    btn.disabled = true;
    srcs.innerHTML = '';
    addMsg(query, 'user');
    const thinking = addMsg('Searching vault…', 'ai typing');

    try {
      const res  = await fetch(`http://127.0.0.1:${API_PORT}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      thinking.classList.remove('typing');
      thinking.textContent = data.answer || '(no response)';

      // Show source chips
      if (data.sources?.length) {
        data.sources.slice(0, 6).forEach(s => {
          if (!srcs) return;
          const chip = document.createElement('span');
          chip.className   = 'source-chip';
          chip.textContent = s.split('/').pop().replace('.md', '');
          chip.title       = s;
          chip.addEventListener('click', () => window.haimos?.openInObsidian(s));
          srcs.appendChild(chip);
        });
        // Fire neurons on graph
        HaimGraph.fireNodes(data.sources);
      }
    } catch (e) {
      thinking.textContent = `Error: ${e.message}`;
    } finally {
      btn.disabled = false;
      input.focus();
    }
  }

  btn.addEventListener('click', sendChat);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });

  // Welcome message
  addMsg('Hi Haim 👋  Ask me anything about your vault — deals, clients, emails, projects, EYE status, or anything else.', 'ai');
}

// ── Graph controls ────────────────────────────────────────────────────────────
function initGraphControls() {
  document.getElementById('graph-search')?.addEventListener('input', e => {
    HaimGraph.searchFocus(e.target.value);
  });
  document.getElementById('graph-folder-filter')?.addEventListener('change', () => {
    HaimGraph.load(API_PORT, currentFolder());
  });
  document.getElementById('graph-reload')?.addEventListener('click', () => {
    HaimGraph.load(API_PORT, currentFolder());
  });
}

// ── Agent buttons ─────────────────────────────────────────────────────────────
function initAgentButtons() {
  const log = document.getElementById('agent-log');
  document.querySelectorAll('.agent-run-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const script = btn.dataset.script;
      const args   = btn.dataset.args ? btn.dataset.args.split(' ').filter(Boolean) : [];
      btn.classList.add('running');
      btn.textContent = '⏳ ' + btn.textContent.replace('⏳ ', '');
      log.textContent += `\n▶ Running ${script}...\n`;

      try {
        const res  = await fetch(`http://127.0.0.1:${API_PORT}/api/agents/run`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ script, args }),
        });
        const data = await res.json();
        log.textContent += data.stdout || '';
        if (data.stderr) log.textContent += '\n[stderr] ' + data.stderr;
        log.textContent += `\n✓ Done (exit ${data.returncode})\n`;
      } catch (e) {
        log.textContent += `\n✗ Error: ${e.message}\n`;
      } finally {
        btn.classList.remove('running');
        btn.textContent = btn.textContent.replace('⏳ ', '');
        log.scrollTop = log.scrollHeight;
      }
    });
  });
}

// ── VS Code panel ─────────────────────────────────────────────────────────────
function initVSCode() {
  const statusEl    = document.getElementById('vscode-status');
  const webview     = document.getElementById('vscode-view');
  const placeholder = document.getElementById('vscode-placeholder');

  async function tryLoad() {
    try {
      const res  = await fetch(`http://127.0.0.1:${API_PORT}/api/vscode/url`);
      const data = await res.json();
      if (data.url) {
        placeholder.classList.add('hidden');
        webview.src = data.url;
        statusEl.textContent = '● Running';
        statusEl.style.color = '#3fb950';
      } else {
        statusEl.textContent = data.error || 'Unavailable';
      }
    } catch {
      statusEl.textContent = 'Starting…';
      setTimeout(tryLoad, 2000);
    }
  }

  // Poll until code-server is ready (it starts in background with the backend)
  tryLoad();
}

// ── VS Code 2 — second project ───────────────────────────────────────────────
function initVSCode2() {
  const statusEl  = document.getElementById('vscode2-status');
  const launcher  = document.getElementById('vscode2-launcher');
  const webview   = document.getElementById('vscode2-view');
  const folderIn  = document.getElementById('vscode2-folder-input');
  const launchBtn = document.getElementById('vscode2-launch-btn');
  const errEl     = document.getElementById('vscode2-launch-error');
  const presets   = document.getElementById('vscode2-presets');

  if (!statusEl || !launcher || !webview || !folderIn || !launchBtn || !errEl) return;

  // Preset quick-open folders
  const PRESET_FOLDERS = [
    { label: '⬡ HaimOS Vault',         path: '/Users/haimptasznik/Desktop/HaimOS' },
    { label: '🏗️ Orchestration Advisor', path: '/Users/haimptasznik/Desktop/HaimOS/haimos-app' },
    { label: '🗺️ NNA Map',              path: '/Users/haimptasznik/Desktop/SolarTool_2026-04-24_v1_Mark1' },
    { label: '☀️ SolarTool',            path: '/Users/haimptasznik/Desktop/SolarTool_2026-04-24_v1_Mark1' },
    { label: '🍇 Lanteri Project',      path: '/Users/haimptasznik/Desktop/HaimOS/02_Projects/Grants/Lanteri Grapes Farm' },
    { label: '📁 Desktop',             path: '/Users/haimptasznik/Desktop' },
  ];
  PRESET_FOLDERS.forEach(p => {
    const btn = document.createElement('button');
    btn.textContent = p.label;
    btn.style.cssText = 'background:#21262d;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:5px 10px;font-size:0.75rem;cursor:pointer;';
    btn.addEventListener('click', () => { folderIn.value = p.path; });
    if (presets) presets.appendChild(btn);
  });

  async function launch() {
    const folder = folderIn.value.trim();
    if (!folder) { errEl.textContent = 'Please enter a folder path.'; return; }
    errEl.textContent = '';
    statusEl.textContent = 'Starting…';
    statusEl.style.color = '#f0883e';
    launchBtn.disabled = true;

    try {
      const res  = await fetch(`http://127.0.0.1:${API_PORT}/api/vscode2/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder })
      });
      const data = await res.json();
      if (data.error) { errEl.textContent = data.error; statusEl.textContent = 'Error'; launchBtn.disabled = false; return; }

      // Poll until ready
      const url = data.url;
      let tries = 20;
      const poll = async () => {
        try {
          await fetch(url, { mode: 'no-cors' });
          launcher.style.display  = 'none';
          webview.style.display   = 'flex';
          webview.src = url;
          statusEl.textContent = `● Running — ${folder.split('/').pop()}`;
          statusEl.style.color = '#3fb950';
        } catch {
          if (--tries > 0) setTimeout(poll, 1000);
          else { statusEl.textContent = 'Timeout — retry'; launchBtn.disabled = false; }
        }
      };
      setTimeout(poll, 1500);
    } catch(e) {
      errEl.textContent = String(e);
      launchBtn.disabled = false;
    }
  }

  launchBtn.addEventListener('click', launch);
  folderIn.addEventListener('keydown', e => { if (e.key === 'Enter') launch(); });

  // If the tab is shown while webview is already loaded, keep it visible
  document.querySelector('[data-tab="vscode2"]')?.addEventListener('click', () => {
    if (webview.src !== 'about:blank') {
      launcher.style.display = 'none';
      webview.style.display  = 'flex';
    }
  });
}

// ── Quick Capture ─────────────────────────────────────────────────────────────
function initCapture() {
  const saveBtn    = document.getElementById('capture-save');
  const titleInput = document.getElementById('capture-title');
  const bodyInput  = document.getElementById('capture-body');
  const feedback   = document.getElementById('capture-feedback');

  if (!saveBtn || !titleInput || !bodyInput || !feedback) return;

  saveBtn.addEventListener('click', async () => {
    const title   = titleInput.value.trim();
    const content = bodyInput.value.trim();
    if (!title && !content) return;

    try {
      const result = await window.haimos.saveNote({ title: title || 'Quick Note', content });
      if (result.success) {
        feedback.textContent = `✓ Saved as ${result.filename}`;
        titleInput.value = '';
        bodyInput.value  = '';
        setTimeout(() => { feedback.textContent = ''; }, 3000);
      }
    } catch (e) {
      feedback.textContent = `✗ ${e.message}`;
    }
  });

  titleInput.addEventListener('keydown', e => {
    if (e.key === 'Tab') { e.preventDefault(); bodyInput.focus(); }
  });
}

// ── NEM Wholesale Market Dashboard — All Regions ────────────────────────────
let _nemDashboardInitialised = false;
let _nemCache = {};        // persists across Cmd+R reloads
let _nemRefreshTimer = null;
let _nemLoading = false;

function initNemDashboard() {
  // Guard: on Cmd+R, DOMContentLoaded fires again — skip re-registering listeners/timers
  const reinit = _nemDashboardInitialised;
  _nemDashboardInitialised = true;

  const NEM_REGIONS = [
    { code: 'VIC1', label: 'VIC' },
    { code: 'NSW1', label: 'NSW' },
    { code: 'QLD1', label: 'QLD' },
    { code: 'SA1',  label: 'SA'  },
    { code: 'TAS1', label: 'TAS' },
  ];
  const REFRESH_MS = 5 * 60 * 1000;
  // Use module-level vars so they survive Cmd+R page reloads
  const nemCache = _nemCache;

  const status     = document.getElementById('nem-status');
  const refreshBtn = document.getElementById('nem-refresh');
  const grid       = document.getElementById('nem-regions-grid');

  if (!grid) return;

  // Clear any previously appended cards (guard against double-init on Cmd+R)
  grid.innerHTML = '';

  // Build card skeleton for every region
  NEM_REGIONS.forEach(r => {
    const card = document.createElement('div');
    card.className = 'nem-region-card';
    card.id = `nem-card-${r.code}`;
    card.innerHTML = `
      <div class="nem-region-card-header">
        <span class="nem-region-name">${r.label}</span>
        <span class="nem-region-spot" id="nem-spot-${r.code}">—</span>
        <span class="nem-region-unit">$/MWh</span>
      </div>
      <div class="nem-region-kpis">
        <div class="nem-mini-kpi"><div class="nem-mini-label">Today Avg</div><div class="nem-mini-val" id="nem-avg-${r.code}">—</div></div>
        <div class="nem-mini-kpi"><div class="nem-mini-label">Today Peak</div><div class="nem-mini-val" id="nem-max-${r.code}">—</div></div>
        <div class="nem-mini-kpi"><div class="nem-mini-label">Neg Periods</div><div class="nem-mini-val" id="nem-neg-${r.code}">—</div></div>
        <div class="nem-mini-kpi"><div class="nem-mini-label">R6s FCAS</div><div class="nem-mini-val" id="nem-r6s-${r.code}">—</div></div>
      </div>
      <svg class="nem-sparkline" id="nem-chart-${r.code}"></svg>
      <div class="nem-region-ts" id="nem-ts-${r.code}">Loading…</div>
    `;
    if (grid) grid.appendChild(card);
  });

  function setStatus(text, cls) {
    if (status) { status.textContent = text; status.className = cls || ''; }
  }

  function fmtPrice(v) {
    if (v == null || isNaN(v)) return '—';
    return (v >= 0 ? '' : '-') + '$' + Math.abs(v).toLocaleString('en-AU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function fmtTime(ts) {
    return new Date(ts).toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit', hour12: false });
  }

  function priceColor(v) {
    if (v > 300) return '#ff4040';
    if (v > 100) return '#ff8c30';
    if (v < 0)   return '#00e5ff';
    return '#4caf50';
  }

  // ── Per-region sparkline ─────────────────────────────────────────────────
  // Fixed window: today's 00:00 → 24:00 in the same "naive local" basis
  // that new Date('2026-07-11T00:00:00') uses — so it matches AEMO timestamps.
  function getTodayWindowMs() {
    const now = new Date();
    // Midnight today in local time (same basis as naive ISO strings from backend)
    const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
    const tMin = midnight.getTime();
    const tMax = tMin + 24 * 3600000;
    return { tMin, tMax };
  }

  function drawSparkline(svgEl, history, forecast) {
    if (!svgEl) return;
    const W = svgEl.parentElement?.clientWidth || 280;
    const H = 130;
    svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svgEl.setAttribute('width', W);
    svgEl.setAttribute('height', H);
    svgEl.innerHTML = '';
    const ns = 'http://www.w3.org/2000/svg';

    if (!history.length) {
      const t = document.createElementNS(ns, 'text');
      t.setAttribute('x', '50%'); t.setAttribute('y', '50%');
      t.setAttribute('fill', '#444'); t.setAttribute('text-anchor', 'middle');
      t.setAttribute('dominant-baseline', 'middle'); t.setAttribute('font-size', '10');
      t.textContent = 'No data';
      svgEl.appendChild(t);
      return;
    }

    const pad = { top: 8, right: 8, bottom: 18, left: 44 };
    const iW = W - pad.left - pad.right;
    const iH = H - pad.top - pad.bottom;

    // Fixed x-axis: midnight AEST → midnight+24h (same for all 5 regions)
    const { tMin, tMax } = getTodayWindowMs();
    const tRange = tMax - tMin;
    const xS = t => pad.left + (t - tMin) / tRange * iW;

    // Price scale: all data in view
    const lastH = history[history.length - 1];
    const allPrices = [
      ...history.map(d => d.price_mwh),
      ...forecast.map(d => d.price_mwh),
    ].filter(v => v != null);
    const rawMin = Math.min(...allPrices);
    const rawMax = Math.max(...allPrices);
    const pPad = (rawMax - rawMin) * 0.15 || 20;
    const pMin = Math.min(0, rawMin - pPad);
    const pMax = rawMax + pPad;
    const pRange = pMax - pMin || 1;
    const yS = p => pad.top + iH - (p - pMin) / pRange * iH;

    // Vertical grid lines at 00:00, 06:00, 12:00, 18:00, 24:00
    [0, 6, 12, 18, 24].forEach(h => {
      const t = tMin + h * 3600000;
      const x = xS(t);
      const gl = document.createElementNS(ns, 'line');
      gl.setAttribute('x1', x); gl.setAttribute('x2', x);
      gl.setAttribute('y1', pad.top); gl.setAttribute('y2', pad.top + iH);
      gl.setAttribute('stroke', '#222'); gl.setAttribute('stroke-width', '1');
      svgEl.appendChild(gl);
      if (h > 0 && h < 24) {
        const tl = document.createElementNS(ns, 'text');
        tl.setAttribute('x', x); tl.setAttribute('y', pad.top + iH + 13);
        tl.setAttribute('fill', '#3a3a3a'); tl.setAttribute('font-size', '8');
        tl.setAttribute('text-anchor', 'middle');
        tl.textContent = `${String(h).padStart(2,'0')}:00`;
        svgEl.appendChild(tl);
      }
    });

    // Y-axis price labels (min, mid, max)
    [pMin, (pMin + pMax) / 2, pMax].forEach(p => {
      const y = yS(p);
      const lbl = document.createElementNS(ns, 'text');
      lbl.setAttribute('x', pad.left - 4); lbl.setAttribute('y', y + 3);
      lbl.setAttribute('fill', '#444'); lbl.setAttribute('font-size', '9');
      lbl.setAttribute('text-anchor', 'end');
      lbl.textContent = '$' + Math.round(p);
      svgEl.appendChild(lbl);
    });

    // Zero line if negatives
    if (pMin < 0) {
      const zy = yS(0);
      const zl = document.createElementNS(ns, 'line');
      zl.setAttribute('x1', pad.left); zl.setAttribute('x2', pad.left + iW);
      zl.setAttribute('y1', zy); zl.setAttribute('y2', zy);
      zl.setAttribute('stroke', '#333'); zl.setAttribute('stroke-dasharray', '3,2');
      svgEl.appendChild(zl);
    }

    // History area + line
    if (history.length > 1) {
      const pts = history.map(d => `${xS(new Date(d.timestamp).getTime()).toFixed(1)},${yS(d.price_mwh).toFixed(1)}`);
      const baseY = yS(Math.max(0, pMin)).toFixed(1);
      const x0 = pts[0].split(',')[0];
      const xN = pts[pts.length - 1].split(',')[0];

      const area = document.createElementNS(ns, 'polygon');
      area.setAttribute('points', `${x0},${baseY} ${pts.join(' ')} ${xN},${baseY}`);
      area.setAttribute('fill', 'rgba(76,175,80,0.08)');
      svgEl.appendChild(area);

      const pl = document.createElementNS(ns, 'polyline');
      pl.setAttribute('points', pts.join(' ')); pl.setAttribute('fill', 'none');
      pl.setAttribute('stroke', '#4caf50'); pl.setAttribute('stroke-width', '1.8');
      pl.setAttribute('stroke-linejoin', 'round');
      svgEl.appendChild(pl);
    }

    // Forecast dashed — bridge from last history point
    const fcastBridged = forecast.length ? [lastH, ...forecast] : [];
    if (fcastBridged.length > 1) {
      const pts = fcastBridged.map(d => `${xS(new Date(d.timestamp).getTime()).toFixed(1)},${yS(d.price_mwh).toFixed(1)}`).join(' ');
      const fl = document.createElementNS(ns, 'polyline');
      fl.setAttribute('points', pts); fl.setAttribute('fill', 'none');
      fl.setAttribute('stroke', '#ff8c30'); fl.setAttribute('stroke-width', '1.5');
      fl.setAttribute('stroke-dasharray', '5,3'); fl.setAttribute('stroke-linejoin', 'round');
      svgEl.appendChild(fl);
    }

    // "Now" vertical marker
    const nowX = xS(new Date(lastH.timestamp).getTime()).toFixed(1);
    const nowLine = document.createElementNS(ns, 'line');
    nowLine.setAttribute('x1', nowX); nowLine.setAttribute('x2', nowX);
    nowLine.setAttribute('y1', pad.top); nowLine.setAttribute('y2', pad.top + iH);
    nowLine.setAttribute('stroke', '#ffffff'); nowLine.setAttribute('stroke-width', '1');
    nowLine.setAttribute('opacity', '0.15');
    svgEl.appendChild(nowLine);
  }



  function renderRegion(region, data) {
    const history  = data.today_history    || [];
    const forecast = data.forward_forecast || [];
    const latest   = data.latest_interval  || {};
    const prices   = history.map(d => d.price_mwh).filter(v => v != null);
    const avg      = prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : null;
    const max      = prices.length ? Math.max(...prices) : null;
    const negCount = prices.filter(p => p < 0).length;

    const spotEl = document.getElementById(`nem-spot-${region}`);
    if (spotEl) { spotEl.textContent = fmtPrice(latest.price_mwh); spotEl.style.color = latest.price_mwh != null ? priceColor(latest.price_mwh) : ''; }
    const avgEl = document.getElementById(`nem-avg-${region}`);
    if (avgEl) avgEl.textContent = fmtPrice(avg);
    const maxEl = document.getElementById(`nem-max-${region}`);
    if (maxEl) maxEl.textContent = fmtPrice(max);
    const negEl = document.getElementById(`nem-neg-${region}`);
    if (negEl) negEl.textContent = negCount;
    const r6sEl = document.getElementById(`nem-r6s-${region}`);
    if (r6sEl) r6sEl.textContent = fmtPrice(latest.fcas_raise_6sec_aud_per_mw);
    drawSparkline(document.getElementById(`nem-chart-${region}`), history, forecast);
    const tsEl = document.getElementById(`nem-ts-${region}`);
    if (tsEl) tsEl.textContent = latest.timestamp ? `Updated ${fmtTime(latest.timestamp)} AEST` : '—';
  }

  // ── Spot + Forecast line chart (kept for BESS dispatch panel) ────────────
  function drawSpotChart(history, forecast) {
    const svg = document.getElementById('nem-spot-chart');
    if (!svg) return;
    const W = svg.parentElement.clientWidth || 600;
    const H = 220;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.innerHTML = '';

    const pad = { top: 16, right: 20, bottom: 32, left: 64 };
    const iW = W - pad.left - pad.right;
    const iH = H - pad.top - pad.bottom;

    const all = [...history, ...forecast];
    if (!all.length) { svg.innerHTML = '<text x="50%" y="50%" fill="#888" text-anchor="middle" dominant-baseline="middle">No data</text>'; return; }

    const times = all.map(d => new Date(d.timestamp).getTime());
    const prices = all.map(d => d.price_mwh);
    const tMin = Math.min(...times), tMax = Math.max(...times);
    const pMin = Math.min(0, Math.min(...prices));
    const pMax = Math.max(...prices) * 1.05 || 100;

    const xScale = t => pad.left + (t - tMin) / (tMax - tMin) * iW;
    const yScale = p => pad.top + iH - (p - pMin) / (pMax - pMin) * iH;

    // Grid lines
    const ns = 'http://www.w3.org/2000/svg';
    const g = document.createElementNS(ns, 'g');
    [0, 0.25, 0.5, 0.75, 1].forEach(f => {
      const y = pad.top + iH * (1 - f);
      const price = pMin + (pMax - pMin) * f;
      const line = document.createElementNS(ns, 'line');
      line.setAttribute('x1', pad.left); line.setAttribute('x2', pad.left + iW);
      line.setAttribute('y1', y); line.setAttribute('y2', y);
      line.setAttribute('stroke', '#2a2a2a'); line.setAttribute('stroke-width', '1');
      g.appendChild(line);
      const lbl = document.createElementNS(ns, 'text');
      lbl.setAttribute('x', pad.left - 6); lbl.setAttribute('y', y + 4);
      lbl.setAttribute('fill', '#666'); lbl.setAttribute('font-size', '10');
      lbl.setAttribute('text-anchor', 'end');
      lbl.textContent = '$' + Math.round(price);
      g.appendChild(lbl);
    });
    svg.appendChild(g);

    // Zero line if negative prices exist
    if (pMin < 0) {
      const zeroLine = document.createElementNS(ns, 'line');
      zeroLine.setAttribute('x1', pad.left); zeroLine.setAttribute('x2', pad.left + iW);
      const zy = yScale(0);
      zeroLine.setAttribute('y1', zy); zeroLine.setAttribute('y2', zy);
      zeroLine.setAttribute('stroke', '#444'); zeroLine.setAttribute('stroke-dasharray', '4,2');
      svg.appendChild(zeroLine);
    }

    // History area fill
    if (history.length > 1) {
      const pts = history.map(d => `${xScale(new Date(d.timestamp).getTime())},${yScale(d.price_mwh)}`).join(' ');
      const first = history[0], last = history[history.length - 1];
      const area = document.createElementNS(ns, 'polygon');
      const baseY = yScale(Math.max(0, pMin));
      area.setAttribute('points',
        `${xScale(new Date(first.timestamp).getTime())},${baseY} ${pts} ${xScale(new Date(last.timestamp).getTime())},${baseY}`);
      area.setAttribute('fill', 'rgba(76,175,80,0.08)');
      svg.appendChild(area);

      const histPath = document.createElementNS(ns, 'polyline');
      histPath.setAttribute('points', pts);
      histPath.setAttribute('fill', 'none');
      histPath.setAttribute('stroke', '#4caf50');
      histPath.setAttribute('stroke-width', '1.5');
      svg.appendChild(histPath);
    }

    // Forecast dashed line
    if (forecast.length > 1) {
      const pts = forecast.map(d => `${xScale(new Date(d.timestamp).getTime())},${yScale(d.price_mwh)}`).join(' ');
      const fPath = document.createElementNS(ns, 'polyline');
      fPath.setAttribute('points', pts);
      fPath.setAttribute('fill', 'none');
      fPath.setAttribute('stroke', '#ff8c30');
      fPath.setAttribute('stroke-width', '1.5');
      fPath.setAttribute('stroke-dasharray', '6,3');
      svg.appendChild(fPath);
    }

    // Now marker
    const nowTime = history.length ? new Date(history[history.length - 1].timestamp).getTime() : null;
    if (nowTime) {
      const nx = xScale(nowTime);
      const nowLine = document.createElementNS(ns, 'line');
      nowLine.setAttribute('x1', nx); nowLine.setAttribute('x2', nx);
      nowLine.setAttribute('y1', pad.top); nowLine.setAttribute('y2', pad.top + iH);
      nowLine.setAttribute('stroke', '#fff'); nowLine.setAttribute('stroke-width', '1'); nowLine.setAttribute('opacity', '0.3');
      svg.appendChild(nowLine);
    }

    // Legend
    const leg = document.createElementNS(ns, 'g');
    [[pad.left + 8, '#4caf50', 'Actual'], [pad.left + 80, '#ff8c30', 'Forecast']].forEach(([x, c, label], i) => {
      const line = document.createElementNS(ns, 'line');
      line.setAttribute('x1', x); line.setAttribute('x2', x + 20);
      line.setAttribute('y1', pad.top + 8); line.setAttribute('y2', pad.top + 8);
      line.setAttribute('stroke', c); line.setAttribute('stroke-width', '2');
      if (i === 1) line.setAttribute('stroke-dasharray', '5,3');
      leg.appendChild(line);
      const t = document.createElementNS(ns, 'text');
      t.setAttribute('x', x + 24); t.setAttribute('y', pad.top + 12);
      t.setAttribute('fill', '#aaa'); t.setAttribute('font-size', '10');
      t.textContent = label;
      leg.appendChild(t);
    });
    svg.appendChild(leg);
  }

  // ── FCAS bar chart ──────────────────────────────────────────────────────
  function drawFcasChart(row) {
    const svg = document.getElementById('nem-fcas-chart');
    if (!svg || !row) return;
    const W = svg.parentElement.clientWidth || 320;
    const H = 220;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.innerHTML = '';

    const markets = [
      { key: 'fcas_raise_1sec_aud_per_mw',  label: 'R1s' },
      { key: 'fcas_raise_6sec_aud_per_mw',  label: 'R6s' },
      { key: 'fcas_raise_60sec_aud_per_mw', label: 'R60s' },
      { key: 'fcas_raise_5min_aud_per_mw',  label: 'R5m' },
      { key: 'fcas_reg_raise_aud_per_mw',   label: 'RRaise' },
      { key: 'fcas_lower_1sec_aud_per_mw',  label: 'L1s' },
      { key: 'fcas_lower_6sec_aud_per_mw',  label: 'L6s' },
      { key: 'fcas_lower_60sec_aud_per_mw', label: 'L60s' },
      { key: 'fcas_lower_5min_aud_per_mw',  label: 'L5m' },
      { key: 'fcas_reg_lower_aud_per_mw',   label: 'RLower' },
    ];
    const ns = 'http://www.w3.org/2000/svg';
    const pad = { top: 16, right: 12, bottom: 36, left: 52 };
    const iW = W - pad.left - pad.right;
    const iH = H - pad.top - pad.bottom;
    const vals = markets.map(m => row[m.key] || 0);
    const maxVal = Math.max(...vals, 1);
    const barW = iW / markets.length;

    markets.forEach((m, i) => {
      const v = vals[i];
      const bH = (v / maxVal) * iH;
      const x = pad.left + i * barW + barW * 0.1;
      const w = barW * 0.8;
      const rect = document.createElementNS(ns, 'rect');
      rect.setAttribute('x', x);
      rect.setAttribute('y', pad.top + iH - bH);
      rect.setAttribute('width', w);
      rect.setAttribute('height', bH);
      rect.setAttribute('fill', i < 5 ? '#4caf50' : '#00bcd4');
      rect.setAttribute('rx', '2');
      svg.appendChild(rect);

      const valLbl = document.createElementNS(ns, 'text');
      valLbl.setAttribute('x', x + w / 2);
      valLbl.setAttribute('y', pad.top + iH - bH - 3);
      valLbl.setAttribute('fill', '#aaa');
      valLbl.setAttribute('font-size', '8');
      valLbl.setAttribute('text-anchor', 'middle');
      valLbl.textContent = v > 0 ? '$' + Math.round(v) : '';
      svg.appendChild(valLbl);

      const lbl = document.createElementNS(ns, 'text');
      lbl.setAttribute('x', x + w / 2);
      lbl.setAttribute('y', pad.top + iH + 12);
      lbl.setAttribute('fill', '#888');
      lbl.setAttribute('font-size', '9');
      lbl.setAttribute('text-anchor', 'middle');
      lbl.textContent = m.label;
      svg.appendChild(lbl);
    });

    // Y axis label
    const yLbl = document.createElementNS(ns, 'text');
    yLbl.setAttribute('x', 10);
    yLbl.setAttribute('y', pad.top + iH / 2);
    yLbl.setAttribute('fill', '#666');
    yLbl.setAttribute('font-size', '9');
    yLbl.setAttribute('text-anchor', 'middle');
    yLbl.setAttribute('transform', `rotate(-90, 10, ${pad.top + iH / 2})`);
    yLbl.textContent = '$/MWh';
    svg.appendChild(yLbl);
  }

  // ── Table ───────────────────────────────────────────────────────────────
  function renderTable(history) {
    const tbody = document.getElementById('nem-table-body');
    if (!tbody) return;
    const rows = [...history].reverse().slice(0, 24);
    tbody.innerHTML = rows.map(d => {
      const p = d.price_mwh;
      const cls = p > 300 ? 'price-spike' : p < 0 ? 'price-neg' : '';
      return `<tr class="${cls}">
        <td>${fmtTime(d.timestamp)}</td>
        <td>${fmtPrice(p)}</td>
        <td>${fmtPrice(d.fcas_raise_6sec_aud_per_mw)}</td>
        <td>${fmtPrice(d.fcas_raise_60sec_aud_per_mw)}</td>
        <td>${fmtPrice(d.fcas_raise_5min_aud_per_mw)}</td>
        <td>${fmtPrice(d.fcas_reg_raise_aud_per_mw)}</td>
        <td>${fmtPrice(d.fcas_lower_6sec_aud_per_mw)}</td>
      </tr>`;
    }).join('');
  }

  // ── Load all regions in parallel ────────────────────────────────────────
  let _loading = _nemLoading; // prevent concurrent fetches

  async function loadAllRegions(force = false) {
    if (_nemLoading) return;
    _nemLoading = true; _loading = true;
    setStatus('Fetching all regions…', '');
    const port = window._API_PORT || API_PORT || 8765;
    let loaded = 0, errors = 0;

    await Promise.allSettled(NEM_REGIONS.map(async r => {
      try {
        const res = await fetch(`http://127.0.0.1:${port}/api/nem/snapshot?region=${r.code}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        // Only update if we actually got history rows — never overwrite good data with empty
        const hasData = (data.today_history || []).length > 0;
        if (hasData || force || !nemCache[r.code]) {
          nemCache[r.code] = { data, fetchedAt: Date.now() };
          renderRegion(r.code, data);
        }
        loaded++;
      } catch (e) {
        errors++;
        // If we have cached data, keep displaying it — just update timestamp
        const tsEl = document.getElementById(`nem-ts-${r.code}`);
        if (tsEl) {
          const cached = nemCache[r.code];
          tsEl.textContent = cached ? `Cached — refresh failed` : `Error: ${e.message}`;
        }
      }
    }));

    _nemLoading = false; _loading = false;
    const now = new Date().toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit', hour12: false });
    setStatus(
      errors && loaded === 0 ? `● Error — click ↺ to retry` :
      errors ? `● ${loaded}/5 live — ${errors} using cache — ${now} AEST` :
      `● Live — all regions — ${now} AEST`,
      errors && loaded === 0 ? 'error' : 'ready'
    );
  }

  refreshBtn?.addEventListener('click', () => { _nemLoading = false; _loading = false; loadAllRegions(true); });

  if (!reinit) {
    // Only attach nav/timer listeners once — they survive Cmd+R because the
    // module-level _nemDashboardInitialised flag prevents re-registration.
    document.querySelectorAll('.nav-btn[data-tab="nem"]').forEach(navBtn => {
      navBtn.addEventListener('click', () => {
        const anyStale = NEM_REGIONS.some(r => !nemCache[r.code] || Date.now() - nemCache[r.code].fetchedAt > REFRESH_MS);
        if (anyStale && !_nemLoading) loadAllRegions();
        clearInterval(_nemRefreshTimer);
        _nemRefreshTimer = setInterval(loadAllRegions, REFRESH_MS);
      });
    });

    // Poll until backend ready, then start the auto-refresh cycle
    async function waitForBackendThenLoad() {
      const port = window._API_PORT || API_PORT || 8765;
      const MAX_ATTEMPTS = 30;
      const POLL_MS = 2000;
      for (let i = 0; i < MAX_ATTEMPTS; i++) {
        try {
          const r = await fetch(`http://127.0.0.1:${port}/api/vault/stats`);
          if (r.ok) {
            await loadAllRegions();
            _nemRefreshTimer = setInterval(loadAllRegions, REFRESH_MS);
            return;
          }
        } catch (_) { /* backend not ready yet */ }
        setStatus(`Waiting for backend… (${i + 1}/${MAX_ATTEMPTS})`, '');
        await new Promise(res => setTimeout(res, POLL_MS));
      }
      setStatus('Backend unreachable — click ↺ to retry', 'error');
    }

    waitForBackendThenLoad();
  } else {
    // Cmd+R reload: DOM rebuilt, just re-render from cache (no re-fetch needed)
    NEM_REGIONS.forEach(r => {
      if (nemCache[r.code]) renderRegion(r.code, nemCache[r.code].data);
    });
    const now = new Date().toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit', hour12: false });
    setStatus(`● Live — all regions — ${now} AEST`, 'ready');
  }
}
// ── Digital Twin — BESS Dispatch Algorithm Overlay ───────────────────────────
function initDispatchAlgorithm() {
  const runBtn = document.getElementById('dispatch-run-btn');
  if (!runBtn) return;

  runBtn.addEventListener('click', runDispatch);

  // Solar co-location toggle
  const dpSolarEnable = document.getElementById('dp-solar-enable');
  const dpSolarFields = document.getElementById('dp-solar-fields');
  if (dpSolarEnable && dpSolarFields) {
    dpSolarEnable.addEventListener('change', function() {
      dpSolarFields.style.display = this.checked ? '' : 'none';
    });
  }

  async function runDispatch() {
    const region   = document.getElementById('dp-region')?.value || 'VIC1';
    const bessMw   = parseFloat(document.getElementById('dp-mw').value)   || 5;
    const bessMwh  = parseFloat(document.getElementById('dp-mwh').value)  || 10;
    const strategy = document.getElementById('dp-strategy')?.value || 'co_optimised_revenue_max';
    const solarOn  = document.getElementById('dp-solar-enable')?.checked || false;
    const solarMw  = solarOn ? (parseFloat(document.getElementById('dp-solar-mw')?.value) || 6) : 0;
    const solarLat = solarOn ? (parseFloat(document.getElementById('dp-solar-lat')?.value) || -37.8136) : -37.8136;
    const solarLon = solarOn ? (parseFloat(document.getElementById('dp-solar-lon')?.value) || 144.9631) : 144.9631;

    const badge = document.getElementById('dispatch-status');
    badge.textContent = 'Running...';
    badge.className = 'dispatch-status-badge running';
    runBtn.disabled = true;

    try {
      const params = new URLSearchParams({ region, bess_mw: bessMw, bess_mwh: bessMwh, strategy,
        solar_dc_mw: solarMw, solar_lat: solarLat, solar_lon: solarLon });
      const res = await fetch('http://127.0.0.1:' + API_PORT + '/api/nem/dispatch?' + params);
      if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
      const data = await res.json();
      renderDispatchResult(data);
      const strat = data.strategy_name || strategy;
      badge.textContent = 'Done — ' + strat + ' · ' + (data.intervals ? data.intervals.length : 0) + ' intervals';
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
    el.outerHTML = html.replace('<svg ', '<svg id="dispatch-soc-chart" ');
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
    el.outerHTML = html.replace('<svg ', '<svg id="dispatch-rev-chart" ');
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


// ── Backcast & YTD Strategy Comparison ───────────────────────────────────────
function initBackcastPanel() {
  const runBtn = document.getElementById('backcast-run-btn');
  if (!runBtn) return;
  runBtn.addEventListener('click', runBackcast);

  // Solar co-location toggle
  const bcSolarEnable = document.getElementById('bc-solar-enable');
  const bcSolarFields = document.getElementById('bc-solar-fields');
  if (bcSolarEnable && bcSolarFields) {
    bcSolarEnable.addEventListener('change', function() {
      bcSolarFields.style.display = this.checked ? '' : 'none';
    });
  }

  async function runBackcast() {
    const region = document.getElementById('dp-region')?.value || 'VIC1';
    const days   = parseInt(document.getElementById('bc-days')?.value) || 365;
    const bessMw = parseFloat(document.getElementById('bc-mw')?.value) || 5;
    const bessMwh = parseFloat(document.getElementById('bc-mwh')?.value) || 10;
    const solarOn  = document.getElementById('bc-solar-enable')?.checked || false;
    const solarMw  = solarOn ? (parseFloat(document.getElementById('bc-solar-mw')?.value) || 6) : 0;
    const solarLat = solarOn ? (parseFloat(document.getElementById('bc-solar-lat')?.value) || -37.8136) : -37.8136;
    const solarLon = solarOn ? (parseFloat(document.getElementById('bc-solar-lon')?.value) || 144.9631) : 144.9631;
    const checks = document.querySelectorAll('#backcast-strategy-checks input[type=checkbox]:checked');
    const strategyIds = Array.from(checks).map(function(c){ return c.value; });
    if (!strategyIds.length) { alert('Select at least one strategy.'); return; }

    const badge = document.getElementById('backcast-status');
    badge.textContent = 'Running… (may take 30–90s for large windows)';
    badge.className = 'dispatch-status-badge running';
    runBtn.disabled = true;

    try {
      const params = new URLSearchParams({
        region, days, bess_mw: bessMw, bess_mwh: bessMwh,
        strategies: strategyIds.join(','),
        solar_dc_mw: solarMw, solar_lat: solarLat, solar_lon: solarLon,
      });
      const res = await fetch('http://127.0.0.1:' + API_PORT + '/api/nem/backcast/compare?' + params);
      if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      renderYTDTiles(data);
      renderBackcastChart(data);
      renderBackcastTable(data);
      badge.textContent = 'Done — ' + days + ' days · ' + strategyIds.length + ' strategies';
      badge.className = 'dispatch-status-badge done';
    } catch (err) {
      badge.textContent = 'Error: ' + err.message;
      badge.className = 'dispatch-status-badge error';
    } finally {
      runBtn.disabled = false;
    }
  }

  function renderYTDTiles(data) {
    var container = document.getElementById('backcast-ytd-row');
    if (!container) return;
    var strategies = data.strategies || {};
    var ytdYear = data.ytd_year || new Date().getFullYear();
    var $ = function(v) { return v == null ? '—' : '$' + Math.round(v).toLocaleString('en-AU'); };

    // Find best YTD for highlighting
    var best = Math.max.apply(null, Object.values(strategies).map(function(s){ return s.ytd_revenue_aud || 0; }));

    container.innerHTML = Object.entries(strategies).map(function(entry) {
      var sid = entry[0], s = entry[1];
      var isBest = s.ytd_revenue_aud === best && best > 0;
      var annualStr = s.annual_revenue_aud != null ? $(s.annual_revenue_aud) : $(s.total_revenue_aud);
      return '<div class="dispatch-kpi' + (isBest ? ' kpi-best' : '') + '">' +
        '<div class="dispatch-kpi-label">' + (s.strategy_name || sid) + '</div>' +
        '<div class="dispatch-kpi-val">' + $(s.ytd_revenue_aud) + '</div>' +
        '<div class="dispatch-kpi-sub">YTD ' + ytdYear + ' arb rev</div>' +
        '<div class="dispatch-kpi-sub">' + annualStr + ' est. annual (' + data.days + 'd window)</div>' +
        '<div class="dispatch-kpi-sub">' + $(s.total_revenue_aud) + ' total backcast</div>' +
        (isBest ? '<div class="kpi-best-badge">★ Best</div>' : '') +
        '</div>';
    }).join('');
    container.classList.remove('hidden');
  }

  // Colour palette for strategies
  var _STRAT_COLORS = {
    'co_optimised_revenue_max': '#4ade80',
    'co_optimised_contingency_first': '#60a5fa',
    'co_optimised_reg_guaranteed': '#a78bfa',
    'fcas_only': '#f59e0b',
    'arb_only': '#f87171',
    'conservative_peak_discharge': '#94a3b8',
  };

  function renderBackcastChart(data) {
    var el = document.getElementById('backcast-rev-chart');
    if (!el) return;
    var strategies = data.strategies || {};
    var sids = Object.keys(strategies);
    if (!sids.length) return;

    // Build a unified month axis
    var allMonths = Array.from(new Set(
      sids.flatMap(function(sid){ return (strategies[sid].monthly || []).map(function(m){ return m.month; }); })
    )).sort();
    if (!allMonths.length) return;

    var W = el.parentElement.clientWidth || 700, H = 220;
    var pad = { t: 14, r: 120, b: 40, l: 60 };
    var iW = W - pad.l - pad.r, iH = H - pad.t - pad.b;

    // Build cumulative series per strategy
    var series = sids.map(function(sid) {
      var monthly = strategies[sid].monthly || [];
      var byMonth = {};
      monthly.forEach(function(m){ byMonth[m.month] = m.revenue_aud; });
      var cum = 0;
      return allMonths.map(function(mo) { cum += byMonth[mo] || 0; return cum; });
    });

    var allVals = series.flat();
    var minV = Math.min.apply(null, allVals.concat([0]));
    var maxV = Math.max.apply(null, allVals.concat([1]));
    var span = maxV - minV || 1;
    function xS(i) { return pad.l + (i / Math.max(allMonths.length - 1, 1)) * iW; }
    function yS(v) { return pad.t + (1 - (v - minV) / span) * iH; }

    var html = '<svg width="' + W + '" height="' + H + '" xmlns="http://www.w3.org/2000/svg">';
    // grid + y labels
    var useKilo = Math.abs(maxV) >= 2000 || Math.abs(minV) >= 2000;
    function fmtAud(v) {
      if (useKilo) return (v >= 0 ? '$' : '-$') + Math.round(Math.abs(v) / 1000) + 'k';
      return (v >= 0 ? '$' : '-$') + Math.round(Math.abs(v)).toLocaleString('en-AU');
    }
    [0, 0.25, 0.5, 0.75, 1].forEach(function(frac) {
      var v = minV + frac * span;
      var y = yS(v);
      html += '<line x1="' + pad.l + '" y1="' + y + '" x2="' + (W - pad.r) + '" y2="' + y + '" stroke="#2a2a2a" stroke-width="1"/>';
      html += '<text x="' + (pad.l - 6) + '" y="' + (y + 4) + '" text-anchor="end" font-size="9" fill="#666">' + fmtAud(v) + '</text>';
    });
    // x labels (month names)
    var step = Math.max(1, Math.floor(allMonths.length / 8));
    allMonths.forEach(function(mo, i) {
      if (i % step === 0) {
        html += '<text x="' + xS(i) + '" y="' + (H - pad.b + 14) + '" text-anchor="middle" font-size="9" fill="#666">' + mo.substring(2) + '</text>';
      }
    });
    // series lines
    sids.forEach(function(sid, si) {
      var color = _STRAT_COLORS[sid] || '#aaa';
      var pts = series[si].map(function(v, i) { return xS(i) + ',' + yS(v); }).join(' ');
      html += '<polyline points="' + pts + '" fill="none" stroke="' + color + '" stroke-width="2"/>';
      // end label
      var lastY = yS(series[si][series[si].length - 1]);
      var name = (strategies[sid].strategy_name || sid).replace('Co-optimised: ', '').replace('co_optimised_', '').replace('_', ' ');
      html += '<text x="' + (W - pad.r + 4) + '" y="' + (lastY + 4) + '" font-size="9" fill="' + color + '">' + name.substring(0,18) + '</text>';
    });
    html += '</svg>';
    el.outerHTML = html.replace('<svg ', '<svg id="backcast-rev-chart" ');
    document.getElementById('backcast-chart-wrap').classList.remove('hidden');
  }

  function renderBackcastTable(data) {
    var strategies = data.strategies || {};
    var sids = Object.keys(strategies);
    if (!sids.length) return;

    var allMonths = Array.from(new Set(
      sids.flatMap(function(sid){ return (strategies[sid].monthly || []).map(function(m){ return m.month; }); })
    )).sort();

    var thead = document.getElementById('backcast-table-head');
    var tbody = document.getElementById('backcast-table-body');
    if (!thead || !tbody) return;

    var $ = function(v) { return v == null ? '—' : '$' + Math.round(v).toLocaleString('en-AU'); };

    thead.innerHTML = '<tr><th>Month</th>' + sids.map(function(sid){
      return '<th>' + (strategies[sid].strategy_name || sid) + '</th>';
    }).join('') + '</tr>';

    // Build lookup: sid -> month -> revenue
    var lookup = {};
    sids.forEach(function(sid) {
      lookup[sid] = {};
      (strategies[sid].monthly || []).forEach(function(m){ lookup[sid][m.month] = m.revenue_aud; });
    });

    // YTD row at top
    tbody.innerHTML = '<tr class="ytd-row"><td><strong>YTD ' + data.ytd_year + '</strong></td>' +
      sids.map(function(sid) {
        return '<td><strong>' + $(strategies[sid].ytd_revenue_aud) + '</strong></td>';
      }).join('') + '</tr>' +
      allMonths.slice().reverse().map(function(mo) {
        var vals = sids.map(function(sid){ return lookup[sid][mo] || 0; });
        var maxVal = Math.max.apply(null, vals);
        return '<tr><td>' + mo + '</td>' + sids.map(function(sid, i) {
          var v = lookup[sid][mo];
          var isBest = v != null && v === maxVal && maxVal > 0;
          return '<td' + (isBest ? ' class="cell-best"' : '') + '>' + $(v) + '</td>';
        }).join('') + '</tr>';
      }).join('');

    // FCAS note
    var noteEl = document.getElementById('backcast-fcas-note');
    if (noteEl) {
      var firstSid = sids[0];
      noteEl.textContent = strategies[firstSid] ? strategies[firstSid].fcas_note : '';
    }

    document.getElementById('backcast-table-wrap').classList.remove('hidden');
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── To-Do Tab ─────────────────────────────────────────────────────────────────
let _todoFilter = 'active';
async function initTodos() {
  const addBtn = document.getElementById('todo-add-btn');
  const input  = document.getElementById('todo-input');
  if (!addBtn || addBtn._todoBound) return;
  addBtn._todoBound = true;

  const syncBtn = document.getElementById('todo-sync-btn');
  if (syncBtn && !syncBtn._bound) {
    syncBtn._bound = true;
    syncBtn.addEventListener('click', async () => {
      syncBtn.textContent = '⟳ Syncing…';
      syncBtn.disabled = true;
      await fetch(`http://127.0.0.1:${API_PORT}/todos/sync-from-md`, { method: 'POST' }).catch(()=>null);
      await renderTodos();
      syncBtn.textContent = '⟳ Sync';
      syncBtn.disabled = false;
    });
  }

  addBtn.addEventListener('click', async () => {
    const text = input.value.trim();
    if (!text) return;
    const priority = document.getElementById('todo-priority').value;
    const area     = document.getElementById('todo-area').value;
    await fetch(`http://127.0.0.1:${API_PORT}/todos`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ text, priority, area })
    });
    input.value = '';
    renderTodos();
  });
  input.addEventListener('keydown', e => { if (e.key==='Enter') addBtn.click(); });

  document.querySelectorAll('.todo-filter-btn').forEach(b => {
    b.addEventListener('click', () => {
      document.querySelectorAll('.todo-filter-btn').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      _todoFilter = b.dataset.filter;
      renderTodos();
    });
  });
  renderTodos();
}

async function renderTodos() {
  const res = await fetch(`http://127.0.0.1:${API_PORT}/todos`).catch(()=>null);
  if (!res) return;
  const todos = await res.json();
  const container = document.getElementById('todo-columns');
  if (!container) return;

  const filtered = todos.filter(t => {
    if (_todoFilter === 'active')    return !t.done;
    if (_todoFilter === 'done')      return  t.done;
    if (_todoFilter === 'david_lee') return (t.tags && t.tags.includes('david_lee'));
    return true;
  });

  const priorityIcon = { high:'🔴', medium:'🟡', low:'🟢' };
  const areaColour   = { BDM:'#3b82f6', Investment:'#f59e0b', Divorce:'#a855f7',
                         Grants:'#10b981', Tech:'#06b6d4', Finance:'#f97316',
                         Legal:'#ef4444', Personal:'#ec4899', Other:'#6b7280' };
  const areaOrder = ['BDM','Grants','Investment','Tech','Finance','Legal','Divorce','Personal','Other'];

  // Group by area
  const grouped = {};
  filtered.forEach(t => { const a = t.area||'Other'; if (!grouped[a]) grouped[a]=[]; grouped[a].push(t); });
  const cols = areaOrder.filter(a => grouped[a] && grouped[a].length > 0);

  container.innerHTML = cols.map(area => {
    const colour = areaColour[area] || '#6b7280';
    const items  = grouped[area];
    const itemsHtml = items.map(t => `
      <li style="display:flex;align-items:flex-start;gap:8px;padding:9px 10px;margin-bottom:6px;background:#131929;border-radius:7px;border-left:3px solid ${colour}">
        <input type="checkbox" ${t.done?'checked':''} onchange="(async()=>{await fetch('http://127.0.0.1:${API_PORT}/todos/${escHtml(t.id)}',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({done:this.checked})});renderTodos();})()" style="cursor:pointer;margin-top:2px;flex-shrink:0">
        <span style="flex:1;color:${t.done?'#718096':'#e2e8f0'};text-decoration:${t.done?'line-through':'none'};font-size:13px;line-height:1.4">${priorityIcon[t.priority]||''} ${escHtml(t.text)}</span>
        <button onclick="(async()=>{await fetch('http://127.0.0.1:${API_PORT}/todos/${escHtml(t.id)}',{method:'DELETE'});renderTodos();})()" style="background:none;border:none;color:#4a5568;cursor:pointer;font-size:14px;padding:0;flex-shrink:0">&times;</button>
      </li>`).join('');
    return `
      <div style="flex:0 0 230px;background:#1e2433;border-radius:10px;overflow:hidden;max-height:calc(100vh - 210px);display:flex;flex-direction:column">
        <div style="padding:10px 12px;background:${colour}22;border-bottom:2px solid ${colour};display:flex;justify-content:space-between;align-items:center;flex-shrink:0">
          <span style="font-weight:600;color:${colour};font-size:12px;text-transform:uppercase;letter-spacing:0.5px">${area}</span>
          <span style="font-size:11px;color:#718096">${items.filter(x=>!x.done).length} left</span>
        </div>
        <ul style="list-style:none;padding:8px;margin:0;overflow-y:auto;flex:1">${itemsHtml}</ul>
      </div>`;
  }).join('');
}

// ── NNA Map Tab ───────────────────────────────────────────────────────────────
let _nnaMap = null, _nnaMarkers = [], _nnaData = [], _nnaInited = false;
let _nnaFilters = { dnsp:[], state:[], season:'', search:'', favOnly:false,
                   contractsOnly:false, minDeferral:0, minMw:0, minAdv:0, chatFilters:null };

async function initNNAMap() {
  if (_nnaInited) { _nnaRender(); return; }

  // Load meta for chips
  const meta = await fetch(`http://127.0.0.1:${API_PORT}/nna/meta`).then(r=>r.json()).catch(()=>({dnsp_list:[],state_list:[],dnsp_colors:{}}));

  // DNSP chips
  const dc = document.getElementById('nna-dnsp-chips');
  if (dc) {
    dc.innerHTML = '<span class="nna-chip active" data-val="">All</span>' +
      meta.dnsp_list.map(d=>`<span class="nna-chip" data-val="${escHtml(d)}" style="border-color:${meta.dnsp_colors[d]||'#4a5568'}">${escHtml(d)}</span>`).join('');
    dc.querySelectorAll('.nna-chip').forEach(c => c.addEventListener('click', () => {
      const v = c.dataset.val;
      if (v==='') { _nnaFilters.dnsp=[]; dc.querySelectorAll('.nna-chip').forEach(x=>x.classList.remove('active')); c.classList.add('active'); }
      else { dc.querySelector('[data-val=""]').classList.remove('active'); c.classList.toggle('active'); _nnaFilters.dnsp=[...dc.querySelectorAll('.nna-chip.active:not([data-val=""])').values()].map(x=>x.dataset.val); }
      _nnaRender();
    }));
  }

  // State chips
  const sc = document.getElementById('nna-state-chips');
  if (sc) {
    sc.innerHTML = '<span class="nna-chip active" data-val="">All</span>' +
      meta.state_list.map(s=>`<span class="nna-chip" data-val="${escHtml(s)}">${escHtml(s)}</span>`).join('');
    sc.querySelectorAll('.nna-chip').forEach(c => c.addEventListener('click', () => {
      const v = c.dataset.val;
      if (v==='') { _nnaFilters.state=[]; sc.querySelectorAll('.nna-chip').forEach(x=>x.classList.remove('active')); c.classList.add('active'); }
      else { sc.querySelector('[data-val=""]').classList.remove('active'); c.classList.toggle('active'); _nnaFilters.state=[...sc.querySelectorAll('.nna-chip.active:not([data-val=""])').values()].map(x=>x.dataset.val); }
      _nnaRender();
    }));
  }

  // Season chips
  document.querySelectorAll('#nna-season-chips .nna-chip').forEach(c => {
    c.addEventListener('click', () => {
      document.querySelectorAll('#nna-season-chips .nna-chip').forEach(x=>x.classList.remove('active'));
      c.classList.add('active'); _nnaFilters.season = c.dataset.val; _nnaRender();
    });
  });

  // Fav / contracts toggles
  document.getElementById('nna-fav-only')?.addEventListener('change', e => { _nnaFilters.favOnly=e.target.checked; _nnaRender(); });
  document.getElementById('nna-contracts-only')?.addEventListener('change', e => { _nnaFilters.contractsOnly=e.target.checked; _nnaRender(); });

  // Search
  document.getElementById('nna-search')?.addEventListener('input', e => { _nnaFilters.search=e.target.value.toLowerCase(); _nnaRender(); });

  // Sliders
  ['nna-min-deferral','nna-min-mw','nna-min-adv'].forEach(id => {
    const el = document.getElementById(id);
    const vEl = document.getElementById(id+'-val');
    if (!el) return;
    el.addEventListener('input', () => {
      const v = parseFloat(el.value);
      if (vEl) vEl.textContent = v;
      const pct = (v / parseFloat(el.max)) * 100;
      el.style.setProperty('--pct', pct+'%');
      if (id==='nna-min-deferral') _nnaFilters.minDeferral = v;
      else if (id==='nna-min-mw')  _nnaFilters.minMw = v;
      else if (id==='nna-min-adv') _nnaFilters.minAdv = v;
      _nnaRender();
    });
  });

  // Chat filter
  document.getElementById('nna-chat-btn')?.addEventListener('click', async () => {
    const q = document.getElementById('nna-chat-input')?.value?.trim();
    if (!q) { _nnaFilters.chatFilters=null; document.getElementById('nna-chat-msg').textContent=''; _nnaRender(); return; }
    const r = await fetch(`http://127.0.0.1:${API_PORT}/nna/chat`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:q}) }).then(x=>x.json()).catch(()=>null);
    if (r) { _nnaFilters.chatFilters=r; document.getElementById('nna-chat-msg').textContent=r.summary||''; _nnaRender(); }
  });

  // Init Leaflet map
  const mapEl = document.getElementById('nna-map');
  if (mapEl && typeof L !== 'undefined' && !_nnaMap) {
    _nnaMap = L.map('nna-map', { center:[-28,134], zoom:4, zoomControl:true });
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution:'&copy; OpenStreetMap &copy; CARTO', maxZoom:19
    }).addTo(_nnaMap);
  }

  // Load data
  const data = await fetch(`http://127.0.0.1:${API_PORT}/nna/opportunities`).then(r=>r.json()).catch(()=>[]);
  _nnaData = data;
  _nnaInited = true;
  _nnaRender();
}

function _nnaFiltered() {
  return _nnaData.filter(o => {
    if (_nnaFilters.dnsp.length && !_nnaFilters.dnsp.includes(o.dnsp)) return false;
    if (_nnaFilters.state.length && !_nnaFilters.state.includes(o.state)) return false;
    if (_nnaFilters.season && o.peak_season && !o.peak_season.toLowerCase().includes(_nnaFilters.season)) return false;
    if (_nnaFilters.favOnly && !o.is_favourite) return false;
    if (_nnaFilters.contractsOnly && !o.is_nna) return false;
    if (_nnaFilters.search) {
      const hay = [o.dnsp,o.title,o.location,o.state,o.description].join(' ').toLowerCase();
      if (!hay.includes(_nnaFilters.search)) return false;
    }
    if (_nnaFilters.minDeferral > 0 && !(o.deferral_value_m >= _nnaFilters.minDeferral)) return false;
    if (_nnaFilters.minMw > 0 && !(o.demand_reduction_mw >= _nnaFilters.minMw)) return false;
    if (_nnaFilters.minAdv > 0 && !(o.annual_deferral_value_m >= _nnaFilters.minAdv)) return false;
    if (_nnaFilters.chatFilters) {
      const cf = _nnaFilters.chatFilters;
      if (cf.dnsp?.length && !cf.dnsp.includes(o.dnsp)) return false;
      if (cf.state?.length && !cf.state.includes(o.state)) return false;
      if (cf.season && o.peak_season && !o.peak_season.toLowerCase().includes(cf.season)) return false;
      if (cf.min_mw && !(o.demand_reduction_mw >= cf.min_mw)) return false;
      if (cf.favs_only && !o.is_favourite) return false;
    }
    return true;
  });
}

const _dnspColors = {};
function _nnaGetColor(dnsp) {
  const palette = ['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#f97316','#ec4899','#84cc16','#14b8a6','#a855f7','#fb923c'];
  if (!_dnspColors[dnsp]) {
    const keys = Object.keys(_dnspColors);
    _dnspColors[dnsp] = palette[keys.length % palette.length];
  }
  return _dnspColors[dnsp];
}

function _nnaRender() {
  const visible = _nnaFiltered();

  // Update map markers
  if (_nnaMap) {
    _nnaMarkers.forEach(m => m.remove());
    _nnaMarkers = [];
    // Draw network nodes first (under contracts)
    visible.filter(o=>!o.is_nna).forEach(o => {
      if (!o.lat || !o.lng) return;
      const color = _nnaGetColor(o.dnsp);
      const m = L.circleMarker([o.lat, o.lng], {
        radius:5, color, fillColor:color, fillOpacity:0.15, weight:1.5
      }).addTo(_nnaMap);
      m.bindTooltip(`${o.dnsp} — ${o.title||o.location||''}`);
      m.on('click', () => _nnaShowDetail(o));
      _nnaMarkers.push(m);
    });
    // Draw NNA contracts on top
    visible.filter(o=>o.is_nna).forEach(o => {
      if (!o.lat || !o.lng) return;
      const color = _nnaGetColor(o.dnsp);
      const r = Math.max(7, Math.min(22, 7 + (o.demand_reduction_mw||0) * 0.8));
      const m = L.circleMarker([o.lat, o.lng], {
        radius:r, color, fillColor:color, fillOpacity:0.75, weight:2
      }).addTo(_nnaMap);
      m.bindTooltip(`⚡ ${o.dnsp} — ${o.title||o.location||''} ${o.demand_reduction_mw?'('+o.demand_reduction_mw+'MW)':''}`);
      m.on('click', () => _nnaShowDetail(o));
      _nnaMarkers.push(m);
    });
    // Invalidate size after render (fixes grey-tile bug when tab was hidden)
    setTimeout(() => _nnaMap.invalidateSize(), 50);
  }

  // Update sidebar list — use data-id to avoid inline JSON quoting issues
  const listEl = document.getElementById('nna-results-list');
  if (!listEl) return;
  if (!visible.length) { listEl.innerHTML='<div style="color:#718096;font-size:13px;padding:12px">No results</div>'; return; }
  listEl.innerHTML = visible.slice(0,80).map(o => {
    const color = _nnaGetColor(o.dnsp);
    const adv   = o.annual_deferral_value_m ? ` <span style="color:#10b981">$${parseFloat(o.annual_deferral_value_m).toFixed(2)}M/yr</span>` : '';
    return `<div class="nna-result-item ${o.is_nna?'nna-is-contract':'nna-is-node'}" data-nna-id="${escHtml(o.id)}" style="border-left:3px solid ${color}">
      <div class="nna-result-title">${escHtml(o.title||o.location||'Unknown')}${adv}</div>
      <div class="nna-result-meta">${escHtml(o.dnsp)} · ${escHtml(o.state||'')} · ${escHtml(o.peak_season||'')}</div>
    </div>`;
  }).join('');
  // Attach click via event delegation — no inline JSON
  listEl.querySelectorAll('[data-nna-id]').forEach(el => {
    el.addEventListener('click', () => {
      const o = _nnaData.find(x => x.id === el.dataset.nnaId);
      if (o) _nnaShowDetail(o);
    });
  });
}

function _nnaShowDetail(o) {
  const el = document.getElementById('nna-detail');
  if (!el) return;
  const color = _nnaGetColor(o.dnsp);
  const rows = [
    ['DNSP', o.dnsp], ['State', o.state], ['Location', o.location],
    ['Season', o.peak_season],
    ['Demand Reduction', o.demand_reduction_mw ? o.demand_reduction_mw + ' MW' : ''],
    ['Deferral Value', o.deferral_value_m ? '$' + o.deferral_value_m + 'M' : ''],
    ['Annual Value', o.annual_deferral_value_m ? '$' + o.annual_deferral_value_m + 'M/yr' : ''],
    ['Window', o.service_window], ['Description', o.description]
  ].filter(([, v]) => v);

  el.style.display = 'block';
  el.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <strong style="color:#e2e8f0;font-size:14px">${escHtml(o.title||o.location||'Opportunity')}</strong>
      <span id="nna-fav-btn" style="cursor:pointer;font-size:20px;color:${o.is_favourite?'#f59e0b':'#718096'}">${o.is_favourite?'★':'☆'}</span>
    </div>
    <div style="font-size:11px;padding:2px 8px;border-radius:10px;background:${color}22;color:${color};border:1px solid ${color};display:inline-block;margin-bottom:8px">${o.is_nna?'⚡ NNA Contract':'🔌 Network Node'}</div>
    <table style="width:100%;font-size:12px;border-collapse:collapse">
      ${rows.map(([k, v]) => `<tr><td style="color:#718096;padding:3px 6px 3px 0;vertical-align:top">${escHtml(k)}</td><td style="color:#e2e8f0;padding:3px 0">${escHtml(String(v))}</td></tr>`).join('')}
    </table>
    <button id="nna-detail-close" style="margin-top:10px;background:#2d3748;color:#e2e8f0;border:none;padding:4px 12px;border-radius:6px;cursor:pointer">Close</button>
  `;
  document.getElementById('nna-fav-btn')?.addEventListener('click', () => _nnaToggleFav(o));
  document.getElementById('nna-detail-close')?.addEventListener('click', () => { el.style.display = 'none'; });
}

async function _nnaToggleFav(o) {
  if (o.is_favourite) {
    await fetch(`http://127.0.0.1:${API_PORT}/nna/favourites/${o.id}`, {method:'DELETE'});
    o.is_favourite = false;
  } else {
    await fetch(`http://127.0.0.1:${API_PORT}/nna/favourites/${o.id}`, {method:'POST'});
    o.is_favourite = true;
  }
  const idx = _nnaData.findIndex(x=>x.id===o.id);
  if (idx>=0) _nnaData[idx].is_favourite = o.is_favourite;
  _nnaRender();
  _nnaShowDetail(o);
}

// ── Social / LinkedIn Post Approval ──────────────────────────────────────────

let _socialDrafts     = [];
let _socialFilter     = 'all';
let _socialInited     = false;

function initSocial() {
  if (_socialInited) {
    _socialLoadDrafts();
    _socialCheckLinkedIn();
    return;
  }
  _socialInited = true;

  // Filter bar
  document.querySelectorAll('.social-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.social-filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _socialFilter = btn.dataset.status;
      _socialRender();
    });
  });

  // Generate button
  document.getElementById('social-generate-btn')?.addEventListener('click', _socialGenerate);

  // Custom vault draft button
  document.getElementById('social-custom-draft-btn')?.addEventListener('click', _socialCustomDraft);

  // Allow Enter key in subject input
  document.getElementById('social-subject-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') _socialCustomDraft();
  });

  // LinkedIn connect button
  document.getElementById('social-li-connect-btn')?.addEventListener('click', _socialConnectLinkedIn);

  // Listen for OAuth popup message
  window.addEventListener('message', (e) => {
    if (e.data === 'linkedin_auth_ok') _socialCheckLinkedIn();
  });

  _socialLoadDrafts();
  _socialCheckLinkedIn();
}

async function _socialLoadDrafts() {
  try {
    const res  = await fetch(`http://127.0.0.1:${API_PORT}/api/social/drafts`);
    const data = await res.json();
    _socialDrafts = data.drafts || [];
    _socialRender();

    const pending = _socialDrafts.filter(d => d.status === 'pending').length;
    document.getElementById('social-status-text').textContent =
      _socialDrafts.length === 0
        ? 'No drafts yet — click "Generate Today\'s Drafts" to start'
        : `${_socialDrafts.length} drafts · ${pending} pending review`;
  } catch (e) {
    document.getElementById('social-status-text').textContent = 'Could not load drafts';
  }
}

function _socialRender() {
  const grid = document.getElementById('social-drafts-grid');
  const visible = _socialFilter === 'all'
    ? _socialDrafts
    : _socialDrafts.filter(d => d.status === _socialFilter);

  if (visible.length === 0) {
    grid.innerHTML = `<div class="social-empty">
      ${_socialFilter === 'all' ? 'No drafts yet. Click <strong>⚡ Generate Today\'s Drafts</strong> to fetch news and create posts.' : `No ${_socialFilter} posts.`}
    </div>`;
    return;
  }

  grid.innerHTML = visible.map(d => _socialCardHTML(d)).join('');

  // Bind card actions
  grid.querySelectorAll('[data-action]').forEach(el => {
    el.addEventListener('click', async (e) => {
      const action  = el.dataset.action;
      const draftId = el.dataset.id;
      if      (action === 'approve')  await _socialApproveDraft(draftId);
      else if (action === 'reject')   await _socialRejectDraft(draftId);
      else if (action === 'post')     await _socialPostDraft(draftId);
      else if (action === 'delete')   await _socialDeleteDraft(draftId);
      else if (action === 'edit')     _socialEditDraft(draftId);
    });
  });

  // Save edits on blur
  grid.querySelectorAll('.social-post-textarea').forEach(ta => {
    ta.addEventListener('blur', async () => {
      await _socialPatchDraft(ta.dataset.id, { post_text: ta.value });
    });
  });
}

function _socialCardHTML(d) {
  const statusLabel = { pending: '⏳ Pending', approved: '✅ Approved', rejected: '❌ Rejected', posted: '🚀 Posted' };
  const statusClass = `social-status-${d.status}`;
  const dateStr     = d.created_at ? new Date(d.created_at).toLocaleDateString('en-AU', { day:'numeric', month:'short' }) : '';
  const postedStr   = d.posted_at  ? ` · Posted ${new Date(d.posted_at).toLocaleDateString('en-AU', { day:'numeric', month:'short' })}` : '';
  const imgTag      = d.image_path
    ? `<img class="social-card-img" src="http://127.0.0.1:${API_PORT}/api/social/image/${d.id}" alt="AI image" loading="lazy">`
    : `<div class="social-card-img-placeholder">🖼️ No image</div>`;

  const actionBtns = (() => {
    if (d.status === 'pending') return `
      <button class="social-btn-approve" data-action="approve" data-id="${d.id}">✅ Approve</button>
      <button class="social-btn-reject"  data-action="reject"  data-id="${d.id}">❌ Reject</button>`;
    if (d.status === 'approved') return `
      <button class="social-btn-post"   data-action="post"   data-id="${d.id}">🚀 Post to LinkedIn</button>
      <button class="social-btn-reject" data-action="reject" data-id="${d.id}">❌ Reject</button>`;
    if (d.status === 'rejected') return `
      <button class="social-btn-approve" data-action="approve" data-id="${d.id}">↩️ Restore</button>`;
    if (d.status === 'posted') return `<span class="social-posted-tag">🚀 Live on LinkedIn</span>`;
    return '';
  })();

  return `
  <div class="social-card ${statusClass}">
    <div class="social-card-top">
      ${imgTag}
      <div class="social-card-meta">
        <span class="social-source-tag">${d.source_name || ''} · ${d.region || ''}</span>
        <span class="social-date-tag">${dateStr}${postedStr}</span>
        <span class="social-status-tag ${statusClass}">${statusLabel[d.status] || d.status}</span>
      </div>
    </div>
    <div class="social-card-source-title">
      <a href="${d.source_link}" target="_blank" rel="noopener noreferrer">${d.source_title || ''}</a>
    </div>
    <textarea class="social-post-textarea" data-id="${d.id}" ${d.status === 'posted' ? 'readonly' : ''}>${d.post_text || ''}</textarea>
    <div class="social-card-actions">
      ${actionBtns}
      <button class="social-btn-delete" data-action="delete" data-id="${d.id}" title="Delete draft">🗑</button>
    </div>
  </div>`;
}

async function _socialPatchDraft(draftId, updates) {
  await fetch(`http://127.0.0.1:${API_PORT}/api/social/drafts/${draftId}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates)
  });
  const idx = _socialDrafts.findIndex(d => d.id === draftId);
  if (idx !== -1) Object.assign(_socialDrafts[idx], updates);
}

async function _socialApproveDraft(draftId) {
  await _socialPatchDraft(draftId, { status: 'approved' });
  _socialRender();
}
async function _socialRejectDraft(draftId) {
  await _socialPatchDraft(draftId, { status: 'rejected' });
  _socialRender();
}
async function _socialDeleteDraft(draftId) {
  if (!confirm('Delete this draft permanently?')) return;
  await fetch(`http://127.0.0.1:${API_PORT}/api/social/drafts/${draftId}`, { method: 'DELETE' });
  _socialDrafts = _socialDrafts.filter(d => d.id !== draftId);
  _socialRender();
}
async function _socialPostDraft(draftId) {
  const badge = document.querySelector(`[data-action="post"][data-id="${draftId}"]`);
  if (badge) badge.textContent = '⏳ Posting…';
  try {
    const res  = await fetch(`http://127.0.0.1:${API_PORT}/api/social/linkedin/post/${draftId}`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      await _socialPatchDraft(draftId, { status: 'posted', linkedin_id: data.linkedin_id });
      _socialRender();
    } else {
      alert(`Post failed: ${data.detail || data.error || 'Unknown error'}`);
      if (badge) badge.textContent = '🚀 Post to LinkedIn';
    }
  } catch (e) {
    alert(`Post error: ${e.message}`);
    if (badge) badge.textContent = '🚀 Post to LinkedIn';
  }
}

async function _socialGenerate() {
  const spinner = document.getElementById('social-spinner');
  const btn     = document.getElementById('social-generate-btn');
  spinner.classList.remove('hidden');
  btn.disabled = true;
  try {
    const res  = await fetch(`http://127.0.0.1:${API_PORT}/api/social/generate`, { method: 'POST' });
    const data = await res.json();
    if (data.error) { alert(`Generation failed: ${data.error}`); return; }
    await _socialLoadDrafts();
  } catch (e) {
    alert(`Error: ${e.message}`);
  } finally {
    spinner.classList.add('hidden');
    btn.disabled = false;
  }
}

async function _socialCustomDraft() {
  const input   = document.getElementById('social-subject-input');
  const btn     = document.getElementById('social-custom-draft-btn');
  const spinner = document.getElementById('social-spinner');
  const subject = input.value.trim();
  if (!subject) { input.focus(); return; }

  spinner.classList.remove('hidden');
  btn.disabled = true;
  const origText = btn.textContent;
  btn.textContent = '⏳ Searching vault + drafting…';

  try {
    const res  = await fetch(`http://127.0.0.1:${API_PORT}/api/social/generate-custom`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subject }),
    });
    const data = await res.json();
    if (data.error || !data.draft) {
      alert(`Draft failed: ${data.detail || data.error || 'Unknown error'}`);
      return;
    }
    input.value = '';
    // Switch filter to "all" so the new draft is visible
    document.querySelectorAll('.social-filter-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('.social-filter-btn[data-status="all"]').classList.add('active');
    _socialFilter = 'all';
    await _socialLoadDrafts();
  } catch (e) {
    alert(`Error: ${e.message}`);
  } finally {
    spinner.classList.add('hidden');
    btn.disabled = false;
    btn.textContent = origText;
  }
}

async function _socialCheckLinkedIn() {
  const badge = document.getElementById('social-li-badge');
  const btn   = document.getElementById('social-li-connect-btn');
  try {
    const res  = await fetch(`http://127.0.0.1:${API_PORT}/api/social/linkedin/status`);
    const data = await res.json();
    if (data.connected) {
      badge.textContent = `● ${data.name || 'Connected'}`;
      badge.className   = 'li-badge connected';
      btn.textContent   = 'Reconnect';
    } else {
      badge.textContent = '● Not connected';
      badge.className   = 'li-badge disconnected';
      btn.textContent   = 'Connect LinkedIn';
    }
  } catch { /* backend not up yet */ }
}

async function _socialConnectLinkedIn() {
  try {
    const res  = await fetch(`http://127.0.0.1:${API_PORT}/api/social/linkedin/auth`);
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    // Open OAuth in a small popup window
    window.open(data.auth_url, 'linkedin_oauth',
      'width=600,height=700,menubar=no,toolbar=no,location=yes');
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────────
// ── Project Workbenches ───────────────────────────────────────────────────────
const PROJECT_PATHS = {
  lanteri: '/Users/haimptasznik/Desktop/HaimOS/02_Projects/Grants/Lanteri Grapes Farm/data_workbench.html',
};
const PROJECT_TITLES = {
  lanteri: '🍇 Lanteri Grapes Farm — Energy Workbench',
};

function openProjectWorkbench(key) {
  const path = PROJECT_PATHS[key];
  if (!path) return;
  const grid = document.getElementById('projects-grid');
  const wrapper = document.getElementById('project-webview-wrapper');
  const wv = document.getElementById('project-webview');
  const title = document.getElementById('project-webview-title');
  if (grid) grid.style.display = 'none';
  if (wrapper) wrapper.style.display = 'flex';
  if (title) title.textContent = PROJECT_TITLES[key] || key;
  if (wv) wv.src = `file://${path}`;
}

function closeProjectWorkbench() {
  const grid = document.getElementById('projects-grid');
  const wrapper = document.getElementById('project-webview-wrapper');
  const wv = document.getElementById('project-webview');
  if (grid) grid.style.display = 'flex';
  if (wrapper) wrapper.style.display = 'none';
  if (wv) wv.src = 'about:blank';
}

window.openProjectWorkbench = openProjectWorkbench;
window.closeProjectWorkbench = closeProjectWorkbench;

function _trStatus(msg, isError = false) {
  const el = document.getElementById('tr-status');
  if (!el) return;
  el.textContent = msg;
  el.style.color = isError ? '#f87171' : '#94a3b8';
}

function _trRenderCards(summarySection) {
  const container = document.getElementById('tr-summary-cards');
  if (!container) return;

  if (!summarySection || summarySection.status !== 'ok') {
    container.innerHTML = '<div style="color:#718096">Summary unavailable.</div>';
    return;
  }

  const summary = summarySection.summary || {};
  const entries = [
    ['Scope', summary.calibration_scope || '—'],
    ['Rows Backtested', summary.rows_backtested ?? '—'],
    ['Weighted Score', summary.weighted_score_mean ?? summary.weighted_score ?? '—'],
    ['MAPE (Actual)', summary.mape_actual_per_unit_mean ?? summary.mape_actual_per_unit ?? '—'],
    ['MAPE (Price)', summary.mape_clearing_price_mean ?? summary.mape_clearing_price ?? '—'],
  ];

  container.innerHTML = entries.map(([label, value]) => `
    <div style="background:#1e2433;border:1px solid #2d3748;border-radius:8px;padding:10px 12px">
      <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px">${label}</div>
      <div style="font-size:16px;color:#e2e8f0;font-weight:600;margin-top:4px">${value}</div>
    </div>
  `).join('');
}

function _trRenderMarketCards(correlation, trends, backtest, arbitrage) {
  const container = document.getElementById('tr-market-cards');
  if (!container) return;

  const corrVal = correlation?.pearson?.fill_rate?.clearing_price;
  const pairs = backtest?.pairs_evaluated;
  const hit = backtest?.overall_hit_rate;
  const uplift = backtest?.uplift_vs_baseline_pct;
  const trendCount = trends?.products_with_trend;
  const grossTotal = arbitrage?.gross_total_edge_aud;
  const grossLong = arbitrage?.gross_long_edge_aud;
  const grossShort = arbitrage?.gross_short_edge_aud;

  const entries = [
    ['Fill↔Price Corr', corrVal != null ? Number(corrVal).toFixed(3) : '—'],
    ['Trend Products', trendCount ?? '—'],
    ['Backtest Pairs', pairs ?? '—'],
    ['Hit Rate', hit != null ? `${(Number(hit) * 100).toFixed(1)}%` : '—'],
    ['Uplift vs Baseline', uplift != null ? `${Number(uplift).toFixed(2)}%` : '—'],
    ['Gross Arb Edge', grossTotal != null ? _trFormatMoney(grossTotal) : '—'],
    ['Long Edge', grossLong != null ? _trFormatMoney(grossLong) : '—'],
    ['Short Edge', grossShort != null ? _trFormatMoney(grossShort) : '—'],
  ];

  container.innerHTML = entries.map(([label, value]) => `
    <div style="background:#151b24;border:1px solid #2d3748;border-radius:8px;padding:10px 12px">
      <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px">${label}</div>
      <div style="font-size:16px;color:#e2e8f0;font-weight:600;margin-top:4px">${value}</div>
    </div>
  `).join('');
}

function _trRenderTable(tableId, section) {
  const table = document.getElementById(tableId);
  if (!table) return;

  if (!section || section.status !== 'ok' || !section.rows?.length) {
    table.innerHTML = '<tbody><tr><td style="color:#718096;padding:8px">No data</td></tr></tbody>';
    return;
  }

  const columns = Object.keys(section.rows[0]);
  const head = `
    <thead>
      <tr>${columns.map(col => `<th style="text-align:left;padding:6px;border-bottom:1px solid #2d3748;color:#94a3b8">${col}</th>`).join('')}</tr>
    </thead>
  `;
  const body = `
    <tbody>
      ${section.rows.map(row => `<tr>${columns.map(col => `<td style="padding:6px;border-bottom:1px solid #1f2937;color:#e2e8f0">${row[col] ?? ''}</td>`).join('')}</tr>`).join('')}
    </tbody>
  `;
  table.innerHTML = head + body;
}

function _trFormatMoney(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const num = Number(value);
  return num >= 0 ? num.toLocaleString('en-AU', { maximumFractionDigits: 2 }) : `-${Math.abs(num).toLocaleString('en-AU', { maximumFractionDigits: 2 })}`;
}

function _trFormatPct(value, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toFixed(digits)}%`;
}

function _trRecommendationTone(label) {
  if (label === 'BUY') return { bg: '#12351f', fg: '#76e4b8', border: '#1e7a45' };
  if (label === 'HOLD') return { bg: '#2b240f', fg: '#f7c948', border: '#8a6d1d' };
  if (label === 'AVOID') return { bg: '#36161a', fg: '#ff8f8f', border: '#a34949' };
  return { bg: '#1f2733', fg: '#a8c5ff', border: '#40506b' };
}

function _trQuarterProgressHtml(progress) {
  const pct = Math.max(0, Math.min(100, Number(progress) || 0));
  return `
    <div style="display:flex;align-items:center;gap:8px;min-width:120px">
      <div style="flex:1;height:8px;background:#111827;border:1px solid #2d3748;border-radius:999px;overflow:hidden">
        <div style="height:100%;width:${pct}%;background:linear-gradient(90deg,#3b82f6,#8b5cf6)"></div>
      </div>
      <span style="font-size:11px;color:#cbd5e1;min-width:42px;text-align:right">${pct.toFixed(1)}%</span>
    </div>`;
}

function _trRenderProducts(section) {
  const table = document.getElementById('tr-products-table');
  if (!table) return;

  if (!section || section.status !== 'ok' || !section.rows?.length) {
    table.innerHTML = '<tbody><tr><td style="color:#718096;padding:10px">No data</td></tr></tbody>';
    return;
  }

  const rows = section.rows;
  const head = `
    <thead>
      <tr>
        <th style="text-align:left;padding:10px 8px;border-bottom:1px solid #2d3748;color:#94a3b8">Product</th>
        <th style="text-align:left;padding:10px 8px;border-bottom:1px solid #2d3748;color:#94a3b8">Market @ Start</th>
        <th style="text-align:left;padding:10px 8px;border-bottom:1px solid #2d3748;color:#94a3b8">Quarter</th>
        <th style="text-align:left;padding:10px 8px;border-bottom:1px solid #2d3748;color:#94a3b8">Into Quarter</th>
        <th style="text-align:left;padding:10px 8px;border-bottom:1px solid #2d3748;color:#94a3b8">Fair Value</th>
        <th style="text-align:left;padding:10px 8px;border-bottom:1px solid #2d3748;color:#94a3b8">Valuation</th>
        <th style="text-align:left;padding:10px 8px;border-bottom:1px solid #2d3748;color:#94a3b8">Call</th>
      </tr>
    </thead>
  `;

  const body = `
    <tbody>
      ${rows.map(row => {
        const tone = _trRecommendationTone(row.recommendation);
        const market = Number(row.market_price_start_qtr_aud ?? row.current_value_per_unit_aud ?? 0);
        const fair = Number(row.fair_value_per_unit_aud ?? 0);
        const premium = row.fair_premium_pct ?? ((market > 0 ? ((fair - market) / market) * 100 : 0));
        const share = row.market_share_of_fair_pct ?? ((fair > 0 ? market / fair * 100 : 0));
        const directionText = row.direction_label || `${row.from_region} → ${row.to_region || '—'}`;
        return `
          <tr style="border-bottom:1px solid #1f2937">
            <td style="padding:12px 8px;vertical-align:top;min-width:220px">
              <div style="font-weight:700;color:#e2e8f0;font-size:13px">${row.interconnector} · T${row.tranche_no}</div>
              <div style="font-size:11px;color:#94a3b8;margin-top:3px">${row.contract_id} · ${directionText}</div>
              <div style="font-size:10px;color:#64748b;margin-top:4px">${row.source_file || ''}</div>
            </td>
            <td style="padding:12px 8px;vertical-align:top;white-space:nowrap">
              <div style="font-size:15px;font-weight:700;color:#f8fafc">${_trFormatMoney(market)}</div>
              <div style="font-size:11px;color:#94a3b8">per unit</div>
            </td>
            <td style="padding:12px 8px;vertical-align:top;white-space:nowrap">
              <div style="font-size:14px;font-weight:700;color:#cbd5e1">${row.quarter}</div>
              <div style="font-size:11px;color:#94a3b8">${row.quarter_progress_pct != null ? _trQuarterProgressHtml(row.quarter_progress_pct) : '—'}</div>
            </td>
            <td style="padding:12px 8px;vertical-align:top;white-space:nowrap">
              <div style="font-size:14px;font-weight:700;color:#e2e8f0">${_trFormatPct(row.quarter_progress_pct, 1)}</div>
              <div style="font-size:11px;color:#94a3b8">of quarter elapsed</div>
            </td>
            <td style="padding:12px 8px;vertical-align:top;white-space:nowrap">
              <div style="font-size:15px;font-weight:700;color:#76e4b8">${_trFormatMoney(fair)}</div>
              <div style="font-size:11px;color:#94a3b8">${_trFormatMoney(row.fair_value_total_aud)} total</div>
            </td>
            <td style="padding:12px 8px;vertical-align:top;min-width:190px">
              <div style="display:flex;align-items:center;gap:8px;justify-content:space-between">
                <span style="font-size:11px;color:#94a3b8">${_trFormatPct(share, 1)} of fair</span>
                <span style="font-size:11px;color:#94a3b8">${_trFormatPct(premium, 1)} premium</span>
              </div>
              <div style="margin-top:6px;height:8px;background:#111827;border:1px solid #2d3748;border-radius:999px;overflow:hidden">
                <div style="height:100%;width:${Math.max(0, Math.min(100, share))}%;background:linear-gradient(90deg,#10b981,#3b82f6)"></div>
              </div>
              <div style="font-size:10px;color:#64748b;margin-top:4px">${row.recommendation_reason || ''}</div>
            </td>
            <td style="padding:12px 8px;vertical-align:top;white-space:nowrap">
              <div style="display:inline-flex;align-items:center;padding:4px 10px;border-radius:999px;background:${tone.bg};color:${tone.fg};border:1px solid ${tone.border};font-weight:800;font-size:11px;letter-spacing:.4px">${row.recommendation || 'WATCH'}</div>
              <div style="font-size:10px;color:#94a3b8;margin-top:6px">${row.source_status || ''}</div>
            </td>
          </tr>
        `;
      }).join('')}
    </tbody>
  `;

  table.innerHTML = head + body;
}

async function refreshTransmissionRightsDashboard() {
  const base = 'http://127.0.0.1:8000';
  _trStatus('Loading data…');
  try {
    const [bestBuyRes, sellRes, corrRes, trendRes, backtestRes, arbitrageRes] = await Promise.all([
      fetch(`${base}/ux/market/best-buy-options?limit=50&min_confidence=0.35&min_edge_pct=2&max_participation_pct=10`),
      fetch(`${base}/ux/market/sell-quarter?min_confidence=0.35&min_edge_pct=2&max_participation_pct=10`),
      fetch(`${base}/ux/market/correlations`),
      fetch(`${base}/ux/market/trends`),
      fetch(`${base}/ux/market/backtest`),
      fetch(`${base}/ux/market/arbitrage?limit=50`),
    ]);

    const failed = [
      ['best-buy-options', bestBuyRes],
      ['sell-quarter', sellRes],
      ['correlations', corrRes],
      ['trends', trendRes],
      ['backtest', backtestRes],
      ['arbitrage', arbitrageRes],
    ].filter(([, res]) => !res.ok);

    if (failed.length) {
      const details = failed.map(([name, res]) => `${name}:${res.status}`).join(', ');
      throw new Error(`API errors: ${details}`);
    }

    const bestBuy = await bestBuyRes.json();
    const sellQuarter = await sellRes.json();
    const correlation = await corrRes.json();
    const trends = await trendRes.json();
    const backtest = await backtestRes.json();
    const arbitrage = await arbitrageRes.json();

    _trRenderOpportunitiesTables(bestBuy);
    _trRenderSellQuarterTables(sellQuarter);
    _trRenderAnalyticsTables(correlation, trends, backtest, arbitrage);
    updatePnLStrategy();

    _trStatus(`Loaded ${bestBuy.count || 0} opportunities`);
  } catch (error) {
    _trStatus(`Load failed: ${error.message}`, true);
    _trRenderOpportunitiesTables(null);
    _trRenderSellQuarterTables(null);
  }
}

function _trCalcRow(item) {
  const spend     = Number(item.suggested_spend_aud  || 0);
  const edge      = Number(item.expected_edge_aud    || 0);
  const conf      = Number(item.confidence           || 0);
  const riskUnit  = Number(item.risk_per_unit_aud    || 0);
  const units     = Number(item.suggested_units      || 0);
  const projProfit  = Math.round(edge * conf);            // confidence-weighted projected profit
  const capitalAtRisk = Math.round(riskUnit * units);     // max loss scenario (stop loss * units)
  const rorc = capitalAtRisk > 0 ? (projProfit / capitalAtRisk) : 0; // return on risked capital
  return { spend, edge, conf, projProfit, capitalAtRisk, rorc };
}

function _trRenderOpportunitiesTables(data) {
  const container = document.getElementById('tr-opportunities-container');
  if (!container) return;

  window._trCurrentBestBuys = data?.best_buys || [];
  window._trQuarterSummaries = data?.quarter_summaries || [];
  window._trYearSummaries = data?.year_summaries || [];

  if (!data || data.status !== 'ok' || !data.best_buys?.length) {
    container.innerHTML = '<div style="color:#718096;text-align:center;padding:40px;font-size:14px">No buy opportunities found.</div>';
    return;
  }

  // Group by year then by quarter
  const byYear = {};
  const quarterSummaryByQuarter = Object.fromEntries((data.quarter_summaries || []).map(item => [item.quarter, item]));
  data.best_buys.forEach(item => {
    const year = (item.quarter || 'Unknown').substring(1, 5);
    const qtr  = item.quarter || 'Unknown';
    if (!byYear[year]) byYear[year] = {};
    if (!byYear[year][qtr]) byYear[year][qtr] = [];
    byYear[year][qtr].push(item);
  });

  // Grand totals
  let grandSpend = 0, grandEdge = 0, grandProfit = 0, grandRisk = 0;
  const sortedYears = Object.keys(byYear).sort();

  const TH = (label, right = false) =>
    `<th style="text-align:${right?'right':'left'};padding:10px 8px;color:#94a3b8;font-weight:600;white-space:nowrap">${label}</th>`;

  const subtotalRow = (label, spend, edge, profit, risk, rorc, bg = '#131d2b') => {
    const rorColor = rorc >= 1 ? '#76e4b8' : rorc >= 0.5 ? '#fbbf24' : '#f87171';
    return `
      <tr style="background:${bg};border-top:2px solid #3d4758;font-weight:700">
        <td colspan="4" style="padding:10px 8px;color:#94a3b8;font-style:italic">${label}</td>
        <td style="padding:10px 8px;color:#cbd5e1;text-align:right">${_trFormatMoney(spend)}</td>
        <td style="padding:10px 8px;text-align:right"></td>
        <td style="padding:10px 8px;color:#76e4b8;text-align:right">${_trFormatMoney(edge)}</td>
        <td style="padding:10px 8px;color:#10b981;text-align:right">${_trFormatMoney(profit)}</td>
        <td style="padding:10px 8px;color:#f87171;text-align:right">${_trFormatMoney(risk)}</td>
        <td style="padding:10px 8px;text-align:right"></td>
        <td style="padding:10px 8px;color:${rorColor};text-align:right;font-size:14px">${(rorc * 100).toFixed(1)}%</td>
        <td colspan="4"></td>
      </tr>
    `;
  };

  const yearBlocks = sortedYears.map(year => {
    const quarters = Object.keys(byYear[year]).sort();
    let yearSpend = 0, yearEdge = 0, yearProfit = 0, yearRisk = 0;
    const yearSummary = (data.year_summaries || []).find(item => item.year === year);

    const quarterSections = quarters.map(qtr => {
      const items = byYear[year][qtr];
      const quarterSummary = quarterSummaryByQuarter[qtr] || {};
      let qSpend = 0, qEdge = 0, qProfit = 0, qRisk = 0;

      const rows = items.map(item => {
        const allIdx = window._trCurrentBestBuys.findIndex(x => x.product_id === item.product_id);
        const { spend, edge, conf, projProfit, capitalAtRisk, rorc } = _trCalcRow(item);
        qSpend += spend; qEdge += edge; qProfit += projProfit; qRisk += capitalAtRisk;
        const edgePct  = Number(item.delta_edge_pct || 0).toFixed(1);
        const confPct  = Math.round(conf * 100);
        const rorColor = rorc >= 1 ? '#76e4b8' : rorc >= 0.5 ? '#fbbf24' : '#f87171';
        return `
          <tr style="border-bottom:1px solid #1f2937" onmouseover="this.style.background='#1f2d3d'" onmouseout="this.style.background=''">
            <td style="padding:10px 8px;color:#94a3b8">${item.quarter}</td>
            <td style="padding:10px 8px;color:#cbd5e1;font-weight:600">${item.interconnector}</td>
            <td style="padding:10px 8px;color:#94a3b8">${item.direction}</td>
            <td style="padding:10px 8px;color:#60a5fa;text-align:right">${item.suggested_units}</td>
            <td style="padding:10px 8px;color:#cbd5e1;text-align:right">${_trFormatMoney(spend)}</td>
            <td style="padding:10px 8px;color:#10b981;text-align:right;font-weight:700">${edgePct}%</td>
            <td style="padding:10px 8px;color:#76e4b8;text-align:right">${_trFormatMoney(edge)}</td>
            <td style="padding:10px 8px;color:#34d399;text-align:right;font-weight:700">${_trFormatMoney(projProfit)}</td>
            <td style="padding:10px 8px;color:#f87171;text-align:right">${_trFormatMoney(capitalAtRisk)}</td>
            <td style="padding:10px 8px;color:#fbbf24;text-align:right">${confPct}%</td>
            <td style="padding:10px 8px;color:${rorColor};text-align:right;font-weight:700">${(rorc * 100).toFixed(1)}%</td>
            <td style="padding:10px 8px;text-align:center">
              <button onclick="openTRDetailsModal(${allIdx})" style="background:#3b82f6;color:#fff;border:none;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px;font-weight:600">Details</button>
            </td>
          </tr>`;
      }).join('');

      yearSpend += qSpend; yearEdge += qEdge; yearProfit += qProfit; yearRisk += qRisk;
      const qRorc = qRisk > 0 ? qProfit / qRisk : 0;
      const qRorcColor = qRorc >= 1 ? '#76e4b8' : qRorc >= 0.5 ? '#fbbf24' : '#f87171';
      const sellNowValue = quarterSummary.sell_now_value_aud ?? qSpend;

      return `
        <tr style="background:#10202d;border-top:1px solid #243445;border-bottom:1px solid #243445">
          <td colspan="15" style="padding:12px 10px">
            <div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;align-items:center">
              <div>
                <div style="font-size:14px;font-weight:700;color:#e2e8f0">${qtr} · ${items.length} trades</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px">${quarterSummary.notation || 'Sell entire quarter = exit the full proposed position at current market value.'}</div>
              </div>
              <div style="display:flex;flex-wrap:wrap;gap:16px;align-items:center">
                <div><div style="font-size:10px;color:#94a3b8">Spend</div><div style="font-weight:700;color:#cbd5e1">${_trFormatMoney(qSpend)}</div></div>
                <div><div style="font-size:10px;color:#94a3b8">Proj Profit</div><div style="font-weight:700;color:#34d399">${_trFormatMoney(qProfit)}</div></div>
                <div><div style="font-size:10px;color:#94a3b8">Capital at Risk</div><div style="font-weight:700;color:#f87171">${_trFormatMoney(qRisk)}</div></div>
                <div><div style="font-size:10px;color:#94a3b8">RORC</div><div style="font-weight:800;color:${qRorcColor}">${(qRorc * 100).toFixed(1)}%</div></div>
                <div><div style="font-size:10px;color:#94a3b8">Sell Now Value</div><div style="font-weight:700;color:#76e4b8">${_trFormatMoney(sellNowValue)}</div></div>
                <button onclick="openTRQuarterSummaryModal('${year}','${qtr}')" style="background:#10b981;color:#fff;border:none;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:11px;font-weight:700">Sell Whole Quarter</button>
              </div>
            </div>
          </td>
        </tr>
        ${rows}
        ${subtotalRow(`${qtr} Subtotal (${items.length} trades)`, qSpend, qEdge, qProfit, qRisk, qRorc, '#0d1a26')}`;
    }).join('');

    grandSpend += yearSpend; grandEdge += yearEdge; grandProfit += yearProfit; grandRisk += yearRisk;
    const yearRorc = yearRisk > 0 ? yearProfit / yearRisk : 0;
    const yearRorColor = yearRorc >= 1 ? '#76e4b8' : yearRorc >= 0.5 ? '#fbbf24' : '#f87171';

    return `
      <div style="background:#1e2433;border:1px solid #2d3748;border-radius:10px;overflow:hidden">
        <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:#141e2b;border-bottom:1px solid #2d3748">
          <div style="font-weight:700;color:#e2e8f0;font-size:15px">📅 ${year}</div>
          <div style="display:flex;gap:24px;font-size:12px">
            <span style="color:#94a3b8">Spend: <strong style="color:#cbd5e1">${_trFormatMoney(yearSpend)}</strong></span>
            <span style="color:#94a3b8">Proj Profit: <strong style="color:#34d399">${_trFormatMoney(yearProfit)}</strong></span>
            <span style="color:#94a3b8">Capital at Risk: <strong style="color:#f87171">${_trFormatMoney(yearRisk)}</strong></span>
            <span style="color:#94a3b8">RORC: <strong style="color:${yearRorColor};font-size:14px">${(yearRorc * 100).toFixed(1)}%</strong></span>
            <span style="color:#94a3b8">Sell Now: <strong style="color:#76e4b8">${_trFormatMoney(yearSummary?.total_suggested_spend_aud || yearSpend)}</strong></span>
          </div>
        </div>
        <div style="overflow-x:auto">
          <table style="width:100%;font-size:12px;border-collapse:collapse">
            <thead>
              <tr style="background:#0f1419;border-bottom:1px solid #3d4758">
                ${TH('Quarter')} ${TH('Interconnector')} ${TH('Direction')}
                ${TH('Units', true)} ${TH('Spend', true)} ${TH('Edge %', true)}
                ${TH('Expected Edge', true)} ${TH('Proj Profit', true)} ${TH('Capital at Risk', true)}
                ${TH('Confidence', true)} ${TH('RORC', true)}
                ${TH('Starts', true)} ${TH('Days', true)} ${TH('Intervals', true)}
                ${TH('', true)}
              </tr>
              <tr style="background:#0a1018;border-bottom:2px solid #3d4758">
                <td colspan="11" style="padding:4px 8px;font-size:10px;color:#64748b;font-style:italic">
                  ⚡ SRA pays every 5-min dispatch interval the interconnector flows your direction. ~288 intervals/day. Payment = max(0, RRP_from − RRP_to) per interval per unit.
                </td>
                <td style="padding:4px 8px;font-size:10px;color:#64748b;text-align:right;white-space:nowrap">in calendar</td>
                <td style="padding:4px 8px;font-size:10px;color:#64748b;text-align:right;white-space:nowrap">total</td>
                <td style="padding:4px 8px;font-size:10px;color:#64748b;text-align:right;white-space:nowrap">exp. paying</td>
                <td></td>
              </tr>
            </thead>
            <tbody>
              ${quarterSections}
            </tbody>
          </table>
        </div>
      </div>`;
  }).join('');

  // Grand total bar
  const grandRorc = grandRisk > 0 ? grandProfit / grandRisk : 0;
  const grandRorColor = grandRorc >= 1 ? '#76e4b8' : grandRorc >= 0.5 ? '#fbbf24' : '#f87171';
  const grandBar = `
    <div style="background:linear-gradient(135deg,#141e2b,#0f1419);border:2px solid #3d4758;border-radius:10px;padding:16px 20px;display:flex;flex-wrap:wrap;gap:24px;align-items:center">
      <div style="font-weight:700;color:#e2e8f0;font-size:16px;flex:0 0 auto">📊 Portfolio Total</div>
      <div style="flex:1;display:flex;flex-wrap:wrap;gap:20px;justify-content:flex-end">
        <div style="text-align:center"><div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px">Total Spend</div><div style="font-size:20px;color:#cbd5e1;font-weight:700">${_trFormatMoney(grandSpend)}</div></div>
        <div style="text-align:center"><div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px">Expected Edge</div><div style="font-size:20px;color:#76e4b8;font-weight:700">${_trFormatMoney(grandEdge)}</div></div>
        <div style="text-align:center"><div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px">Projected Profit</div><div style="font-size:20px;color:#34d399;font-weight:700">${_trFormatMoney(grandProfit)}</div></div>
        <div style="text-align:center"><div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px">Capital at Risk</div><div style="font-size:20px;color:#f87171;font-weight:700">${_trFormatMoney(grandRisk)}</div></div>
        <div style="text-align:center;background:#141e2b;border:2px solid ${grandRorColor};border-radius:8px;padding:8px 16px"><div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px">Return on Risked Capital</div><div style="font-size:26px;color:${grandRorColor};font-weight:800">${(grandRorc * 100).toFixed(1)}%</div></div>
      </div>
    </div>`;

  container.innerHTML = grandBar + '<div style="display:flex;flex-direction:column;gap:16px;margin-top:4px">' + yearBlocks + '</div>';
}

function _trRenderAnalyticsTables(correlation, trends, backtest, arbitrage) {
  // Render market cards
  const cardsContainer = document.getElementById('tr-analytics-cards');
  if (cardsContainer) {
    const corrVal = correlation?.pearson?.fill_rate?.clearing_price;
    const pairs = backtest?.pairs_evaluated;
    const hit = backtest?.overall_hit_rate;
    const uplift = backtest?.uplift_vs_baseline_pct;
    const trendCount = trends?.products_with_trend;
    const grossTotal = arbitrage?.gross_total_edge_aud;
    const grossLong = arbitrage?.gross_long_edge_aud;
    const grossShort = arbitrage?.gross_short_edge_aud;

    const entries = [
      ['Fill↔Price Corr', corrVal != null ? Number(corrVal).toFixed(3) : '—'],
      ['Trend Products', trendCount ?? '—'],
      ['Backtest Pairs', pairs ?? '—'],
      ['Hit Rate', hit != null ? `${(Number(hit) * 100).toFixed(1)}%` : '—'],
      ['Uplift vs Baseline', uplift != null ? `${Number(uplift).toFixed(2)}%` : '—'],
      ['Gross Arb Edge', grossTotal != null ? _trFormatMoney(grossTotal) : '—'],
      ['Long Edge', grossLong != null ? _trFormatMoney(grossLong) : '—'],
      ['Short Edge', grossShort != null ? _trFormatMoney(grossShort) : '—'],
    ];

    cardsContainer.innerHTML = entries.map(([label, value]) => `
      <div style="background:#151b24;border:1px solid #2d3748;border-radius:8px;padding:12px">
        <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px">${label}</div>
        <div style="font-size:16px;color:#e2e8f0;font-weight:600;margin-top:4px">${value}</div>
      </div>
    `).join('');
  }

  // Render correlation table
  _trRenderTable('tr-correlation-table', {
    status: correlation?.status || 'error',
    rows: (correlation?.interconnector || []).slice(0, 20),
  });

  // Render trend table
  _trRenderTable('tr-trend-table', {
    status: trends?.status || 'error',
    rows: (trends?.rows || []).slice(0, 20),
  });

  // Render backtest table
  _trRenderTable('tr-backtest-table', {
    status: backtest?.status || 'error',
    rows: backtest?.by_recommendation || [],
  });

  // Render arbitrage table
  _trRenderTable('tr-arbitrage-table', {
    status: arbitrage?.status || 'error',
    rows: (arbitrage?.top_opportunities || []).slice(0, 25).map(item => ({
      interconnector: item.interconnector,
      direction: item.direction_label || `${item.from_region || ''}→${item.to_region || ''}`,
      quarter: item.quarter,
      tranche_no: item.tranche_no,
      side: item.arbitrage_side,
      arb_per_unit_aud: item.arbitrage_per_unit_aud,
      arb_total_aud: item.arbitrage_total_aud,
      fair_premium_pct: item.fair_premium_pct,
      recommendation: item.recommendation,
    })),
  });
}

function _trRenderSellQuarterTables(data) {
  const container = document.getElementById('tr-sell-quarter-container');
  if (!container) return;

  window._trQuarterSummaries = data?.quarter_summaries || [];
  window._trYearSummaries = data?.year_summaries || [];

  if (!data || data.status !== 'ok' || !data.quarter_summaries?.length) {
    container.innerHTML = '<div style="color:#718096;text-align:center;padding:40px;font-size:14px">No quarter summaries available.</div>';
    return;
  }

  const byYear = {};
  data.quarter_summaries.forEach(item => {
    const year = item.year || (item.quarter || 'Unknown').substring(1, 5) || 'Unknown';
    if (!byYear[year]) byYear[year] = [];
    byYear[year].push(item);
  });

  const sortedYears = Object.keys(byYear).sort();

  container.innerHTML = `
    <div style="background:#111827;border:1px solid #2d3748;border-radius:8px;padding:14px;margin-bottom:16px">
      <div style="font-size:13px;color:#86efac;font-weight:700;margin-bottom:6px">📤 Sell Quarter View</div>
      <div style="font-size:12px;color:#a7f3d0;line-height:1.6">
        Use this tab to compare <strong>sell now value</strong> versus <strong>holding through the quarter</strong>. The table shows quarter-level PnL, capital at risk, and return on risked capital so you can decide whether to exit the whole quarter position now.
      </div>
    </div>
    ${sortedYears.map(year => {
      const items = byYear[year].sort((a, b) => String(a.quarter).localeCompare(String(b.quarter)));
      const totals = (data.year_summaries || []).find(item => item.year === year) || {};
      return `
        <div style="background:#1e2433;border:1px solid #2d3748;border-radius:10px;overflow:hidden">
          <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:#141e2b;border-bottom:1px solid #2d3748">
            <div style="font-weight:700;color:#e2e8f0;font-size:15px">📅 ${year}</div>
            <div style="display:flex;gap:20px;font-size:12px;flex-wrap:wrap;justify-content:flex-end">
              <span style="color:#94a3b8">Quarter Count: <strong style="color:#cbd5e1">${items.length}</strong></span>
              <span style="color:#94a3b8">Sell Now Total: <strong style="color:#76e4b8">${_trFormatMoney(totals.total_suggested_spend_aud || 0)}</strong></span>
              <span style="color:#94a3b8">Projected Profit: <strong style="color:#34d399">${_trFormatMoney(totals.total_projected_profit_aud || 0)}</strong></span>
              <span style="color:#94a3b8">RORC: <strong style="color:#fbbf24;font-size:14px">${Number(totals.return_on_risked_capital_pct || 0).toFixed(1)}%</strong></span>
            </div>
          </div>
          <div style="overflow-x:auto">
            <table style="width:100%;font-size:12px;border-collapse:collapse">
              <thead>
                <tr style="background:#0f1419;border-bottom:1px solid #3d4758">
                  <th style="text-align:left;padding:10px 8px;color:#94a3b8;font-weight:600">Quarter</th>
                  <th style="text-align:right;padding:10px 8px;color:#94a3b8;font-weight:600">Sell Now Value</th>
                  <th style="text-align:right;padding:10px 8px;color:#94a3b8;font-weight:600">Projected Profit</th>
                  <th style="text-align:right;padding:10px 8px;color:#94a3b8;font-weight:600">Capital at Risk</th>
                  <th style="text-align:right;padding:10px 8px;color:#94a3b8;font-weight:600">RORC</th>
                  <th style="text-align:left;padding:10px 8px;color:#94a3b8;font-weight:600">Notation</th>
                  <th style="text-align:center;padding:10px 8px;color:#94a3b8;font-weight:600">Action</th>
                </tr>
              </thead>
              <tbody>
                ${items.map(item => {
                  const rorc = Number(item.return_on_risked_capital_pct || 0) / 100;
                  const rorcColor = rorc >= 1 ? '#76e4b8' : rorc >= 0.5 ? '#fbbf24' : '#f87171';
                  return `
                    <tr style="border-bottom:1px solid #1f2937" onmouseover="this.style.background='#1f2d3d'" onmouseout="this.style.background=''">
                      <td style="padding:10px 8px;color:#cbd5e1;font-weight:600">${item.quarter}</td>
                      <td style="padding:10px 8px;color:#76e4b8;text-align:right;font-weight:700">${_trFormatMoney(item.sell_now_value_aud || item.exit_price_aud || 0)}</td>
                      <td style="padding:10px 8px;color:#34d399;text-align:right;font-weight:700">${_trFormatMoney(item.total_projected_profit_aud || item.projected_hold_pnl_aud || 0)}</td>
                      <td style="padding:10px 8px;color:#f87171;text-align:right">${_trFormatMoney(item.total_capital_at_risk_aud || 0)}</td>
                      <td style="padding:10px 8px;color:${rorcColor};text-align:right;font-weight:700">${Number(item.return_on_risked_capital_pct || 0).toFixed(1)}%</td>
                      <td style="padding:10px 8px;color:#94a3b8;font-size:11px;line-height:1.4">${item.sell_entire_quarter_note || item.notation || ''}</td>
                      <td style="padding:10px 8px;text-align:center">
                        <button onclick="openTRQuarterSummaryModal('${year}','${item.quarter}')" style="background:#10b981;color:#fff;border:none;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px;font-weight:600">Details</button>
                      </td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `;
    }).join('')}
  `;
}

function updatePnLStrategy() {
  const targetInput = document.getElementById('tr-investment-target');
  const targetAmount = parseFloat(targetInput.value) || 1000000;
  
  const best_buys = window._trCurrentBestBuys || [];
  if (!best_buys.length) {
    document.getElementById('tr-pnl-container').innerHTML = '<div style="color:#f87171">No opportunity data loaded</div>';
    return;
  }

  // Group by quarter and calculate totals
  const quarters = {};
  let totalSpend = 0;
  let totalProfit = 0;
  
  for (const item of best_buys) {
    const q = item.quarter;
    if (!quarters[q]) {
      quarters[q] = {
        quarter: q,
        trades: [],
        year: q.split('Q')[0].substring(1),
        quarter_start: item.quarter_start,
        quarter_end: item.quarter_end,
        total_spend: 0,
        total_profit: 0,
        total_risk: 0,
        trades_count: 0
      };
    }
    quarters[q].trades.push(item);
    quarters[q].total_spend += item.suggested_spend_aud || 0;
    quarters[q].total_profit += (item.expected_edge_aud || 0) * item.confidence;
    quarters[q].total_risk += item.suggested_spend_aud || 0;
    quarters[q].trades_count += 1;
  }

  // Sort quarters chronologically
  const sortedQuarters = Object.values(quarters).sort((a, b) => {
    const [aYear, aQtr] = [parseInt(a.year), parseInt(a.quarter.split('Q')[1])];
    const [bYear, bQtr] = [parseInt(b.year), parseInt(b.quarter.split('Q')[1])];
    return aYear - bYear || aQtr - bQtr;
  });

  const representativeQuarter = sortedQuarters.find(q => q.quarter_start && q.quarter_end);
  const representativeDays = representativeQuarter
    ? Math.max(0, Math.round((new Date(representativeQuarter.quarter_end) - new Date(representativeQuarter.quarter_start)) / (1000 * 60 * 60 * 24)))
    : 90;
  const representativeIntervals = representativeDays * 288;

  // Allocate target budget proportionally to spend opportunities
  const totalAvailableSpend = sortedQuarters.reduce((s, q) => s + q.total_spend, 0);
  const allocation = {};
  let allocatedTotal = 0;

  for (const q of sortedQuarters) {
    const proportion = q.total_spend / totalAvailableSpend;
    const allocatedBudget = Math.min(proportion * targetAmount, q.total_spend);
    allocation[q.quarter] = {
      ...q,
      allocated_budget: allocatedBudget,
      scaled_profit: (allocatedBudget / q.total_spend) * q.total_profit,
      rorc: allocatedBudget > 0 ? ((allocatedBudget / q.total_spend) * q.total_profit) / allocatedBudget * 100 : 0
    };
    allocatedTotal += allocatedBudget;
    totalProfit += allocation[q.quarter].scaled_profit;
  }

  // Group by year for summary
  const years = {};
  for (const q of Object.values(allocation)) {
    if (!years[q.year]) {
      years[q.year] = {
        year: q.year,
        quarters: [],
        year_spend: 0,
        year_profit: 0,
        year_rorc: 0
      };
    }
    years[q.year].quarters.push(q);
    years[q.year].year_spend += q.allocated_budget;
    years[q.year].year_profit += q.scaled_profit;
  }

  for (const y of Object.values(years)) {
    y.year_rorc = y.year_spend > 0 ? (y.year_profit / y.year_spend) * 100 : 0;
  }

  const quarterRows = Object.values(allocation);
  const avgQuarterRorc = quarterRows.length
    ? quarterRows.reduce((sum, quarter) => sum + (quarter.rorc || 0), 0) / quarterRows.length
    : 0;
  const portfolioRorc = allocatedTotal > 0 ? (totalProfit / allocatedTotal) * 100 : 0;

  // Render P&L table
  let html = `
    <div style="background:#1e2433;border:1px solid #2d3748;border-radius:8px;padding:16px">
      <div style="font-weight:600;color:#cbd5e1;margin-bottom:12px">Portfolio Allocation Summary</div>
      <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:16px">
        <div style="background:#0f1419;border:1px solid #3d4758;border-radius:6px;padding:12px">
          <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px">Total Allocation</div>
          <div style="font-size:18px;font-weight:600;color:#10b981;margin-top:4px">$${allocatedTotal.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}</div>
        </div>
        <div style="background:#0f1419;border:1px solid #3d4758;border-radius:6px;padding:12px">
          <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px">Expected Profit</div>
          <div style="font-size:18px;font-weight:600;color:#fbbf24;margin-top:4px">$${totalProfit.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}</div>
        </div>
        <div style="background:#0f1419;border:1px solid #3d4758;border-radius:6px;padding:12px">
          <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px">Portfolio RORC (All Quarters)</div>
          <div style="font-size:18px;font-weight:600;color:#60a5fa;margin-top:4px">${portfolioRorc.toFixed(1)}%</div>
        </div>
        <div style="background:#0f1419;border:1px solid #3d4758;border-radius:6px;padding:12px">
          <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px">Avg Quarter RORC</div>
          <div style="font-size:18px;font-weight:600;color:#a78bfa;margin-top:4px">${avgQuarterRorc.toFixed(1)}%</div>
        </div>
        <div style="background:#0f1419;border:1px solid #3d4758;border-radius:6px;padding:12px">
          <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px">Opportunity Gap</div>
          <div style="font-size:18px;font-weight:600;color:#f87171;margin-top:4px">$${(totalAvailableSpend - allocatedTotal).toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}</div>
        </div>
      </div>
    </div>
  `;

  // Year headers with totals
  const sortedYears = Object.values(years).sort((a, b) => parseInt(a.year) - parseInt(b.year));
  for (const year of sortedYears) {
    html += `
      <div style="background:#1e2433;border:1px solid #2d3748;border-radius:8px;padding:16px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <div style="font-weight:600;color:#cbd5e1;font-size:15px">${year.year} Quarters</div>
          <div style="display:flex;gap:16px;font-size:13px">
            <div><span style="color:#94a3b8">Spend:</span> <span style="color:#cbd5e1;font-weight:600">$${year.year_spend.toLocaleString('en-US', {minimumFractionDigits: 0})}</span></div>
            <div><span style="color:#94a3b8">Profit:</span> <span style="color:#fbbf24;font-weight:600">$${year.year_profit.toLocaleString('en-US', {minimumFractionDigits: 0})}</span></div>
            <div><span style="color:#94a3b8">RORC:</span> <span style="color:#60a5fa;font-weight:600">${year.year_rorc.toFixed(1)}%</span></div>
          </div>
        </div>

        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead>
            <tr style="border-bottom:1px solid #3d4758">
              <th style="text-align:left;padding:8px;color:#94a3b8">Quarter</th>
              <th style="text-align:left;padding:8px;color:#94a3b8">Profit Period</th>
              <th style="text-align:right;padding:8px;color:#94a3b8">Trades</th>
              <th style="text-align:right;padding:8px;color:#94a3b8">Budget Allocated</th>
              <th style="text-align:right;padding:8px;color:#94a3b8">Expected Profit</th>
              <th style="text-align:right;padding:8px;color:#94a3b8">Total Cash Earned</th>
              <th style="text-align:right;padding:8px;color:#94a3b8">RORC</th>
              <th style="text-align:center;padding:8px;color:#94a3b8">Settlement Detail</th>
            </tr>
          </thead>
          <tbody>
            ${year.quarters.map(q => {
              const startDate = new Date(q.quarter_start);
              const endDate = new Date(q.quarter_end);
              const days = Math.round((endDate - startDate) / (1000 * 60 * 60 * 24));
              const intervals = Math.round(days * 288);
              const profitStart = startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
              const profitEnd = endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
              const totalCashEarned = q.allocated_budget + q.scaled_profit;
              
              return `
                <tr style="border-bottom:1px solid #2d3748;background:#0f1419">
                  <td style="padding:8px;color:#cbd5e1;font-weight:500">${q.quarter}</td>
                  <td style="padding:8px;color:#cbd5e1;font-size:12px"><span style="background:#2d3748;padding:4px 8px;border-radius:4px">${profitStart} → ${profitEnd}</span></td>
                  <td style="text-align:right;padding:8px;color:#cbd5e1">${q.trades_count}</td>
                  <td style="text-align:right;padding:8px;color:#10b981;font-weight:500">$${q.allocated_budget.toLocaleString('en-US', {minimumFractionDigits: 0})}</td>
                  <td style="text-align:right;padding:8px;color:#fbbf24;font-weight:500">$${q.scaled_profit.toLocaleString('en-US', {minimumFractionDigits: 0})}</td>
                  <td style="text-align:right;padding:8px;color:#60a5fa;font-weight:600">$${totalCashEarned.toLocaleString('en-US', {minimumFractionDigits: 0})}</td>
                  <td style="text-align:right;padding:8px;color:#60a5fa;font-weight:500">${q.rorc.toFixed(1)}%</td>
                  <td style="text-align:center;padding:8px;font-size:11px;color:#94a3b8">${days} calendar days<br/>~${intervals.toLocaleString()} × 5-min intervals</td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  html += `
    <div style="background:#1e2433;border:1px solid #2d3748;border-radius:8px;padding:16px;margin-top:0">
      <div style="font-weight:600;color:#cbd5e1;margin-bottom:12px">How Profit Periods Work</div>
      <div style="color:#cbd5e1;line-height:1.6;font-size:13px">
        <p><strong>📅 Today (July 11, 2026):</strong> You pay $${allocatedTotal.toLocaleString('en-US', {minimumFractionDigits: 0})} upfront for all contracts listed above.</p>
        <p><strong>⚡ Profit Period:</strong> Each quarter has a defined <span style="background:#2d3748;padding:2px 6px;border-radius:3px">Profit Period</span> (e.g., <span style="color:#fbbf24">Jan 1 → Mar 31, 2027</span>). This is the exact timeframe during which you earn the expected profit through settlement payouts.</p>
        <p><strong>🔄 Settlement Cycles:</strong> During the profit period, power dispatch happens every 5 minutes (~${representativeIntervals.toLocaleString()} intervals per quarter). You get paid for each interval where power flows in your predicted direction. Not every interval pays—only directional flows (~85% on average).</p>
        <p><strong>💰 Daily Payouts:</strong> As intervals settle, you collect cash continuously throughout the profit period—not a lump sum at quarter-end. For C2027Q3 example: expect ~$${(Object.values(years)[0]?.quarters[0]?.scaled_profit ? Math.round(Object.values(years)[0].quarters[0].scaled_profit / 91) : 0).toLocaleString()}/day average.</p>
        <p><strong>✅ Total Return:</strong> After all profit periods complete, you'll have collected $${totalProfit.toLocaleString('en-US', {minimumFractionDigits: 0})} profit across all positions, representing a ${portfolioRorc.toFixed(1)}% return on your initial $${allocatedTotal.toLocaleString('en-US', {minimumFractionDigits: 0})} investment.</p>
      </div>
    </div>
  `;

  document.getElementById('tr-pnl-container').innerHTML = html;
  updateTRMonthlyCashflow();
}

window.updatePnLStrategy = updatePnLStrategy;

function updateTRMonthlyCashflow() {
  const container = document.getElementById('tr-cashflow-container');
  if (!container) return;

  const best_buys = window._trCurrentBestBuys || [];
  if (!best_buys.length) {
    container.innerHTML = '<div style="color:#f87171">No opportunity data loaded</div>';
    return;
  }

  const targetInput = document.getElementById('tr-investment-target');
  const targetAmount = parseFloat(targetInput?.value) || 1000000;

  const quarters = {};
  for (const item of best_buys) {
    const quarterCode = item.quarter;
    if (!quarters[quarterCode]) {
      quarters[quarterCode] = {
        quarter: quarterCode,
        quarter_start: item.quarter_start,
        quarter_end: item.quarter_end,
        total_spend: 0,
        total_profit: 0,
        end_month_key: item.quarter_end ? item.quarter_end.slice(0, 7) : null,
      };
    }
    quarters[quarterCode].total_spend += Number(item.suggested_spend_aud || 0);
    quarters[quarterCode].total_profit += Number(item.expected_edge_aud || 0) * Number(item.confidence || 0);
  }

  const quarterList = Object.values(quarters).filter(q => q.quarter_start && q.quarter_end);
  if (!quarterList.length) {
    container.innerHTML = '<div style="color:#f87171">No quarter date ranges available for cashflow model</div>';
    return;
  }

  const totalAvailableSpend = quarterList.reduce((sum, quarter) => sum + quarter.total_spend, 0);
  const allocatedQuarters = quarterList.map(quarter => {
    const proportion = totalAvailableSpend > 0 ? (quarter.total_spend / totalAvailableSpend) : 0;
    const allocatedBudget = Math.min(proportion * targetAmount, quarter.total_spend);
    const scaledProfit = quarter.total_spend > 0 ? (allocatedBudget / quarter.total_spend) * quarter.total_profit : 0;
    return {
      ...quarter,
      allocated_budget: allocatedBudget,
      scaled_profit: scaledProfit,
      start: new Date(`${quarter.quarter_start}T00:00:00`),
      end: new Date(`${quarter.quarter_end}T00:00:00`),
    };
  });

  const allocatedTotal = allocatedQuarters.reduce((sum, quarter) => sum + quarter.allocated_budget, 0);
  const totalProfit = allocatedQuarters.reduce((sum, quarter) => sum + quarter.scaled_profit, 0);

  const minStart = new Date(Math.min(...allocatedQuarters.map(quarter => quarter.start.getTime())));
  const maxEnd = new Date(Math.max(...allocatedQuarters.map(quarter => quarter.end.getTime())));
  const firstMonth = new Date(minStart.getFullYear(), minStart.getMonth(), 1);
  const lastMonth = new Date(maxEnd.getFullYear(), maxEnd.getMonth(), 1);

  const monthRows = [];
  for (let cursor = new Date(firstMonth); cursor <= lastMonth; cursor.setMonth(cursor.getMonth() + 1)) {
    const monthStart = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const monthEnd = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0);

    let principalDeployed = 0;
    let principalReturned = 0;
    let monthProfitInflow = 0;
    let activeQuarterCount = 0;

    if (`${monthStart.getFullYear()}-${String(monthStart.getMonth() + 1).padStart(2, '0')}` === `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}`) {
      principalDeployed = allocatedTotal;
    }

    for (const quarter of allocatedQuarters) {
      const overlapStart = new Date(Math.max(monthStart.getTime(), quarter.start.getTime()));
      const overlapEnd = new Date(Math.min(monthEnd.getTime(), quarter.end.getTime()));
      if (overlapStart <= overlapEnd) {
        activeQuarterCount += 1;
        const overlapDays = Math.floor((overlapEnd - overlapStart) / (1000 * 60 * 60 * 24)) + 1;
        const quarterDays = Math.floor((quarter.end - quarter.start) / (1000 * 60 * 60 * 24)) + 1;
        const monthShare = quarterDays > 0 ? (overlapDays / quarterDays) : 0;
        monthProfitInflow += quarter.scaled_profit * monthShare;
      }

      const monthKey = `${monthStart.getFullYear()}-${String(monthStart.getMonth() + 1).padStart(2, '0')}`;
      if (quarter.end_month_key === monthKey) {
        principalReturned += quarter.allocated_budget;
      }
    }

    monthRows.push({
      key: `${monthStart.getFullYear()}-${String(monthStart.getMonth() + 1).padStart(2, '0')}`,
      label: monthStart.toLocaleDateString('en-US', { month: 'short', year: 'numeric' }),
      principal_deployed: principalDeployed,
      principal_returned: principalReturned,
      month_profit_inflow: monthProfitInflow,
      cash_received: principalReturned + monthProfitInflow,
      active_quarters: activeQuarterCount,
      monthly_net_cashflow: monthProfitInflow + principalReturned - principalDeployed,
    });
  }

  const asOf = new Date();
  monthRows.unshift({
    key: `today-${asOf.getFullYear()}-${String(asOf.getMonth() + 1).padStart(2, '0')}`,
    label: `Today · ${asOf.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}`,
    principal_deployed: allocatedTotal,
    principal_returned: 0,
    month_profit_inflow: 0,
    cash_received: 0,
    active_quarters: 0,
    monthly_net_cashflow: -allocatedTotal,
  });

  let cumulativeProfit = 0;
  let cumulativePrincipalDeployed = 0;
  let cumulativePrincipalReturned = 0;
  let cumulativeNetCash = 0;
  for (const row of monthRows) {
    cumulativeProfit += row.month_profit_inflow;
    cumulativePrincipalDeployed += row.principal_deployed || 0;
    cumulativePrincipalReturned += row.principal_returned || 0;
    cumulativeNetCash += row.monthly_net_cashflow;
    row.cumulative_profit = cumulativeProfit;
    row.cumulative_principal_deployed = cumulativePrincipalDeployed;
    row.cumulative_principal_returned = cumulativePrincipalReturned;
    row.principal_remaining = Math.max(0, cumulativePrincipalDeployed - cumulativePrincipalReturned);
    row.cumulative_cash_received = cumulativePrincipalReturned + cumulativeProfit;
    row.cumulative_net_cash = cumulativeNetCash;
  }

  const maxAbsMonthly = Math.max(...monthRows.map(row => Math.abs(row.monthly_net_cashflow)), 1);

  container.innerHTML = `
    <div style="background:#1e2433;border:1px solid #2d3748;border-radius:8px;padding:16px;margin-bottom:16px">
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
        <div style="background:#0f1419;border:1px solid #3d4758;border-radius:6px;padding:12px" title="Total capital deployed upfront into transmission rights positions">
          <div style="font-size:11px;color:#94a3b8;text-transform:uppercase">Capital Invested</div>
          <div style="font-size:18px;font-weight:700;color:#f87171;margin-top:4px">$${allocatedTotal.toLocaleString('en-US', {maximumFractionDigits: 0})}</div>
        </div>
        <div style="background:#0f1419;border:1px solid #3d4758;border-radius:6px;padding:12px" title="Same as Capital Invested—the total amount returned through settlements and position exits over the forecast period">
          <div style="font-size:11px;color:#94a3b8;text-transform:uppercase">Capital Recovered</div>
          <div style="font-size:18px;font-weight:700;color:#10b981;margin-top:4px">$${allocatedTotal.toLocaleString('en-US', {maximumFractionDigits: 0})}</div>
        </div>
        <div style="background:#0f1419;border:1px solid #3d4758;border-radius:6px;padding:12px">
          <div style="font-size:11px;color:#94a3b8;text-transform:uppercase">Total Cash Received</div>
          <div style="font-size:18px;font-weight:700;color:#60a5fa;margin-top:4px">$${(allocatedTotal + totalProfit).toLocaleString('en-US', {maximumFractionDigits: 0})}</div>
        </div>
        <div style="background:#0f1419;border:1px solid #3d4758;border-radius:6px;padding:12px">
          <div style="font-size:11px;color:#94a3b8;text-transform:uppercase">Total Expected Profit</div>
          <div style="font-size:18px;font-weight:700;color:#10b981;margin-top:4px">$${totalProfit.toLocaleString('en-US', {maximumFractionDigits: 0})}</div>
        </div>
      </div>
      <div style="font-size:12px;color:#94a3b8;margin-top:10px">Capital is shown as an upfront outflow in ${asOf.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })} and as capital recovered at quarter end or exit. This does not mean the position is sold every quarter; it’s just the accounting view of cash coming back. Total cash received = capital recovered + profit.</div>
    </div>

    <div style="background:#1e2433;border:1px solid #2d3748;border-radius:8px;padding:16px;margin-bottom:16px">
      <div style="font-weight:600;color:#cbd5e1;margin-bottom:10px">Monthly Cashflow Chart</div>
      <div style="height:240px;display:flex;align-items:flex-end;gap:6px;padding:8px 4px;border-top:1px solid #2d3748;border-bottom:1px solid #2d3748;overflow-x:auto">
        ${monthRows.map(row => {
          const heightPx = Math.max(4, Math.round((Math.abs(row.monthly_net_cashflow) / maxAbsMonthly) * 180));
          const isPositive = row.monthly_net_cashflow >= 0;
          return `
            <div style="display:flex;flex-direction:column;align-items:center;min-width:38px;gap:6px" title="${row.label}: capital invested $${(row.principal_deployed || 0).toLocaleString('en-US', {maximumFractionDigits: 0})}, capital recovered $${(row.principal_returned || 0).toLocaleString('en-US', {maximumFractionDigits: 0})}, profit $${row.month_profit_inflow.toLocaleString('en-US', {maximumFractionDigits: 0})}, cash received $${row.cash_received.toLocaleString('en-US', {maximumFractionDigits: 0})}, net $${row.monthly_net_cashflow.toLocaleString('en-US', {maximumFractionDigits: 0})}">
              <div style="font-size:10px;color:#94a3b8">${(row.cash_received / 1000).toFixed(0)}k</div>
              <div style="width:20px;height:${heightPx}px;background:${isPositive ? '#10b981' : '#ef4444'};border-radius:4px"></div>
              <div style="font-size:10px;color:#94a3b8;white-space:nowrap">${row.label.replace(' ', '\n')}</div>
            </div>
          `;
        }).join('')}
      </div>
    </div>

    <div style="background:#1e2433;border:1px solid #2d3748;border-radius:8px;padding:16px">
      <div style="font-weight:600;color:#cbd5e1;margin-bottom:10px">Month-by-Month Cashflow Table</div>
      <div style="overflow:auto;max-height:420px">
        <table style="width:100%;border-collapse:collapse;font-size:12px">
          <thead>
            <tr style="border-bottom:1px solid #3d4758">
              <th style="text-align:left;padding:8px;color:#94a3b8">Month</th>
              <th style="text-align:right;padding:8px;color:#94a3b8">Active Quarters</th>
              <th style="text-align:right;padding:8px;color:#94a3b8">Capital Invested</th>
              <th style="text-align:right;padding:8px;color:#94a3b8">Capital Recovered</th>
              <th style="text-align:right;padding:8px;color:#94a3b8">Total Cash Received</th>
              <th style="text-align:right;padding:8px;color:#94a3b8">Net Cash Movement</th>
              <th style="text-align:right;padding:8px;color:#94a3b8">Capital Remaining</th>
              <th style="text-align:right;padding:8px;color:#94a3b8">Cumulative Cash Received</th>
              <th style="text-align:right;padding:8px;color:#94a3b8">Cumulative Net Cash</th>
            </tr>
          </thead>
          <tbody>
            ${monthRows.map(row => `
              <tr style="border-bottom:1px solid #2d3748;background:#0f1419">
                <td style="padding:8px;color:#cbd5e1">${row.label}</td>
                <td style="text-align:right;padding:8px;color:#94a3b8">${row.active_quarters}</td>
                <td style="text-align:right;padding:8px;color:${row.principal_deployed ? '#f87171' : '#64748b'}">$${(row.principal_deployed || 0).toLocaleString('en-US', {maximumFractionDigits: 0})}</td>
                <td style="text-align:right;padding:8px;color:${row.principal_returned ? '#10b981' : '#64748b'}">$${(row.principal_returned || 0).toLocaleString('en-US', {maximumFractionDigits: 0})}</td>
                <td style="text-align:right;padding:8px;color:#60a5fa;font-weight:600">$${row.cash_received.toLocaleString('en-US', {maximumFractionDigits: 0})}</td>
                <td style="text-align:right;padding:8px;color:${row.monthly_net_cashflow >= 0 ? '#10b981' : '#f87171'}">$${row.monthly_net_cashflow.toLocaleString('en-US', {maximumFractionDigits: 0})}</td>
                <td style="text-align:right;padding:8px;color:#f87171">$${row.principal_remaining.toLocaleString('en-US', {maximumFractionDigits: 0})}</td>
                <td style="text-align:right;padding:8px;color:#60a5fa;font-weight:600">$${row.cumulative_cash_received.toLocaleString('en-US', {maximumFractionDigits: 0})}</td>
                <td style="text-align:right;padding:8px;color:${row.cumulative_net_cash >= 0 ? '#10b981' : '#f59e0b'}">$${row.cumulative_net_cash.toLocaleString('en-US', {maximumFractionDigits: 0})}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

window.updateTRMonthlyCashflow = updateTRMonthlyCashflow;

function switchTRTab(tabName) {
  const oppBtn = document.getElementById('tr-tab-opportunities');
  const sellBtn = document.getElementById('tr-tab-sell');
  const pnlBtn = document.getElementById('tr-tab-pnl');
  const cashflowBtn = document.getElementById('tr-tab-cashflow');
  const anaBtn = document.getElementById('tr-tab-analytics');
  const oppPanel = document.getElementById('tr-tab-opportunities-panel');
  const sellPanel = document.getElementById('tr-tab-sell-panel');
  const pnlPanel = document.getElementById('tr-tab-pnl-panel');
  const cashflowPanel = document.getElementById('tr-tab-cashflow-panel');
  const anaPanel = document.getElementById('tr-tab-analytics-panel');

  if (tabName === 'opportunities') {
    oppBtn.style.borderBottom = '3px solid #10b981';
    oppBtn.style.color = '#cbd5e1';
    sellBtn.style.borderBottom = '3px solid transparent';
    sellBtn.style.color = '#94a3b8';
    pnlBtn.style.borderBottom = '3px solid transparent';
    pnlBtn.style.color = '#94a3b8';
    cashflowBtn.style.borderBottom = '3px solid transparent';
    cashflowBtn.style.color = '#94a3b8';
    anaBtn.style.borderBottom = '3px solid transparent';
    anaBtn.style.color = '#94a3b8';
    oppPanel.style.display = 'flex';
    sellPanel.style.display = 'none';
    pnlPanel.style.display = 'none';
    cashflowPanel.style.display = 'none';
    anaPanel.style.display = 'none';
  } else if (tabName === 'sell') {
    oppBtn.style.borderBottom = '3px solid transparent';
    oppBtn.style.color = '#94a3b8';
    sellBtn.style.borderBottom = '3px solid #10b981';
    sellBtn.style.color = '#cbd5e1';
    pnlBtn.style.borderBottom = '3px solid transparent';
    pnlBtn.style.color = '#94a3b8';
    cashflowBtn.style.borderBottom = '3px solid transparent';
    cashflowBtn.style.color = '#94a3b8';
    anaBtn.style.borderBottom = '3px solid transparent';
    anaBtn.style.color = '#94a3b8';
    oppPanel.style.display = 'none';
    sellPanel.style.display = 'flex';
    pnlPanel.style.display = 'none';
    cashflowPanel.style.display = 'none';
    anaPanel.style.display = 'none';
  } else if (tabName === 'pnl') {
    oppBtn.style.borderBottom = '3px solid transparent';
    oppBtn.style.color = '#94a3b8';
    sellBtn.style.borderBottom = '3px solid transparent';
    sellBtn.style.color = '#94a3b8';
    pnlBtn.style.borderBottom = '3px solid #10b981';
    pnlBtn.style.color = '#cbd5e1';
    cashflowBtn.style.borderBottom = '3px solid transparent';
    cashflowBtn.style.color = '#94a3b8';
    anaBtn.style.borderBottom = '3px solid transparent';
    anaBtn.style.color = '#94a3b8';
    oppPanel.style.display = 'none';
    sellPanel.style.display = 'none';
    pnlPanel.style.display = 'flex';
    cashflowPanel.style.display = 'none';
    anaPanel.style.display = 'none';
  } else if (tabName === 'cashflow') {
    oppBtn.style.borderBottom = '3px solid transparent';
    oppBtn.style.color = '#94a3b8';
    sellBtn.style.borderBottom = '3px solid transparent';
    sellBtn.style.color = '#94a3b8';
    pnlBtn.style.borderBottom = '3px solid transparent';
    pnlBtn.style.color = '#94a3b8';
    cashflowBtn.style.borderBottom = '3px solid #10b981';
    cashflowBtn.style.color = '#cbd5e1';
    anaBtn.style.borderBottom = '3px solid transparent';
    anaBtn.style.color = '#94a3b8';
    oppPanel.style.display = 'none';
    sellPanel.style.display = 'none';
    pnlPanel.style.display = 'none';
    cashflowPanel.style.display = 'flex';
    anaPanel.style.display = 'none';
  } else {
    oppBtn.style.borderBottom = '3px solid transparent';
    oppBtn.style.color = '#94a3b8';
    sellBtn.style.borderBottom = '3px solid transparent';
    sellBtn.style.color = '#94a3b8';
    pnlBtn.style.borderBottom = '3px solid transparent';
    pnlBtn.style.color = '#94a3b8';
    cashflowBtn.style.borderBottom = '3px solid transparent';
    cashflowBtn.style.color = '#94a3b8';
    anaBtn.style.borderBottom = '3px solid #10b981';
    anaBtn.style.color = '#cbd5e1';
    oppPanel.style.display = 'none';
    sellPanel.style.display = 'none';
    pnlPanel.style.display = 'none';
    cashflowPanel.style.display = 'none';
    anaPanel.style.display = 'flex';
  }
}

window.switchTRTab = switchTRTab;

function openTRDetailsModal(index) {
  const best_buys = window._trCurrentBestBuys || [];
  if (index < 0 || index >= best_buys.length) return;
  
  const item = best_buys[index];
  const modal = document.getElementById('tr-details-modal');
  const content = document.getElementById('tr-details-content');
  
  if (!modal || !content) return;

    const detailsHtml = `
    <h3 style="margin:0 0 16px 0;color:#e2e8f0;font-size:18px;border-bottom:1px solid #3d4758;padding-bottom:12px">
      💰 ${item.interconnector} · ${item.quarter}
    </h3>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">
      <div>
        <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">Market Price (per unit)</div>
        <div style="font-size:24px;color:#cbd5e1;font-weight:700">${_trFormatMoney(item.market_price_aud)}</div>
      </div>
      <div>
        <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">Fair Value (per unit)</div>
        <div style="font-size:24px;color:#76e4b8;font-weight:700">${_trFormatMoney(item.fair_value_aud)}</div>
      </div>
    </div>

    ${item.quarter_start ? `
    <div style="background:#111827;border:1px solid #2d3748;border-radius:8px;padding:14px;margin-bottom:20px">
      <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;font-weight:600">⏱ Time Scale</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:12px">
        <div>
          <div style="font-size:11px;color:#64748b">Quarter Start</div>
          <div style="font-size:13px;color:#cbd5e1;font-weight:600">${item.quarter_start}</div>
        </div>
        <div>
          <div style="font-size:11px;color:#64748b">Quarter End</div>
          <div style="font-size:13px;color:#cbd5e1;font-weight:600">${item.quarter_end}</div>
        </div>
        <div>
          <div style="font-size:11px;color:#64748b">Calendar Days</div>
          <div style="font-size:13px;color:#cbd5e1;font-weight:600">${item.calendar_days}</div>
        </div>
        <div>
          <div style="font-size:11px;color:#64748b">${item.quarter_started ? 'Days Remaining' : 'Days to Start'}</div>
          <div style="font-size:13px;color:${item.quarter_started ? '#f87171' : '#60a5fa'};font-weight:700">${item.quarter_started ? item.days_remaining : item.days_to_start}d</div>
        </div>
        <div>
          <div style="font-size:11px;color:#64748b">Total 5-min Intervals</div>
          <div style="font-size:13px;color:#cbd5e1;font-weight:600">${(item.total_5min_intervals||0).toLocaleString()}</div>
        </div>
        <div>
          <div style="font-size:11px;color:#64748b">Exp. Paying Intervals</div>
          <div style="font-size:13px;color:#10b981;font-weight:700">${(item.expected_paying_intervals||0).toLocaleString()}</div>
        </div>
      </div>
    </div>` : ''}

    <div style="background:rgba(16,185,129,0.15);border:1px solid #10b981;border-radius:8px;padding:16px;margin-bottom:20px">
      <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">Expected Edge</div>
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px">
        <div style="font-size:28px;color:#76e4b8;font-weight:700">${Number(item.delta_edge_pct || 0).toFixed(1)}%</div>
        <div style="font-size:16px;color:#cbd5e1;font-weight:600">${_trFormatMoney(item.expected_edge_aud)} total</div>
      </div>
      <div style="font-size:13px;color:#cbd5e1;line-height:1.6">
        At ${item.suggested_units} units: ${_trFormatMoney(Number(item.arbitrage_per_unit_aud || 0) * item.suggested_units)} profit
      </div>
    </div>

    <div style="margin-bottom:20px">
      <div style="font-size:13px;color:#94a3b8;font-weight:600;margin-bottom:8px">Reasoning</div>
      <div style="background:#111827;padding:12px;border-radius:6px;color:#cbd5e1;font-size:13px;line-height:1.6;border-left:3px solid #4a9eff">
        ${item.recommendation_reason || 'Strong undervalue opportunity based on fill-rate signal analysis.'}
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px">
      <div>
        <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">Confidence Level</div>
        <div style="background:#1f2937;padding:12px;border-radius:6px;border-left:3px solid #fbbf24">
          <div style="font-size:18px;color:#fbbf24;font-weight:700">${Math.round(Number(item.confidence || 0) * 100)}%</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:4px">Model certainty</div>
        </div>
      </div>
      <div>
        <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">Trade Action</div>
        <div style="background:#1f2937;padding:12px;border-radius:6px;border-left:3px solid #60a5fa">
          <div style="font-size:16px;color:#60a5fa;font-weight:700">${item.trade_action}</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:4px">${item.side} position</div>
        </div>
      </div>
    </div>

    <div style="background:#111827;padding:16px;border-radius:8px;border:1px solid #2d4a5f;margin-bottom:20px">
      <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;font-weight:600">Execution Plan</div>
      
      <div style="margin-bottom:12px">
        <div style="font-size:12px;color:#cbd5e1;margin-bottom:4px">Suggested Units to Buy</div>
        <div style="font-size:16px;color:#60a5fa;font-weight:700">${item.suggested_units} units</div>
      </div>

      <div style="margin-bottom:12px">
        <div style="font-size:12px;color:#cbd5e1;margin-bottom:4px">Suggested Spend</div>
        <div style="font-size:16px;color:#e2e8f0;font-weight:700">${_trFormatMoney(item.suggested_spend_aud)}</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:4px">At ${_trFormatMoney(item.market_price_aud)}/unit</div>
      </div>

      <div style="margin-bottom:12px;padding:10px;background:#0f1419;border-radius:6px">
        <div style="font-size:12px;color:#94a3b8;margin-bottom:4px">⚠️ Maximum Spend (without market impact)</div>
        <div style="font-size:14px;color:#cbd5e1;font-weight:600">${_trFormatMoney(item.max_no_impact_spend_aud)}</div>
        <div style="font-size:10px;color:#64748b;margin-top:4px">
          ${item.max_no_impact_units} units · ${item.liquidity_participation_pct}% of available liquidity
        </div>
      </div>

      <div style="font-size:12px;color:#cbd5e1;margin-bottom:4px">Risk per Unit (Stop Loss)</div>
      <div style="font-size:14px;color:#fca5a5;font-weight:700">${_trFormatMoney(item.risk_per_unit_aud)}</div>
    </div>

    ${item.settlement_mechanics ? `
    <div style="background:#0d1a10;border:1px solid #1f5c2a;border-radius:8px;padding:14px;margin-bottom:20px">
      <div style="font-size:12px;color:#86efac;font-weight:700;margin-bottom:8px">⚡ How You Get Paid — SRA Settlement</div>
      <div style="font-size:12px;color:#a7f3d0;line-height:1.7">${item.settlement_mechanics}</div>
    </div>` : ''}

    <div style="text-align:center">
      <button onclick="closeTRDetailsModal()" style="background:#3b82f6;color:#fff;border:none;padding:10px 24px;border-radius:6px;cursor:pointer;font-weight:600">Close</button>
    </div>
  `;  content.innerHTML = detailsHtml;
  modal.style.display = 'flex';
}

function closeTRDetailsModal() {
  const modal = document.getElementById('tr-details-modal');
  if (modal) modal.style.display = 'none';
}

function openTRQuarterSummaryModal(year, quarter) {
  const summaries = window._trQuarterSummaries || [];
  const summary = summaries.find(item => item.year === year && item.quarter === quarter);
  const modal = document.getElementById('tr-details-modal');
  const content = document.getElementById('tr-details-content');
  if (!modal || !content || !summary) return;

  content.innerHTML = `
    <h3 style="margin:0 0 16px 0;color:#e2e8f0;font-size:18px;border-bottom:1px solid #3d4758;padding-bottom:12px">
      📦 Quarter Summary · ${quarter}
    </h3>

    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:18px">
      <div style="background:#111827;padding:12px;border-radius:8px"><div style="font-size:11px;color:#94a3b8">Projected Profit</div><div style="font-size:18px;color:#34d399;font-weight:700">${_trFormatMoney(summary.total_projected_profit_aud)}</div></div>
      <div style="background:#111827;padding:12px;border-radius:8px"><div style="font-size:11px;color:#94a3b8">Capital at Risk</div><div style="font-size:18px;color:#f87171;font-weight:700">${_trFormatMoney(summary.total_capital_at_risk_aud)}</div></div>
      <div style="background:#111827;padding:12px;border-radius:8px"><div style="font-size:11px;color:#94a3b8">Total Spend</div><div style="font-size:18px;color:#cbd5e1;font-weight:700">${_trFormatMoney(summary.total_suggested_spend_aud)}</div></div>
      <div style="background:#111827;padding:12px;border-radius:8px"><div style="font-size:11px;color:#94a3b8">RORC</div><div style="font-size:18px;color:#76e4b8;font-weight:700">${Number(summary.return_on_risked_capital_pct || 0).toFixed(1)}%</div></div>
      <div style="background:#111827;padding:12px;border-radius:8px"><div style="font-size:11px;color:#94a3b8">Sell Whole Quarter Now</div><div style="font-size:18px;color:#60a5fa;font-weight:700">${_trFormatMoney(summary.exit_price_aud || summary.sell_now_value_aud)}</div></div>
      <div style="background:#111827;padding:12px;border-radius:8px"><div style="font-size:11px;color:#94a3b8">Expected Edge</div><div style="font-size:18px;color:#76e4b8;font-weight:700">${_trFormatMoney(summary.total_expected_edge_aud)}</div></div>
    </div>

    <div style="background:#0d1a10;border:1px solid #1f5c2a;border-radius:8px;padding:14px;margin-bottom:18px">
      <div style="font-size:12px;color:#86efac;font-weight:700;margin-bottom:8px">How to Sell the Whole Quarter</div>
      <div style="font-size:12px;color:#a7f3d0;line-height:1.7">
        ${summary.sell_entire_quarter_note || summary.notation || 'Sell the whole quarter = exit the full proposed position at current market prices. That is a trade, not the quarter payout itself.'}
      </div>
    </div>

    <div style="background:#111827;padding:12px;border-radius:8px;margin-bottom:18px">
      <div style="font-size:12px;color:#94a3b8;margin-bottom:6px">Quarter window</div>
      <div style="font-size:13px;color:#e2e8f0">${summary.quarter_start || '—'} → ${summary.quarter_end || '—'}</div>
      <div style="font-size:12px;color:#94a3b8;margin-top:8px">Trade count: <span style="color:#cbd5e1;font-weight:600">${summary.count}</span></div>
    </div>

    <div style="text-align:center">
      <button onclick="closeTRDetailsModal()" style="background:#3b82f6;color:#fff;border:none;padding:10px 24px;border-radius:6px;cursor:pointer;font-weight:600">Close</button>
    </div>
  `;
  modal.style.display = 'flex';
}

window.openTRDetailsModal = openTRDetailsModal;
window.closeTRDetailsModal = closeTRDetailsModal;
window.openTRQuarterSummaryModal = openTRQuarterSummaryModal;

function startTransmissionRightsAutoRefresh() {
  if (_trRefreshTimer) return;
  _trRefreshTimer = setInterval(() => {
    const wrapper = document.getElementById('tr-dashboard-wrapper');
    if (wrapper && wrapper.style.display !== 'none') {
      refreshTransmissionRightsDashboard();
    }
  }, 30_000);
}

function stopTransmissionRightsAutoRefresh() {
  if (_trRefreshTimer) {
    clearInterval(_trRefreshTimer);
    _trRefreshTimer = null;
  }
}

function openTransmissionRightsDashboard() {
  const grid = document.getElementById('projects-grid');
  const wrapper = document.getElementById('project-webview-wrapper');
  const trWrapper = document.getElementById('tr-dashboard-wrapper');
  if (grid) grid.style.display = 'none';
  if (wrapper) wrapper.style.display = 'none';
  if (trWrapper) trWrapper.style.display = 'flex';
  refreshTransmissionRightsDashboard();
  startTransmissionRightsAutoRefresh();
}

function closeTransmissionRightsDashboard() {
  const grid = document.getElementById('projects-grid');
  const trWrapper = document.getElementById('tr-dashboard-wrapper');
  if (grid) grid.style.display = 'flex';
  if (trWrapper) trWrapper.style.display = 'none';
  stopTransmissionRightsAutoRefresh();
}

window.openTransmissionRightsDashboard = openTransmissionRightsDashboard;
window.closeTransmissionRightsDashboard = closeTransmissionRightsDashboard;

window.addEventListener('DOMContentLoaded', async () => {
  await initApiPort();
  initTabs();
  initChat();
  initGraphControls();
  initAgentButtons();
  initVSCode();
  initVSCode2();
  initCapture();
  initNemDashboard();
  initDispatchAlgorithm();
  initBackcastPanel();
  initTodos();
  initSocial();
  initWeeklyReview();

  // Load stats and graph
  await loadStats();
  setInterval(loadStats, 30_000);

  // Init and load brain graph
  HaimGraph.init();
  HaimGraph.load(API_PORT);

  document.getElementById('tr-refresh-btn')?.addEventListener('click', refreshTransmissionRightsDashboard);

  document.addEventListener('visibilitychange', () => {
    const wrapper = document.getElementById('tr-dashboard-wrapper');
    if (!wrapper) return;
    if (document.hidden) stopTransmissionRightsAutoRefresh();
    else if (wrapper.style.display !== 'none') startTransmissionRightsAutoRefresh();
  });
});

// ── Weekly Review / David Lee Check-In ────────────────────────────────────────

let _wrFilter = 'all';

const WR_STATUS_BADGE = {
  active:   { label: '🟢 Active',   bg: '#10b98122', color: '#10b981', border: '#10b98155' },
  on_hold:  { label: '⏸ On Hold',  bg: '#94a3b822', color: '#94a3b8', border: '#94a3b855' },
  won:      { label: '✅ Won',      bg: '#3b82f622', color: '#60a5fa', border: '#3b82f655' },
  lost:     { label: '❌ Lost',     bg: '#ef444422', color: '#f87171', border: '#ef444455' },
};

const WR_COURT_BADGE = {
  us:     { label: '🎯 In Our Court',     color: '#60a5fa' },
  client: { label: '⏳ Waiting on Client', color: '#f59e0b' },
};

const WR_STAGE_STATUS = {
  delivered: { label: 'Delivered', color: '#10b981' },
  in_progress: { label: 'In Progress', color: '#60a5fa' },
  proposed: { label: 'Proposed', color: '#f59e0b' },
  pending:  { label: 'Pending', color: '#94a3b8' },
  cancelled: { label: 'Cancelled', color: '#ef4444' },
};

const WR_CAT_COLOR = {
  BDM: '#3b82f6', Grants: '#10b981', Investment: '#f59e0b',
  Tech: '#06b6d4', Finance: '#f97316', Other: '#6b7280'
};

function fmtMoney(n) {
  if (!n || n === 0) return '—';
  if (n >= 1_000_000) return `$${(n/1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n/1_000).toFixed(0)}k`;
  return `$${n}`;
}

function initWeeklyReview() {
  // Filter buttons
  document.querySelectorAll('.wr-filter').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.wr-filter').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _wrFilter = btn.dataset.filter;
      renderWeeklyReview();
    });
  });

  document.getElementById('wr-refresh-btn')?.addEventListener('click', renderWeeklyReview);

  // Add project modal
  const modal = document.getElementById('wr-modal');
  document.getElementById('wr-add-btn')?.addEventListener('click', () => {
    modal.style.display = 'flex';
  });
  document.getElementById('wr-m-cancel')?.addEventListener('click', () => {
    modal.style.display = 'none';
  });
  document.getElementById('wr-m-save')?.addEventListener('click', async () => {
    const payload = {
      name:    document.getElementById('wr-m-name').value,
      client:  document.getElementById('wr-m-client').value,
      contact: document.getElementById('wr-m-contact').value,
      category: document.getElementById('wr-m-cat').value,
      status:  document.getElementById('wr-m-status').value,
      court:   document.getElementById('wr-m-court').value,
      notes:   document.getElementById('wr-m-notes').value,
    };
    await fetch(`http://127.0.0.1:${API_PORT}/projects`, {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    modal.style.display = 'none';
    renderWeeklyReview();
  });

  // Payment modal
  const payModal = document.getElementById('wr-pay-modal');
  document.getElementById('pay-cancel')?.addEventListener('click', () => payModal.style.display = 'none');
  document.getElementById('pay-save')?.addEventListener('click', async () => {
    const pid = document.getElementById('pay-project-id').value;
    const payload = {
      amount:  parseFloat(document.getElementById('pay-amount').value) || 0,
      date:    document.getElementById('pay-date').value,
      stage:   document.getElementById('pay-stage').value,
      invoice: document.getElementById('pay-invoice').value,
    };
    await fetch(`http://127.0.0.1:${API_PORT}/projects/${pid}/payments`, {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    payModal.style.display = 'none';
    renderWeeklyReview();
  });
}

async function renderWeeklyReview() {
  const res = await fetch(`http://127.0.0.1:${API_PORT}/projects`).catch(() => null);
  if (!res) return;
  const projects = await res.json();

  // Filter
  const filtered = projects.filter(p => {
    if (_wrFilter === 'all')     return true;
    if (_wrFilter === 'active')  return p.status === 'active';
    if (_wrFilter === 'waiting') return p.court === 'client';
    if (_wrFilter === 'on_hold') return p.status === 'on_hold';
    if (_wrFilter === 'us')      return p.court === 'us' && p.status === 'active';
    return true;
  });

  // Summary stats bar
  const statsEl = document.getElementById('wr-stats');
  if (statsEl) {
    const totalPipeline = projects.reduce((s, p) =>
      s + p.stages.reduce((ss, st) => ss + (st.price || 0), 0), 0);
    const totalPaid = projects.reduce((s, p) =>
      s + (p.payments || []).reduce((ss, pay) => ss + (pay.amount || 0), 0), 0);
    const inCourt   = projects.filter(p => p.court === 'us' && p.status === 'active').length;
    const waiting   = projects.filter(p => p.court === 'client').length;

    statsEl.innerHTML = [
      { label: 'Total Pipeline',  val: fmtMoney(totalPipeline), color: '#60a5fa' },
      { label: 'Payments Received', val: fmtMoney(totalPaid),   color: '#10b981' },
      { label: 'In Our Court',    val: inCourt,                  color: '#60a5fa' },
      { label: 'Waiting on Client', val: waiting,               color: '#f59e0b' },
      { label: 'Active Projects', val: projects.filter(p => p.status === 'active').length, color: '#10b981' },
    ].map(s => `
      <div style="background:#1e2433;border:1px solid #2d3748;border-radius:8px;padding:8px 16px;text-align:center">
        <div style="font-size:18px;font-weight:700;color:${s.color}">${s.val}</div>
        <div style="font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:0.5px;margin-top:2px">${s.label}</div>
      </div>`).join('');
  }

  // Project cards
  const grid = document.getElementById('wr-grid');
  if (!grid) return;

  if (filtered.length === 0) {
    grid.innerHTML = '<div style="color:#718096;padding:40px;text-align:center">No projects match this filter.</div>';
    return;
  }

  grid.innerHTML = filtered.map((p, idx) => {
    const sb = WR_STATUS_BADGE[p.status] || WR_STATUS_BADGE.active;
    const cb = WR_COURT_BADGE[p.court]   || WR_COURT_BADGE.us;
    const catColor = WR_CAT_COLOR[p.category] || '#6b7280';

    // Stages table
    const stagesHtml = p.stages && p.stages.length ? `
      <table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:6px">
        <thead>
          <tr style="color:#718096;text-align:left">
            <th style="padding:4px 8px;border-bottom:1px solid #2d3748;font-weight:500">Stage</th>
            <th style="padding:4px 8px;border-bottom:1px solid #2d3748;font-weight:500;text-align:right">Fee</th>
            <th style="padding:4px 8px;border-bottom:1px solid #2d3748;font-weight:500;text-align:center">Status</th>
            <th style="padding:4px 8px;border-bottom:1px solid #2d3748;font-weight:500;text-align:center">Paid</th>
          </tr>
        </thead>
        <tbody>
          ${p.stages.map(st => {
            const ss = WR_STAGE_STATUS[st.status] || WR_STAGE_STATUS.pending;
            return `<tr style="border-bottom:1px solid #1a2030">
              <td style="padding:5px 8px;color:#e2e8f0">${escHtml(st.name)}${st.note?`<span style="color:#94a3b8;font-size:10px;margin-left:6px">(${escHtml(st.note)})</span>`:''}
              </td>
              <td style="padding:5px 8px;color:#e2e8f0;text-align:right">${fmtMoney(st.price)}</td>
              <td style="padding:5px 8px;text-align:center">
                <span style="background:${ss.color}22;color:${ss.color};border:1px solid ${ss.color}44;padding:2px 8px;border-radius:10px;font-size:10px">${ss.label}</span>
              </td>
              <td style="padding:5px 8px;text-align:center">
                <span style="cursor:pointer;font-size:14px" onclick="wrTogglePaid('${escHtml(p.id)}','${escHtml(st.id)}',${ !st.paid })">${st.paid ? '✅' : '⬜'}</span>
                ${st.paid && st.payment_date ? `<div style="font-size:9px;color:#718096">${st.payment_date}</div>` : ''}
              </td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>` : '<div style="font-size:12px;color:#4a5568;padding:6px 0">No stages defined yet.</div>';

    // Payments received
    const paid = (p.payments || []);
    const paidTotal = paid.reduce((s, x) => s + (x.amount || 0), 0);
    const paymentsHtml = paid.length ? `
      <div style="margin-top:8px;font-size:12px;color:#10b981;font-weight:600">
        💳 ${paid.length} payment${paid.length>1?'s':''} received — ${fmtMoney(paidTotal)} total
      </div>
      <div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:6px">
        ${paid.map(pay => `
          <span style="background:#10b98122;color:#10b981;border:1px solid #10b98144;padding:3px 10px;border-radius:10px;font-size:11px">
            ${fmtMoney(pay.amount)} · ${pay.date || '?'} · ${escHtml(pay.stage || '')}
          </span>`).join('')}
      </div>` : '';

    // Documents
    const docsHtml = p.documents && p.documents.length ? `
      <div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px">
        ${p.documents.map(d => `
          <span
            title="${escHtml(d.path)}"
            onclick="event.stopPropagation();window.haimos?.openInObsidian('${escHtml(d.path)}')"
            style="background:#2d374855;color:#93c5fd;border:1px solid #3b82f644;padding:3px 10px;border-radius:10px;font-size:11px;cursor:pointer;user-select:none">
            📄 ${escHtml(d.name)}
          </span>`).join('')}
      </div>` : '';

    // Our actions
    const actionsHtml = p.our_actions && p.our_actions.length ? `
      <div style="margin-top:10px">
        <div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:5px">🎯 Actions Required (Our Court)</div>
        <ul style="margin:0;padding-left:16px;list-style:disc">
          ${p.our_actions.map(a => `<li style="color:#e2e8f0;font-size:12px;margin-bottom:3px">${escHtml(a)}</li>`).join('')}
        </ul>
      </div>` : '';

    // Waiting on
    const waitingHtml = p.waiting_on && p.waiting_on.length ? `
      <div style="margin-top:10px">
        <div style="font-size:11px;color:#f59e0b;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:5px">⏳ Waiting On</div>
        <ul style="margin:0;padding-left:16px;list-style:disc">
          ${p.waiting_on.map(w => `<li style="color:#fcd34d;font-size:12px;margin-bottom:3px">${escHtml(w)}</li>`).join('')}
        </ul>
      </div>` : '';

    return `
    <div style="background:#1e2433;border:1px solid #2d3748;border-radius:12px;overflow:hidden;border-left:4px solid ${catColor}">

      <!-- Card header -->
      <div style="padding:12px 16px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;cursor:pointer" onclick="wrToggleCard('${escHtml(p.id)}')">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
          <span style="font-size:13px;font-weight:600;color:#e2e8f0">#${p.priority || idx+1} ${escHtml(p.name)}</span>
          <span style="background:${catColor}22;color:${catColor};border:1px solid ${catColor}44;padding:2px 8px;border-radius:10px;font-size:10px">${escHtml(p.category)}</span>
          <span style="background:${sb.bg};color:${sb.color};border:1px solid ${sb.border};padding:2px 8px;border-radius:10px;font-size:10px">${sb.label}</span>
          <span style="color:${cb.color};font-size:11px">${cb.label}</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:11px;color:#718096">${escHtml(p.client)}</span>
          ${p.contact ? `<span style="font-size:11px;color:#94a3b8">· ${escHtml(p.contact)}</span>` : ''}
          <button onclick="event.stopPropagation();wrOpenPayModal('${escHtml(p.id)}')"
            style="background:#10b98122;color:#10b981;border:1px solid #10b98144;padding:3px 10px;border-radius:6px;cursor:pointer;font-size:11px">+ Payment</button>
          <span id="wr-chevron-${escHtml(p.id)}" style="color:#718096;font-size:14px;transition:transform .2s">▼</span>
        </div>
      </div>

      <!-- Card body (collapsible) -->
      <div id="wr-body-${escHtml(p.id)}" style="padding:0 16px 14px;border-top:1px solid #2d374866">

        <!-- Notes -->
        ${p.notes ? `<div style="margin-top:10px;font-size:12px;color:#94a3b8;background:#13192988;padding:8px 12px;border-radius:6px;border-left:3px solid ${catColor}">${escHtml(p.notes)}</div>` : ''}

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:10px">
          <div>${actionsHtml}${waitingHtml}</div>
          <div>
            <!-- Stages -->
            <div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:5px">📋 Stages & Fees</div>
            ${stagesHtml}
            ${paymentsHtml}
            ${docsHtml}
          </div>
        </div>

        <div style="text-align:right;margin-top:8px;font-size:10px;color:#4a5568">Last updated: ${escHtml(p.last_updated || '—')}</div>
      </div>
    </div>`;
  }).join('');
}

async function wrTogglePaid(projectId, stageId, newPaid) {
  await fetch(`http://127.0.0.1:${API_PORT}/projects/${projectId}/stages/${stageId}`, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ paid: newPaid, payment_date: newPaid ? new Date().toISOString().slice(0,10) : '' })
  });
  renderWeeklyReview();
}

function wrToggleCard(id) {
  const body = document.getElementById(`wr-body-${id}`);
  const chev = document.getElementById(`wr-chevron-${id}`);
  if (!body) return;
  const isOpen = body.style.display !== 'none';
  body.style.display = isOpen ? 'none' : '';
  if (chev) chev.style.transform = isOpen ? 'rotate(-90deg)' : '';
}

function wrOpenPayModal(projectId) {
  document.getElementById('pay-project-id').value = projectId;
  document.getElementById('pay-amount').value  = '';
  document.getElementById('pay-date').value    = new Date().toISOString().slice(0,10);
  document.getElementById('pay-stage').value   = '';
  document.getElementById('pay-invoice').value = '';
  document.getElementById('wr-pay-modal').style.display = 'flex';
}

// Trigger render when tab is activated
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.nav-btn[data-tab="weekly"]').forEach(btn => {
    btn.addEventListener('click', renderWeeklyReview);
  });
});

