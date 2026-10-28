# 专业 Agent 协作 MVP 实现与验证记录

> 任务记录：本文件记录当前未完成验收的候选，不是生产就绪声明。

## 身份与授权

- 宿主 macOS，Web 功能开发；本平台目标 Native／Mac Docker Desktop。Windows/Linux 产品验证 NOT_RUN。
- 基线 `1be480183187f181dbcee486d943aabb3559c9d5`，分支 `codex/specialist-collaboration-20261028-specialist-collaboration`。
- 原 checkout 出现 dataless 文件和未知归属的过期安全锁；未删锁、未覆盖源码。从同一已核验 GitHub remote 建立干净隔离 checkout，通过 git_safety fsck 后由正式入口建立 worktree。
- 用户授权仅创建 PR，不合并、不部署；真实模型调用须先估算并确认总费用，本轮没有调用。

## 已实现候选

- 四类不可变专业角色，冻结现有能力中心 Skill 版本、编译摘要及资源清单；独立子上下文，实际原生方法读取另行核验。
- 动态 DAG、依赖与修订校验，输入变化和证据版本变化使下游失效；私有账号账本保存计划、尝试与调用身份，不保存第二份聊天正文。
- 原生 continuable 子会话与持久 reserve／dispatch／accepted 阶段；取消请求不冒充终态，未知提交不重放。支持明确续跑及历史见证对账。
- 每个原生模型请求的 Agent/turn/step 去重、预算准入和截止约束；缺失用量保留未知。按时完成的资格冻结，不随查看时间到期。
- 现有界面的显式协作、未确认预算、节点状态、部分成果和明确续跑；最终接受仍由原报告质量链与专项否决共同控制。
- 原有 Checks／Mac Bootstrap 步骤追加专项回归、模块导入和单个新UI模块字节核验，没有新增依赖、runner、job或延长超时。

## 实际验证

| 项目 | 状态 | 证据 |
| --- | --- | --- |
| 干净 source checkout 的 Git fsck／无锁检查 | PASS | git_safety check 实际回执；未修复原 checkout |
| 新 checkout Harness 初始化、隔离分支 | PASS | 正式 Harness 与 git_safety delivery start 回执 |
| Node 24.19.0 专项及邻近界面测试 | PASS | 106 passed，0 failed，0 skipped；`logs/specialist-final-focused-node24.log` |
| 文档治理目标回归 | PASS | 8 passed；`logs/specialist-doc-governance.log` |
| JS 全量首轮 | FAIL | 1540 passed／4 failed／1 skipped；`logs/specialist-all-javascript.log`。文档缺链已修复并重验；其余3项缺项目 Python 环境 |
| Python 编译与 diff whitespace | PASS | compileall 与 git diff --check 实际 exit0；不是行为测试 |
| Router | 已规划 L4 | `logs/specialist-verification-plan.json`，受管 manifest 14项摘要已核对；候选尚未提交，最终SHA必须重新绑定 |
| Python pytest／ruff／black／isort／mypy | BLOCKED | 已有环境缺 pytest，原依赖部分 dataless；旧归档环境也不完整。未安装或修补未经批准的依赖 |
| Native／Docker 产品与浏览器整合验收 | NOT_RUN | Python 验证环境尚未具备，不用离线JS替代 |
| GitHub 原三门／同候选Mac安装 | NOT_RUN | 未推送，未创建PR，未进行跨平台dispatch |
| 真实模型、取消及重启小样本 | NOT_RUN | 费用授权关口未开启 |

## 审查与修复

已进行独立 Python／JavaScript 和界面接入审查。发现并修复：专项否决被末尾接受逻辑覆盖、取消首次发送锁竞争、父任务停止后的恢复接线、已完成结果随deadline过期、证据同ID覆盖导致旧结论复用、Skill只声明未实际传入、reserve到dispatch的崩溃空窗，以及取消该空窗时丢失提交阶段。修复后的 Python 行为测试尚未执行，不据静态修复宣称这些平台行为已验证。

## 费用与剩余工作

离线代表性首个请求至少需要48613保守预留单位，未含全部实际历史；新界面未确认默认200000、12次请求，旧已确认草稿保留原值。预留单位不是精确Token或人民币费用上限。真实小样本仍须按实际选择的模型、当前官方单价、请求与故障场景测算，再确认总费用。

当前保留源码 worktree 和分支。须获准在任务隔离环境安装仓库声明的Web依赖及测试/静态工具，完成Python与L4实际闭包、最终独评、Native/Docker和适用CI，再创建待审PR；不自动合并或部署。该状态为 BLOCKED／未完成验收，不是 cleaned 或交付完成。

## 依赖授权后的验证更新

用户已明确同意在本任务独立虚拟环境安装依赖。已安装哈希锁定Web依赖及已批准测试/静态工具，pip check通过，未修改产品依赖声明或全局环境。

- 专项Python首轮78 passed；原生控制入口补充后API模块7 passed。
- 相邻Python回归496 passed、2 skipped、1 failed；失败为旧工具目录精确集合缺少本次四项新工具，已更新集合并定点复验1 passed。未将整轮重写为全部通过。
- 完整JavaScript1544 passed、1原有条件skipped、0 failed；日志specialist-all-javascript-validated-env.log。
- 专项及改动集成文件Ruff通过，Black/isort检查通过；mypy专项7源码文件通过。
- 当前不再受测试依赖安装阻断。完整L4、本平台Native/Docker、最终评审和远端CI尚未完成；未创建PR、未合并、未部署、未执行真实模型。前述BLOCKED安装记录保留历史归属，不代表当前仍需重复安装批准。
