/**
 * graph.js — 3D interactive brain graph (3d-force-graph + Three.js)
 * Features: orbit-drag to rotate · scroll to zoom · click inspector ·
 *           double-click opens in Obsidian · hover highlights · search focus ·
 *           coloured nodes by folder · neuron firing animation
 */

window.HaimGraph = (() => {
  // ── State ───────────────────────────────────────────────────────────────────
  let graph3d      = null;
  let rawNodes     = [], rawLinks = [];
  let allNodes     = [], allLinks = [];  // full unfiltered data from API
  let adjacency    = new Map();
  let selectedNode = null;
  let hoveredNode  = null;
  let firingNodes  = new Map();
  const FIRE_DURATION = 3000;

  // ── Colour palette ─────────────────────────────────────────────────────────
  const FOLDER_COLORS = {
    '00_Inbox':          '#ffff00',
    '01_Journal':        '#a8d8a8',
    '02_Projects':       '#4199e1',
    '03_Projects':       '#4199e1',
    '00_Master_Context': '#9835fa',
    '01_State':          '#33dddd',
    '05_System':         '#808000',
    '05_Personal_Admin': '#996666',
    '04_Archive':        '#808080',
    'email':             '#ff4040',
    'trello':            '#0000ff',
    'onenote':           '#7bffff',
    'Clients':           '#ff8c30',
    'Deals':             '#ff6b6b',
    'Finance':           '#008000',
    'Grants':            '#33aa33',
    'Partnerships':      '#008000',
    'Tech':              '#9835fa',
    'Jobs':              '#ff8c30',
    'default':           '#6898d4',
  };

  function nodeColor(n) {
    const key = Object.keys(FOLDER_COLORS).find(k => (n.folder || '').includes(k));
    return (key ? FOLDER_COLORS[key] : null) || n.color || FOLDER_COLORS.default;
  }

  // ── State colours ──────────────────────────────────────────────────────────
  function getNodeRenderColor(n) {
    const isFiring   = firingNodes.has(n.id) && Date.now() < firingNodes.get(n.id);
    const isSelected = selectedNode === n;
    const isHovered  = hoveredNode  === n;
    const focusNode  = hoveredNode || selectedNode;
    const isNeighbor = focusNode && adjacency.get(focusNode.id)?.has(n.id);
    const isDimmed   = focusNode && !isSelected && !isHovered && !isNeighbor;

    if (isFiring)   return '#ffffff';
    if (isSelected) return '#ffffff';
    if (isHovered)  return '#ffffff';
    if (isNeighbor) return nodeColor(n);
    if (isDimmed)   return '#1a1f26';
    return nodeColor(n);
  }

  function getLinkColor(l) {
    const src = l.source, tgt = l.target;
    const isHi = (src === hoveredNode || tgt === hoveredNode ||
                  src === selectedNode || tgt === selectedNode);
    return isHi ? nodeColor(typeof src === 'object' ? src : { id: src }) : '#30363d';
  }

  function getLinkWidth(l) {
    const src = l.source, tgt = l.target;
    return (src === hoveredNode || tgt === hoveredNode ||
            src === selectedNode || tgt === selectedNode) ? 2 : 0.5;
  }

  function refreshColors() {
    if (!graph3d) return;
    graph3d.nodeColor(graph3d.nodeColor())
           .linkColor(graph3d.linkColor())
           .linkWidth(graph3d.linkWidth());
  }

  // ── Init ────────────────────────────────────────────────────────────────────
  function init() {
    const canvas = document.getElementById('graph-canvas');

    // 3d-force-graph needs a div container
    const div = document.createElement('div');
    div.id    = 'graph-3d-container';
    div.style.cssText = 'width:100%;height:100%;position:absolute;top:0;left:0;';
    canvas.parentNode.insertBefore(div, canvas);
    canvas.style.display = 'none';

    graph3d = ForceGraph3D({ antialias: true, alpha: false })(div)
      .backgroundColor('#0d1117')
      .showNavInfo(false)
      .nodeLabel(n => `<div style="background:#161b22;padding:4px 8px;border-radius:4px;border:1px solid #30363d;color:#e6edf3;font-size:12px">${n.id}</div>`)
      .nodeColor(n => getNodeRenderColor(n))
      .nodeVal(n  => Math.pow(n.size || 4, 1.5))
      .nodeOpacity(0.9)
      .linkColor(l  => getLinkColor(l))
      .linkWidth(l  => getLinkWidth(l))
      .linkOpacity(0.35)
      .d3AlphaDecay(0.008)
      .d3VelocityDecay(0.4)
      .onNodeHover(node => {
        hoveredNode = node || null;
        refreshColors();
        document.body.style.cursor = node ? 'pointer' : 'default';
      })
      .onNodeClick(node => {
        if (selectedNode === node) {
          selectedNode = null; closeInspector();
        } else {
          selectedNode = node;
          openInspector(node);
        }
        refreshColors();
      })
      .onNodeRightClick(n => {
        if (window.haimos) window.haimos.openInObsidian(n.path || n.id);
      })
      .onBackgroundClick(() => {
        selectedNode = null; closeInspector(); refreshColors();
      });

    // Stronger repulsion so nodes spread in 3D space
    graph3d.d3Force('charge').strength(-120).theta(0.9);
    graph3d.d3Force('link').distance(70).strength(0.15);

    // Hint text
    const hint = document.createElement('div');
    hint.style.cssText = 'position:absolute;bottom:8px;left:50%;transform:translateX(-50%);' +
      'color:#484f58;font-size:11px;pointer-events:none;z-index:10;white-space:nowrap';
    hint.textContent = 'Left-drag: rotate  ·  Right-drag: pan  ·  Scroll: zoom  ·  Click: inspect  ·  Right-click: open';
    div.appendChild(hint);
  }

  // ── Load data ────────────────────────────────────────────────────────────────
  async function load(apiPort, folder) {
    folder = folder || '';
    let url = 'http://127.0.0.1:' + apiPort + '/api/vault/graph?limit=20000';
    if (folder) url += '&folder=' + encodeURIComponent(folder);
    try {
      const res  = await fetch(url);
      const data = await res.json();
      allNodes = data.nodes;
      allLinks = data.edges;
      applyOrphanFilter();
    } catch (e) { console.error('Graph load error:', e); }
  }

  function applyOrphanFilter() {
    const hideOrphans = document.getElementById('graph-hide-orphans')?.checked !== false;
    const nodes = hideOrphans ? allNodes.filter(n => !n.orphan) : allNodes;
    const nodeIds = new Set(nodes.map(n => n.id));
    const edges = allLinks.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target));
    const orphanCount = allNodes.filter(n => n.orphan).length;
    const countEl = document.getElementById('graph-node-count');
    if (countEl) {
      countEl.textContent = nodes.length.toLocaleString() +
        (hideOrphans && orphanCount ? ` (${orphanCount} orphans hidden)` : '');
    }
    buildGraph(nodes, edges);
  }

  function buildGraph(nodes, edges) {
    selectedNode = null; hoveredNode = null;
    closeInspector();

    rawNodes = nodes.map(n => ({ ...n }));
    rawLinks = edges.map(e => ({ source: e.source, target: e.target }));

    adjacency = new Map(rawNodes.map(n => [n.id, new Set()]));
    for (const e of rawLinks) {
      adjacency.get(e.source)?.add(e.target);
      adjacency.get(e.target)?.add(e.source);
    }

    if (graph3d) {
      graph3d.graphData({ nodes: rawNodes, links: rawLinks });
    }
  }

  // ── Inspector panel ──────────────────────────────────────────────────────────
  function openInspector(node) {
    let panel = document.getElementById('graph-inspector');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'graph-inspector';
      panel.style.cssText = [
        'position:fixed','top:60px','right:12px','width:240px',
        'background:#161b22','border:1px solid #30363d','border-radius:8px',
        'padding:14px 16px','color:#e6edf3','font-size:13px','z-index:9999',
        'max-height:calc(100vh - 80px)','overflow-y:auto',
        'box-shadow:0 4px 24px rgba(0,0,0,.5)'
      ].join(';');
      document.body.appendChild(panel);
    }

    const deg       = (adjacency.get(node.id) || new Set()).size;
    const neighbors = [...(adjacency.get(node.id) || [])].slice(0, 30);

    panel.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">' +
        '<span style="font-weight:600;color:#fff;font-size:14px;word-break:break-word;flex:1">' + node.id + '</span>' +
        '<span id="inspector-close" style="cursor:pointer;color:#8b949e;font-size:20px;padding:0 0 0 8px;line-height:1">×</span>' +
      '</div>' +
      '<div style="color:#8b949e;font-size:11px;margin-bottom:10px">' +
        (node.folder || 'root') + ' &middot; <strong style="color:#6898d4">' + deg + '</strong> connections' +
      '</div>' +
      '<button id="inspector-open" style="width:100%;padding:6px;background:#21262d;border:1px solid #30363d;border-radius:6px;color:#e6edf3;cursor:pointer;font-size:12px;margin-bottom:12px">Open in Obsidian ↗</button>' +
      '<div style="color:#8b949e;font-size:11px;margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em">Connections</div>' +
      '<div style="display:flex;flex-direction:column;gap:3px">' +
        neighbors.map(id =>
          '<div class="insp-nb" data-id="' + id + '" style="padding:4px 8px;background:#0d1117;border-radius:4px;cursor:pointer;font-size:12px;color:#8b949e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="' + id + '">' + id + '</div>'
        ).join('') +
        (deg > 30 ? '<div style="color:#484f58;font-size:11px;padding:4px 8px">+' + (deg - 30) + ' more…</div>' : '') +
      '</div>';

    panel.querySelector('#inspector-close').onclick = () => {
      selectedNode = null; closeInspector(); refreshColors();
    };
    panel.querySelector('#inspector-open').onclick = () => {
      if (window.haimos) window.haimos.openInObsidian(node.path || node.id);
    };
    panel.querySelectorAll('.insp-nb').forEach(el => {
      el.addEventListener('mouseenter', () => { el.style.color = '#e6edf3'; el.style.background = '#21262d'; });
      el.addEventListener('mouseleave', () => { el.style.color = '#8b949e'; el.style.background = '#0d1117'; });
      el.addEventListener('click', () => {
        const found = rawNodes.find(n => n.id === el.dataset.id);
        if (found) { selectedNode = found; openInspector(found); focusOn(found); refreshColors(); }
      });
    });
  }

  function closeInspector() {
    const p = document.getElementById('graph-inspector');
    if (p) p.remove();
  }

  function focusOn(node) {
    if (!graph3d || node.x == null) return;
    const dist = 300;
    graph3d.cameraPosition(
      { x: node.x + dist, y: node.y, z: node.z + dist },
      { x: node.x,        y: node.y, z: node.z        },
      800
    );
  }

  // ── Neuron firing ──────────────────────────────────────────────────────────
  function fireNodes(nodeIds) {
    const now = Date.now();
    nodeIds.forEach(id => {
      const match = rawNodes.find(n =>
        n.id === id || n.path === id ||
        n.id === id.replace(/\.md$/, '').split('/').pop()
      );
      if (match) firingNodes.set(match.id, now + FIRE_DURATION);
    });
    refreshColors();
    setTimeout(refreshColors, FIRE_DURATION + 100);
  }

  // ── Search ─────────────────────────────────────────────────────────────────
  function searchFocus(term) {
    if (!term) { selectedNode = null; closeInspector(); refreshColors(); return; }
    const t = term.toLowerCase();
    const match = rawNodes.find(n => n.id.toLowerCase().includes(t));
    if (match) {
      selectedNode = match;
      openInspector(match);
      focusOn(match);
      refreshColors();
    }
  }

  return { init, load, applyOrphanFilter, fireNodes, searchFocus };
})();
