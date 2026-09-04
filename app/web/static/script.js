
// Research Workbench 前端脚本
const outputArea = document.getElementById("output-area");
const btnTestSimple = document.getElementById("btn-test-simple");
const btnTestSignal = document.getElementById("btn-test-signal");

function log(msg) {
    outputArea.textContent += msg + "\n";
    outputArea.scrollTop = outputArea.scrollHeight;
}

btnTestSimple.addEventListener("click", async () => {
    log("运行基础测试...");
    log("请在终端运行: python examples/test_simple.py");
    log("");
    log("或者点击下面的链接打开文档:");
    log("- README.md - 项目概述");
    log("- docs/REFERENCE.md - 完整参考手册");
});

btnTestSignal.addEventListener("click", async () => {
    log("运行信号测试...");
    log("请在终端运行: python examples/test_signal_lab_simple.py");
    log("");
    log("或者运行完整演示: python examples/signal_lab_demo.py");
});

// 页面加载完成
window.addEventListener("DOMContentLoaded", () => {
    log("Research Workbench Web Workbench");
    log("=============================");
    log("");
    log("快速开始:");
    log("1. 确保已安装依赖: pip install -e \".[dev]\"");
    log("2. 初始化数据库: python scripts/init_db.py");
    log("3. 运行示例: python examples/test_simple.py");
    log("");
    log("CLI 命令:");
    log("- 资产分析: rwb analyze --asset 600000.SH");
    log("- 情景分析: rwb scenario --topic \"人工智能产业发展\"");
    log("- 信号管理: rwb signal --help");
    log("- 运行回测: rwb backtest --help");
    log("");
    log("=============================");
});
