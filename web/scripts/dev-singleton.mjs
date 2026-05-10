import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(webRoot, "..");
const lockDir = path.join(repoRoot, ".runtime", "locks");
const lockPath = path.join(lockDir, "frontend.lock");
const viteEntry = path.join(webRoot, "node_modules", "vite", "bin", "vite.js");

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function readLockInfo() {
  try {
    const content = fs.readFileSync(lockPath, "utf-8").trim();
    return content ? JSON.parse(content) : null;
  } catch {
    return null;
  }
}

function isPidAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) {
    return false;
  }
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function acquireLock() {
  ensureDir(lockDir);
  while (true) {
    try {
      const fd = fs.openSync(lockPath, "wx");
      fs.writeFileSync(
        fd,
        JSON.stringify(
          {
            name: "frontend",
            pid: process.pid,
            startedAt: new Date().toISOString(),
            argv: process.argv.slice(2),
          },
          null,
          2,
        ),
      );
      return fd;
    } catch (error) {
      const existing = readLockInfo();
      if (existing?.pid && isPidAlive(existing.pid)) {
        throw new Error(`frontend is already running (pid=${existing.pid}). Lock file: ${lockPath}`);
      }
      try {
        fs.unlinkSync(lockPath);
      } catch {
        // Ignore stale removal errors and retry.
      }
    }
  }
}

const lockFd = acquireLock();
const viteArgs = [
  viteEntry,
  "--host",
  process.env.VITE_HOST ?? "127.0.0.1",
  "--port",
  process.env.VITE_PORT ?? "5173",
];

if (process.argv.length > 2) {
  viteArgs.push(...process.argv.slice(2));
}

const child = spawn(process.execPath, viteArgs, {
  cwd: webRoot,
  stdio: "inherit",
  shell: false,
  env: process.env,
});

const cleanup = () => {
  try {
    fs.closeSync(lockFd);
  } catch {
    // ignore
  }
  try {
    fs.unlinkSync(lockPath);
  } catch {
    // ignore
  }
};

const terminateChild = () => {
  if (child.killed) {
    return;
  }
  try {
    child.kill("SIGTERM");
  } catch {
    // ignore
  }
};

process.on("SIGINT", () => {
  terminateChild();
});
process.on("SIGTERM", () => {
  terminateChild();
});
process.on("exit", cleanup);

child.on("exit", (code, signal) => {
  cleanup();
  if (signal) {
    process.exitCode = 1;
    return;
  }
  process.exitCode = code ?? 0;
});
