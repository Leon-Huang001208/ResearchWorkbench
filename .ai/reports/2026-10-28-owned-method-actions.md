# C3/C4 自有方法动作切片

宿主：Mac mini / macOS；任务：Web 功能开发。工作区基线
`397365b1c565636eb1b8c9955efecad5d18d627d`，沿主任务已启动 Harness，不重复初始化。

已实现三份 `kind=skill` 版本化方法包、冻结 stdlib 原件动作、严格 query/limit 与问题预置适配。
没有增加模型循环、引擎、供应商调用、依赖、秘密、部署或 schema 数据库迁移。

RED：新增参数测试先因模块缺失失败，证据 `/tmp/rwb-c3-actions-3V1xlNQt/red.log`。
首轮 GREEN：参数/原件 32 tests PASS，Catalog/冻结脚本 3 tests PASS，证据同目录
`green.log`、`packages.log`。该目录已登记 owner.json。
后续当前纯模块目标集 `target3.log`：43 tests PASS；Ruff、Black、isort 对本切片 Python 文件通过。
实际重开三份已有官方摘录的原 SHA（MSFT income/cashflows、FOMC September），不等于新抓取、完整文档
或 live 来源证明。未执行 mypy（现成环境 librt 不可用），不安装依赖补门。

当前明确限制：普通 code 脚本没有现成 Host codeSHA/callID/artifact 完成绑定；主任务已确认
需要受限 method_execution 接线，暂不将普通本地脚本或台账算作 Native ran。参数适配尚未连接
实际入口，因此不更新 C1 注册表为 mapped/ready/callable。真实模型和外部来源 NOT_RUN。

模块合同与边界见 `docs/research-web-owned-methods.md`。独立 SPEC/QUALITY、完整 Router、
本地 CI、Mac 干净安装及发布交由主任务聚合，不由本切片自评替代。
