# Claw 首页示例区移除

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅删除已授权的Claw首页示例、分类、案例卡片与对应样式事件，保留原编辑器和日程草稿入口，无接口或架构改变。","diagrams":[]} -->

macOS / Web UI迭代，隔离分支基线e2cb34c7f90961f005c3a312ca481f3be071d629。按用户要求删除整个“查看示例”区及6个首页案例卡片与分类；移除专用渲染器、五个无入口样例、分类事件和CSS。保留Agent日程新建任务所需schedule草稿与原data-claw-case事件，保留欢迎标题、编辑器、＋菜单、模型、发送/停止和逐题问答。

## 状态与证据

- 首页默认、输入、背景重绘、390/1440及明暗主题不出现示例DOM；输入框仍可填写。
- Agent日程新建仍回到Claw并准备每日收盘点评草稿，不发请求创建会话或任务。
- 编辑前原真实app事件回归新增“无示例”断言，实际FAIL（logs/remove-claw-examples/red.log）；修复后目标74项PASS。
- 隔离Chrome专属矩阵6组PASS，含明暗主题×390/1440无示例、输入框和日程新建回到草稿；完整JS/治理724项，722 PASS、2项既有DSH条件SKIPPED；项目约束、文档治理与Python索引PASS。浏览器首次新增日程断言早于异步草稿准备完成而FAIL，改为等待真实草稿内容后重验PASS；未改产品行为。最终候选CI和独立评审由受管回执记录。
- FinGPT与共享业务/执行接口不变，无依赖、安装器、数据库或DSH变更；原安装CI证明兼容。

## 边界

浏览器使用隔离随机端口夹具，拒绝外部请求，无真实模型、常驻服务或业务数据操作。尚未验证的浏览器/平台不声称通过；常驻部署不由源码/CI通过替代，需满足既有空闲、兼容、保全与恢复安全门。既有常驻部署阻断另在claw-resident-deploy-20261020报告中保留。

实际命令：`node --test tests/javascript/research_web*.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs`；`node tests/e2e/research_web_codex_navigation.mjs --focus-claw-welcome`；`node .agents/project-constraints.mjs --project . --changed-file <完整改动集>`；`node scripts/check_documentation_governance.mjs --project .`；`PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.12 scripts/generate_py_file_index.py --check`。日志见logs/remove-claw-examples及logs/codex-navigation-browser。
