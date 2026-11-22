# OpenBB FRED／BLS 实际试点

macOS arm64，用户已明确同意本次独立安装。使用 Python 3.12、固定 core 2.0.1／FRED 2.0.0／BLS 2.0.0 共48包的 hash 锁，venv 约152 MiB；没有修改 RWB 现有环境或全局 HOME。SDK 冷导入3.491秒，两个公共命令及帮助可用。

固定输入为 FRED DFF、2024-01-02至08，BLS CUUR0000SA0、2024年。实际结果：

- FRED 公共 SDK：缺 `fred_api_key`，HTTP 前拒绝，供应商请求0。先前显式传 optional None 触参数校验，改为省略后才记录该凭据结果。
- BLS 公共 SDK：缺 `bls_api_key`，HTTP 前拒绝，请求0；底层官方 helper 支持匿名，但不能冒充公共命令已通过。
- BLS helper：匿名、catalog=False、一次 POST，10.561秒超时。
- 同端点／请求体 HTTPX 对照：一次 POST，1.005秒、HTTP403、408字节。两次真实网络请求，没有重试或取得成功数据。
- 已安装 FRED 转换代码会 `dropna` 并移除每条 realtime_start/end；BLS 规范化简化 period 与脚注 code。当前不能证明缺失、修订与来源字段等价保留。

结论：本批不采用 OpenBB 替换这两个匿名 Provider，删除清单为空。SDK 能力、真实取数、字段等价和金融质量分别判断；没有成功响应，逐字段对拍为 NOT_RUN，不伪报不一致数值或失败已修。OpenBB仍是扩展其他具体覆盖的候选，未决定全面排除。

实际版本、请求、错误和小原始响应位于本任务 Scratch `weknora-live-chain-20261122/openbb-trial/`，主结论 `SUMMARY.md`。锁定文件在同任务 `openbb-prepare/openbb-minimal-py312-macos-arm64-wheels.lock`。无凭据读取、复制或修改，无常驻服务。
