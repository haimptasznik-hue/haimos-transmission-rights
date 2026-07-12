const { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

const VAULT_ROOT = app.isPackaged
  ? '/Users/haimptasznik/Desktop/HaimOS'
  : path.resolve(__dirname, '..');
const VENV_PYTHON = path.join(VAULT_ROOT, '.venv', 'bin', 'python3');
const SERVER_SCRIPT = path.join(VAULT_ROOT, 'haimos-app', 'backend', 'server.py');
const API_PORT = 8765;
const DEV_RENDERER_ROOT = path.join(VAULT_ROOT, 'haimos-app', 'renderer');
const APP_RENDERER_ROOT = fs.existsSync(DEV_RENDERER_ROOT)
  ? DEV_RENDERER_ROOT
  : path.join(__dirname, 'renderer');

let mainWindow = null;
let tray = null;
let backendProcess = null;
let captureWindow = null;

// ── Start FastAPI backend ─────────────────────────────────────────────────────
function startBackend() {
  console.log('Starting HaimOS backend...');
  backendProcess = spawn(VENV_PYTHON, [SERVER_SCRIPT], {
    cwd: VAULT_ROOT,
    env: { ...process.env },
  });

  backendProcess.stdout.on('data', d => console.log('[backend]', d.toString().trim()));
  backendProcess.stderr.on('data', d => {
    const msg = d.toString().trim();
    if (!msg.includes('INFO') && !msg.includes('GET') && !msg.includes('POST')) {
      console.error('[backend err]', msg);
    }
  });

  backendProcess.on('exit', code => {
    if (code !== 0 && code !== null) console.error(`[backend] exited with code ${code}`);
  });
}

// ── Wait for backend to be ready ─────────────────────────────────────────────
function waitForBackend(retries = 20) {
  return new Promise((resolve, reject) => {
    const http = require('http');
    const check = (n) => {
      setTimeout(() => {
        http.get(`http://127.0.0.1:${API_PORT}/api/vault/stats`, res => {
          resolve();
        }).on('error', () => {
          if (n <= 0) reject(new Error('Backend did not start'));
          else check(n - 1);
        });
      }, 500);
    };
    check(retries);
  });
}

// ── Create main window ────────────────────────────────────────────────────────
async function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 1000,
    minWidth: 1200,
    minHeight: 700,
    backgroundColor: '#0d1117',
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 16, y: 16 },
    webPreferences: {
      preload: path.join(path.dirname(APP_RENDERER_ROOT), 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webviewTag: true,
      webSecurity: false,
      allowRunningInsecureContent: true,
    },
  });

  mainWindow.loadFile(path.join(APP_RENDERER_ROOT, 'index.html'));

  // Inject polyfill preload into every webview (fixes "clearMarks is not a function")
  mainWindow.webContents.on('will-attach-webview', (event, webPreferences, params) => {
    webPreferences.preload = path.join(APP_RENDERER_ROOT, 'webview-preload.js');
  });

  // Open DevTools detached — remove this line once UI is confirmed working
  if (process.env.HAIMOS_DEV) mainWindow.webContents.openDevTools({ mode: 'detach' });

  // Allow webviews to load external sites
  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': ["default-src * 'unsafe-inline' 'unsafe-eval' data: blob:"],
      },
    });
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── Quick capture window ──────────────────────────────────────────────────────
function createCaptureWindow() {
  if (captureWindow) {
    captureWindow.focus();
    return;
  }
  captureWindow = new BrowserWindow({
    width: 600,
    height: 180,
    frame: false,
    alwaysOnTop: true,
    backgroundColor: '#161b22',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  captureWindow.loadFile(path.join(__dirname, 'renderer', 'capture.html'));
  captureWindow.on('closed', () => { captureWindow = null; });
  captureWindow.on('blur', () => { if (captureWindow) captureWindow.close(); });
}

// ── Tray ──────────────────────────────────────────────────────────────────────
function createTray() {
  // Use a simple text tray if no icon available
  const iconPath = path.join(__dirname, 'assets', 'tray-icon.png');
  const hasIcon = fs.existsSync(iconPath);

  if (hasIcon) {
    tray = new Tray(iconPath);
  } else {
    // Create a minimal 16x16 PNG programmatically isn't easy — skip tray on no icon
    return;
  }

  const menu = Menu.buildFromTemplate([
    { label: 'Open HaimOS', click: () => mainWindow ? mainWindow.focus() : createMainWindow() },
    { label: 'Quick Capture  ⌘⇧Space', click: createCaptureWindow },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() },
  ]);
  tray.setContextMenu(menu);
  tray.setToolTip('HaimOS');
}

// ── IPC handlers ─────────────────────────────────────────────────────────────
ipcMain.handle('save-note', async (_, { title, content }) => {
  const inboxDir = path.join(VAULT_ROOT, '00_Inbox');
  const safe = title.replace(/[^a-zA-Z0-9 _-]/g, '').trim() || 'Quick Note';
  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const filename = `${ts}_${safe}.md`;
  const filepath = path.join(inboxDir, filename);
  const body = `# ${title}\n\n${content}\n\n---\n*Captured: ${new Date().toLocaleString()}*\n`;
  fs.writeFileSync(filepath, body, 'utf8');
  return { success: true, filename };
});

ipcMain.handle('open-in-obsidian', (_, notePath) => {
  shell.openExternal(`obsidian://open?vault=HaimOS&file=${encodeURIComponent(notePath)}`);
});

ipcMain.handle('open-external-url', (_, url) => {
  if (typeof url !== 'string') return false;
  if (!/^https?:\/\//i.test(url)) return false;
  shell.openExternal(url);
  return true;
});

ipcMain.handle('get-api-port', () => API_PORT);

ipcMain.handle('close-capture', () => { if (captureWindow) captureWindow.close(); });

// ── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  startBackend();

  // Register global shortcut for quick capture
  globalShortcut.register('CommandOrControl+Shift+Space', createCaptureWindow);

  try {
    await waitForBackend();
    console.log('Backend ready.');
  } catch (e) {
    console.error('Backend failed to start:', e.message);
  }

  await createMainWindow();
  createTray();
});

app.on('window-all-closed', () => {
  // Keep running in tray on macOS
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (!mainWindow) createMainWindow();
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  if (backendProcess) backendProcess.kill();
});
