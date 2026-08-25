#!/usr/bin/env node
// Starts the shared backend (if it isn't already up) before starting a frontend
// dev server. The backend is intentionally left running independently of the
// frontend process — favor-web (8090) and favor-admin (8091) are two frontend
// instances sharing the SAME backend on :8000, so the backend must not die just
// because one of them stops. Written in plain Node (no bash/coreutils) because
// the preview-server spawn environment doesn't put Git's usr/bin on PATH.
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

const ROOT = __dirname;
const PORT = process.argv[2] || "8090";

function checkBackend() {
  return new Promise((resolve) => {
    const req = http.get({ host: "127.0.0.1", port: 8000, path: "/api/bootstrap", timeout: 1000 }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

async function waitForBackend(retries) {
  for (let i = 0; i < retries; i++) {
    if (await checkBackend()) return true;
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

async function main() {
  const up = await checkBackend();
  if (!up) {
    console.log("[dev-with-backend] backend not responding on :8000 - starting it");
    const backendDir = path.join(ROOT, "backend");
    const pythonExe = path.join(backendDir, "venv", "Scripts", "python.exe");
    const backend = spawn(pythonExe, ["-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"], {
      cwd: backendDir,
      env: { ...process.env, EXPO_PUBLIC_BACKEND_URL: "http://localhost:8000" },
      detached: true,
      stdio: "ignore",
    });
    backend.unref();
    const ready = await waitForBackend(20);
    console.log(ready ? "[dev-with-backend] backend is up" : "[dev-with-backend] backend did not respond in time, continuing anyway");
  } else {
    console.log("[dev-with-backend] backend already running on :8000");
  }

  const frontendDir = path.join(ROOT, "frontend");
  const expo = spawn("npx", ["expo", "start", "--web", "--port", PORT], {
    cwd: frontendDir,
    stdio: "inherit",
    shell: true,
  });
  expo.on("exit", (code) => process.exit(code === null ? 0 : code));
}

main();
