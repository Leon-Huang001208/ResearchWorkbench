# WeKnora MCP 客户端登记与原 Host 兼容

宿主：Mac mini / macOS arm64；功能修复。本轮仅调整既有入站 MCP 的登记校验，
不安装依赖、不启动模型、不更新常驻配置，不声称 Windows/Linux 原生或真实 WeKnora 链路通过。

Product-Progress: not-required — 仅修正操作员显式 MCP 配置的兼容性，无产品界面或已启用功能变更。

## 问题与改动

既有 WeKnora 客户端被错误绑定到 `service_only`，并拒绝与 RWB 共用 hostname 的
不同 HTTPS origin。因此现有 RWB 443 + WeKnora 9443 的部署无法登记，而切换
`service_only` 又会改变原 Host 生命周期。

`mcp_facade/config.py` 与 `multiuser/__main__.py` 解除这两项耦合：
已有 DSH 与仅服务模式都能显式登记；必须启用 MCP，完整回调仍由规范来源固定生成。
同一 origin、非法路径/查询/片段、未批准域名仍拒绝。未登记、未启用仍关闭。
原 `rwb.read`、四项冻结工具、PKCE、issuer/resource、旧 grant 与材料批准行为未改。
WeKnora Bearer 登录不替代 RWB 浏览器登录；两个 RWB 网关不能据此共用同 hostname
并期待 Cookie 按端口隔离。

实际隔离验证还发现 `multiuser/origin.py` 和 MCP issuer 校验把合法 Tailnet HTTPS
限定在 443，无法使用不影响生产的独立 9543 入口。最窄修正允许规范非默认 HTTPS 端口，
元数据与准确 Host/Origin、issuer/resource 继续含端口，非法端口、地址与路径仍拒绝；
默认 443 行为保持。不增加代理或任意转发头身份来源。

模块合同及安装说明同步更新。`requirements/web.in`、`requirements/web.lock`、
`scripts/setup_web.py` 与公开一键安装入口无依赖或安装行为变化；最终同候选
Mac Bootstrap 干净安装仍由主任务与 CI 验证。

## 实际验证

- RED：先补配置、Doctor、原 embedded resident 反例，旧实现实际 5 项失败，
  分别命中 `service_only` 耦合和同 host 回调拒绝；没有改产品后再补失败记录。
- GREEN：14 项配置正反例及 Doctor/resident 共 18 项通过。
- 相邻回归：PKCE/重放、恶意回调、resource、跨客户端、原 grant 不可改绑、
  WeKnora 批准冻结读取、HTTPS 登录导航、非法回调与持久开关共 19 项通过。
  两组共 **37 项独立用例 PASS**；均为 WIP 验证，不冒称最终 exact-SHA 验收。
- 9543 增量先观察旧实现 3 项目标失败，修后 **18 项 PASS**，含 SDK ASGI 元数据
  issuer/token endpoint/resource 的准确端口、错误 Host/Origin 端口 403 和原非法来源负例。
  其中 embedded resident 是前批同例在新增 DataHub scope 下复测，不把两批计数直接相加。
  此层未建立真实 TLS/Tailscale 或执行 OAuth；真实链路由主任务继续。
- 全部真实 pytest 执行使用已有批准 Python，经 `test_artifact_retention.py run` 串行、
  每批不超过 20 项；成功根已由原工具回收。必要结果在本机任务证据目录。
- 首次 GREEN 的一个负例错误码预期与旧有 `server_origin_invalid` 不一致，
  更正测试预期后复跑 18 项通过；不扩大产品修复范围。
- 相关文件 Ruff、Black、isort 与 `git diff --check` 通过。Mypy 检查的既有
  `multiuser/__main__.py` `structlog` 重复定义另记，不据此宣称类型检查全绿。

配置/HTTP 替身回归没有真实账号授权、Provider 或模型请求。生产开关、WeKnora
OAuth、Skills/MCP/沙箱、FinGPT/Claw 完整任务链及最终候选 CI 由主任务另行验收。
DataHub 实时查询是后续独立接口增量，不由本次客户端登记修复冒称实现。
