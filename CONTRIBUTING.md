# 参与 ResearchWorkbench

欢迎提交可复现的问题、文档改进和代码贡献。请遵守[社区行为准则](CODE_OF_CONDUCT.md)。安全漏洞请通过[安全政策中的私密入口](SECURITY.md)报告。

## 开始之前

1. 查阅已有 Issue 和 PR。报告问题时提供版本或提交、操作系统、复现步骤、预期与实际结果。只提供脱敏的截图、日志和最小样例。
2. 涉及公开 API、权限、数据库、数据来源或部署边界的改动，先在 Issue 中说明目标、范围与验收方式。
3. 从最新的 `master` 建立短期分支。按[安装指南](docs/research-web-installation.md)搭建本地环境。修改代码前阅读[架构](docs/ARCHITECTURE.md)、[开发地图](docs/DEVELOPMENT_MAP.md)和[工程规则](AGENTS.md)。
4. 使用你有权提交的内容。引入外部代码、素材或数据时，在 PR 中标出来源、精确版本、适用许可和再分发依据。

## 提交 PR

- 将 PR 指向 `master`，说明用户可见变化、受影响范围、关联 Issue 和已执行的检查。
- 按[工程工作流](docs/AGENT_WORKFLOW.md)选择验收。只写实际验证过的平台和结果，标明未运行项。本地可先用 `python scripts/research_web_test_env.py --check --json` 检查共享 Python 测试环境。
- Python 源码变更按工程规则补齐相关测试、文档和任务报告。UI 变更提供脱敏的截图或复现步骤。
- 阅读 [ResearchWorkbench CLA 1.0](CLA.md)，并在每个含有你贡献的 PR 中用自己的 GitHub 账号留下以下确认。代表公司提交时，请同时注明获授权代表的主体名称。

> I have read and agree to the ResearchWorkbench Contributor License Agreement 1.0 for my contributions to this pull request.

维护者在合并前核对确认记录是否覆盖各贡献者及其提交。CLA 适用于确认所涵盖的贡献。已经存在的贡献按其原有授权处理。项目采用[源码可见许可](LICENSE.md)，第三方材料按[原有条款及范围声明](THIRD_PARTY_NOTICES.md)处理。
