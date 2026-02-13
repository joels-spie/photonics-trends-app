const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const API_HOST = "127.0.0.1";
const API_PORT = Number(process.env.PHOTONICS_PORT || "18765");
const API_BASE = `http://${API_HOST}:${API_PORT}`;
const HEALTH_URL = `${API_BASE}/api/health`;

let backendProcess = null;

function backendExecutablePath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend", "photonics-backend.exe");
  }
  return process.env.PHOTONICS_BACKEND_EXE || path.resolve(__dirname, "../../backend/dist/photonics-backend.exe");
}

function waitForBackendReady(timeoutMs = 30000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const poll = () => {
      const req = http.get(HEALTH_URL, (res) => {
        res.resume();
        if (res.statusCode === 200) {
          resolve();
          return;
        }
        retry();
      });
      req.on("error", retry);
      req.setTimeout(2000, () => {
        req.destroy();
        retry();
      });
    };

    const retry = () => {
      if (Date.now() - start > timeoutMs) {
        reject(new Error("Backend startup timed out."));
        return;
      }
      setTimeout(poll, 350);
    };

    poll();
  });
}

function startBackend() {
  const exePath = backendExecutablePath();
  backendProcess = spawn(exePath, [], {
    stdio: "ignore",
    windowsHide: true,
    env: {
      ...process.env,
      PHOTONICS_PORT: String(API_PORT),
    },
  });

  backendProcess.on("exit", () => {
    backendProcess = null;
  });
}

function stopBackend() {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
}

async function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1460,
    height: 920,
    minWidth: 1100,
    minHeight: 760,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      additionalArguments: [`--photonics-api-base=${API_BASE}`],
    },
  });

  if (!app.isPackaged && process.env.ELECTRON_START_URL) {
    await mainWindow.loadURL(process.env.ELECTRON_START_URL);
    return;
  }

  await mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
}

app.whenReady().then(async () => {
  try {
    startBackend();
    await waitForBackendReady();
    await createWindow();
  } catch (error) {
    dialog.showErrorBox("Startup Error", `Could not start Photonics backend.\n\n${String(error)}`);
    app.quit();
  }
});

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  stopBackend();
});
