# Research Web Phase 2C Automation 交付记录

## 范围

- 仅修改 Research Web、本地数据根、专属 DSH MCP 授权桥及对应 Web 文档。
- 不修改 Tauri、桌面打包、原生通知、PostgreSQL 或研究引擎。
- 旧报告日程和 API 继续可用；迁移必须逐项确认。

## 已实现

- 新增 `RESEARCH_AUTOMATIONS_ENABLED` 门控的通用 Automation，锁定 Skill、普通 Workflow 或报告
  Workflow 的版本与内容 SHA，并保存输入、工作空间、格式、日程和 MCP 工具快照。
- 一次、每日、每周、每月日程使用 IANA 时区；月度缺失日期回落月末，DST 空缺顺延到首个有效
  分钟，重复时间只触发第一次。服务启动只合并最近一次遗漏，不批量追赶。
- 每次触发创建独立 Claw 会话；重叠记录 `skipped_overlap`，版本漂移记录 `blocked_version`，无法
  确认的恢复记录 `interrupted`。研究失败不自动重试，手动重试创建带 `retry_of` 的新 Run。
- SMTP、通用 HMAC-SHA256 Webhook、飞书、企业微信和钉钉外发与研究状态分离；初次失败后按
  5/30/120 秒重试三次，事件 ID 在重试间不变。渠道秘密只进入 `ResearchWorkbench.Delivery`。
- Workflow“运行计划”展示通用任务、最近运行、下一次执行、投递渠道和旧报告日程兼容区。
  旧日程只有用户逐项确认且 Automation 原子保存成功后才停用。
- MCP Host 为 Automation 会话保存任务锁定快照，并在每次调用重核安装版本、schema 哈希、
  `read_only` 与 `allow_unattended`；私有数据须任务级授权，高风险工具不能无人值守。

## 安全与日志

- 自动任务、Run 和渠道投影只保存稳定 ID、状态、摘要引用和错误类型，不保存提示正文、工具参数、
  收件人、凭据或第三方响应体。
- 远程渠道只允许 HTTPS 或字面 loopback HTTP；SMTP 主机与邮件头受校验，通用 Webhook 使用
  `{event_id}.{timestamp}.{body}` 计算 HMAC-SHA256。
- 默认外发只包含状态、摘要和本机会话链接；产物引用须逐任务显式启用。

## 架构与视觉证据

- 图 02 增加 Automation service、原子任务事实/Keyring 与外部投递边界。
- Archify showcase：9/9，0 errors，0 warnings。
- 最终 HTML SHA-256：`01aed4e526e3876396e5b3575f4836623f5c57a74e005c3974e52b734ccff803`；规范 SHA-256：`fd63c80fc915d319f60b6804ec81048eb01e87af9005ac40862c6a51df4a9534`。
- 1440×900、1600×1000、1920×1080、2048×1320 自动包含性通过；1440 浅色与 2048 深色最终
  截图已人工查看。自动回执的 `visualReview` 保持原始 `pending`，未伪造为通过。

## 已执行验证

- Automation 与 MCP 聚焦 Python：41 passed，1 个 Starlette 上游弃用警告；包含投递中止不改研究
  结果、启动恢复 pending 投递及渠道索引/Keyring 原子回滚。
- Research Web Python 排除 3 个依赖本机损坏 pip 副本的离线 PyPI 安装用例后：878 passed、4 skipped、
  3 deselected、1 warning。未排除的首次全量命令为 877 passed、1 skipped、3 failed、4 errors：
  3 项失败均因工作树虚拟环境通过 `.pth` 读取到共享环境中缺失的 `pip._internal.cli.spinners`；4 项
  native error 因本机 DSH checkout 为 `c389f96b`，不等于项目固定 `c919b2a4`。未把该命令声明为通过。
- Research Web JavaScript 全套：254 passed；`research_web_capabilities_ui.test.mjs` 单项为 34 passed。
- 相关 Python 文件通过 Ruff、`black --check`、`isort --check-only`；12 个源码文件 mypy 通过。
- Research Web 架构门禁：52 passed；架构/文档映射无 violation；API Atlas 为 178 项源码声明、
  176 个唯一操作、9 个分类。
- `tests/e2e/research_web_automations.mjs`：1440/1280/768/390 的 Light/Dark、reduced-motion 共 8 项通过，
  覆盖锁定版本、新建面板、手动重试、投递配置与秘密遮蔽。
- 远端 CI 状态在发布后补充。

## 未验证边界

- 当前不声明 Windows/Linux、桌面包、公网多用户、真实 SMTP/聊天机器人或任意第三方 MCP Server
  已通过。外部渠道和 Server 的可用性必须由用户配置后单独探测。
