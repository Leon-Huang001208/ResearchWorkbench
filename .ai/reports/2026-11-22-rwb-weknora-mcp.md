# WeKnora MCP 客户端登记与原 Host 兼容

宿主：Mac mini / macOS arm64；功能修复。本轮仅调整既有入站 MCP 的登记校验，
不安装依赖、不启动模型、不更新常驻配置，不声称 Windows/Linux 原生或真实 WeKnora 链路通过。

Product-Progress: not-required — 仅修正操作员显式 MCP 配置的兼容性，无产品界面或已启用功能变更。

## 问题与改动

既有 WeKnora 客户端被错误绑定到 `service_only`，切换该模式又会改变原 Host 生命周期。
`mcp_facade/config.py` 与 `multiuser/__main__.py` 解除这个耦合，已有 DSH 与仅服务模式
均可显式登记；仍要求启用 MCP，完整回调由规范来源固定生成。

最初认为“WeKnora 不写同名 Cookie，因此可以接受同 hostname 的 HTTPS 不同端口”是错误结论。
独立审查的真实 Chrome 离线复现证明：9543→9443 仍会**发送** RWB 的
Secure/HttpOnly/SameSiteStrict Cookie，问题不只是 Cookie 覆盖。本次已撤销该放宽，
恢复 HTTPS issuer/callback 同 hostname 拒绝。跨设备生产必须使用不同 hostname；
本机试点采用 RWB HTTPS 9543 → WeKnora `http://127.0.0.1:18181` 回调。
不能用另建空 CookieJar 掩盖真实浏览器的 Cookie 行为。

同一 origin、非法路径/查询/片段、未批准域名仍拒绝；未登记、未启用仍关闭。
原 `rwb.read`、四项冻结工具、PKCE、issuer/resource、旧 grant 与材料批准行为保持。
新增 DataHub scope/工具的独立实现与验收见[DataHub 接入报告](2026-11-22-rwb-weknora-datahub-mcp.md)。

实际隔离验证还发现 `multiuser/origin.py` 和 MCP issuer 校验把合法 Tailnet HTTPS
限定在 443，无法使用不影响生产的独立 9543 入口。最窄修正允许规范非默认 HTTPS 端口，
元数据与准确 Host/Origin、issuer/resource 继续含端口，非法端口、地址与路径仍拒绝；
默认 443 行为保持。不增加代理或任意转发头身份来源。

模块合同及安装说明同步更新。`requirements/web.in`、`requirements/web.lock`、
`scripts/setup_web.py` 与公开一键安装入口无依赖或安装行为变化；最终同候选
Mac Bootstrap 干净安装仍由主任务与 CI 验证。

## 实际验证

- Cookie P1 的新反例先在放宽版本实际 2 项失败；恢复同 hostname 拒绝后，配置正反例、
  Doctor、embedded resident 和 SDK ASGI 元数据/Host-Origin 端口边界共 **32 项 PASS**。
  两批分别 20/12 项，经原 retention 入口串行执行并自动回收成功根；均为 WIP，
  不冒称最终 exact-SHA 验收。早期候选的 37/18 项结果不代表更正后的安全验收，不累加。
- 9543 标准 HTTPS issuer、原 443、embedded 与仅服务模式保持支持；本机回调改为
  HTTP127.0.0.1，另验证不同 HTTPS hostname 支持；同 origin、同 HTTPS hostname、
  非法地址和端口仍拒绝。
- 一次性现场脚本改用同一浏览器 CookieJar 跟随原授权/回调，回调前移除 RWB 专用
  header，并检查本测试 `rwb_session` 不会发送给回调；不输出 Cookie、code/state/token。
  该修正版仅静态检查，尚未重新执行现场授权。
- 原现场结果 `live-mcp-85296c161a.json` 的目录步骤已由 Root 正常 Ctrl-C 结束；
  只读复核显示 Host 已停止、MCP 已停用、gateway 已退出、9543 已关闭、owner 记录0，
  `cleanup_complete=true`，Provider/model 均 `NOT_RUN`。不重发该旧流程，也不把其元数据
  通过升级为真实浏览器 Cookie 安全或金融链路通过。
- 相关 Ruff、Black、isort、索引及文档检查由主任务绑定最终候选。Mypy 的既有
  `multiuser/__main__.py` `structlog` 重复定义已用 HEAD 基线复核；本修复不冒称消除该债务。

生产开关、修正后的真实 WeKnora OAuth、Skills/MCP/沙箱、FinGPT/Claw 完整任务链及
最终候选 CI 由主任务继续；本报告不以登记回归或目录响应冒称业务替换完成。
