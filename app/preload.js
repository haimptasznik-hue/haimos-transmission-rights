const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('haimos', {
  saveNote:        (data) => ipcRenderer.invoke('save-note', data),
  openInObsidian:  (path) => ipcRenderer.invoke('open-in-obsidian', path),
  openExternalUrl: (url)  => ipcRenderer.invoke('open-external-url', url),
  getApiPort:      ()     => ipcRenderer.invoke('get-api-port'),
  closeCapture:    ()     => ipcRenderer.invoke('close-capture'),
});
