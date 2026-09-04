/**
 * Start an isolated Tauri development preview for the current Git worktree.
 *
 * This keeps the stable desktop instance on its default port while a feature
 * branch is reviewed through its own backend port and runtime data directory.
 */

import { spawn, spawnSync } from "node:child_process";
import { access, mkdtemp, rm, writeFile } from "node:fs/promises";
import { constants } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_PORT = 8766;
const HOST = "127.0.0.1";
const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(SCRIPT_DIR, "../..");
const IS_WINDOWS = process.platform === "win32";

function previewOptions(argv) {
    let port = DEFAULT_PORT;
    let useStableData = false;
    for (let index = 0; index < argv.length; index += 1) {
        if (argv[index] === "--use-stable-data") {
            useStableData = true;
        } else if (argv[index] === "--port") {
            const suppliedPort = argv[index + 1];
            if (!suppliedPort) {
                throw new Error("--port requires a value");
            }
            port = Number(suppliedPort);
            index += 1;
        } else {
            throw new Error("Usage: npm run desktop:preview -- [--port 8766] [--use-stable-data]");
        }
    }

    if (!Number.isInteger(port) || port < 1024 || port > 65535) {
        throw new Error("Preview port must be an integer between 1024 and 65535");
    }
    return { port, useStableData };
}

function stableDesktopDataDir() {
    if (IS_WINDOWS) {
        return path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"), "Research Workbench");
    }
    if (process.platform === "darwin") {
        return path.join(os.homedir(), "Library", "Application Support", "Research Workbench");
    }
    return path.join(process.env.XDG_DATA_HOME || path.join(os.homedir(), ".local", "share"), "Research Workbench");
}

async function executable(pathname) {
    try {
        await access(pathname, constants.X_OK);
        return true;
    } catch {
        return false;
    }
}

async function resolveTauriCli() {
    const configuredCli = process.env.RESEARCH_TAURI_CLI;
    if (configuredCli) {
        if (await executable(configuredCli)) {
            return configuredCli;
        }
        throw new Error(`RESEARCH_TAURI_CLI is not executable: ${configuredCli}`);
    }

    const cliName = IS_WINDOWS ? "tauri.cmd" : "tauri";
    const localCli = path.join(PROJECT_ROOT, "node_modules", ".bin", cliName);
    if (await executable(localCli)) {
        return localCli;
    }

    const worktrees = spawnSync("git", ["worktree", "list", "--porcelain"], {
        cwd: PROJECT_ROOT,
        encoding: "utf8",
    });
    if (worktrees.status === 0) {
        const candidates = worktrees.stdout
            .split("\n")
            .filter((line) => line.startsWith("worktree "))
            .map((line) => line.slice("worktree ".length));
        for (const worktree of candidates) {
            const candidate = path.join(worktree, "node_modules", ".bin", cliName);
            if (await executable(candidate)) {
                return candidate;
            }
        }
    }

    throw new Error(
        "Cannot find Tauri CLI. Run npm ci once in a checked-out Research Workbench worktree, " +
            "or set RESEARCH_TAURI_CLI to an executable path.",
    );
}

function previewConfig(port) {
    const backendUrl = `http://${HOST}:${port}`;
    return {
        build: {
            devUrl: backendUrl,
            beforeDevCommand: `node scripts/desktop/run_backend.js --host ${HOST} --port ${port} --reload`,
        },
        app: {
            security: {
                csp: `default-src 'self'; connect-src 'self' ${backendUrl}; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: ${backendUrl}`,
            },
        },
    };
}

async function main() {
    const { port, useStableData } = previewOptions(process.argv.slice(2));
    const temporaryDir = await mkdtemp(path.join(os.tmpdir(), "research-workbench-preview-"));
    const configPath = path.join(temporaryDir, "tauri.preview.conf.json");
    const dataDir = process.env.RESEARCH_DESKTOP_DATA_DIR || (
        useStableData ? stableDesktopDataDir() : path.join(temporaryDir, "data")
    );
    const tauriCli = await resolveTauriCli();
    await writeFile(configPath, `${JSON.stringify(previewConfig(port), null, 2)}\n`, "utf8");

    console.info(`Starting Research Workbench branch preview at http://${HOST}:${port}`);
    console.info(`Preview runtime data: ${dataDir}`);
    if (useStableData) {
        console.info("Preview is reusing stable desktop configuration; background workers remain disabled.");
    }
    const child = spawn(tauriCli, ["dev", "--config", configPath], {
        cwd: PROJECT_ROOT,
        env: {
            ...process.env,
            RESEARCH_BACKEND_URL: `http://${HOST}:${port}`,
            RESEARCH_DESKTOP_DATA_DIR: dataDir,
            RESEARCH_DESKTOP_PORT: String(port),
            RESEARCH_PREVIEW: "1",
        },
        stdio: "inherit",
    });

    child.on("error", (error) => {
        console.error("Unable to start Research Workbench branch preview:", error.message);
    });
    child.on("exit", async (code, signal) => {
        try {
            await rm(temporaryDir, { recursive: true, force: true });
        } catch (error) {
            console.error("Unable to remove preview temporary files:", error.message);
        }
        process.exitCode = code ?? (signal ? 1 : 0);
    });
}

main().catch((error) => {
    console.error("Research Workbench branch preview failed:", error.message);
    process.exitCode = 1;
});
