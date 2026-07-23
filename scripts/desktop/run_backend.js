/**
 * AlphaFoundry 跨平台后端启动桥接脚本
 *
 * Tauri 的 beforeDevCommand 需要一个长时间运行的命令来启动后端。
 * 本脚本根据平台自动选择 shell 启动器（Windows → .cmd, 其他 → .sh），
 * 确保 npm run desktop:dev 在 Windows/Mac/Linux 上都能正常工作。
 *
 * 用法（作为 tauri.conf.json 的 beforeDevCommand）:
 *   node scripts/desktop/run_backend.js --host 127.0.0.1 --port 8765 --reload
 */

const { spawn } = require("child_process");
const path = require("path");
const os = require("os");

const SCRIPT_DIR = __dirname;
const IS_WINDOWS = os.platform() === "win32";

// 解析命令行参数
const args = process.argv.slice(2);

if (IS_WINDOWS) {
    // Windows: 使用 cmd.exe 运行 run_backend.cmd
    const cmdPath = path.join(SCRIPT_DIR, "run_backend.cmd");
    const child = spawn("cmd.exe", ["/c", cmdPath, ...args], {
        stdio: "inherit",
        env: { ...process.env },
    });

    child.on("exit", (code) => {
        process.exit(code || 0);
    });
} else {
    // Mac / Linux: 使用 bash 运行 run_backend.sh
    const shPath = path.join(SCRIPT_DIR, "run_backend.sh");
    const child = spawn("bash", [shPath, ...args], {
        stdio: "inherit",
        env: { ...process.env },
    });

    child.on("exit", (code) => {
        process.exit(code || 0);
    });
}
