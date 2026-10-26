# 资产分钟K任务报告

macOS功能开发，task asset-minute-k-20261026，基线bb40c791。目标1/5/15/30/60/120分钟K横排直达按钮，原分时/日周月/副图/筹码保留，按原安全门部署，登录/会话/数据不变。

已实现封闭按需API、原Workspace/DataHub/Provider链、有界窗口/账号缓存/真实SDK见证、统一因子OHLC及均价复权/量额原值、隔离派生快照和日线筹码桥接。固定字段字典先证实股/元；真实样本辅助字段矛盾单独标记、隐藏相关计算均价，原始证据保存。

实际证据在用户私有logs/asset-minute-k-20261026：包含除权日的两天六周期/三口径OHLC及1m聚合对照无差异；厂商复权量改变，产品保留原量额。修复后实际Workspace→Broker→Provider18组合均complete，记录1311—2410根。合成离线合同93通过，独评缓存污染/因子摘要/失败口径标签问题已修。浏览器5分钟K已绘制且无浏览器错误，完整交互/Router/CI/同候选Mac安装仍待最终候选验收。

常驻部署NOT_RUN；原未知/活动排空阻断不绕过。源码通过、隔离实源、预览、合并与实际上线分别留证，无模型调用/生产写入/新依赖。Windows/Linux NOT_RUN不冒称支持。

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "分钟K沿原Host资产UI/DataHub/Broker/固定天软及不可变快照链，有界六周期和独立画布，不新增服务、数据库、秘密、依赖或研究引擎；新HTTP已登记Atlas，原三CI/安装及排空/保全拓扑保持。", "diagrams": []} -->

<!-- architecture-review {"group": "workbench", "structure": "unchanged", "reason": "分钟K沿原Host资产UI/DataHub/Broker/固定天软及不可变快照链，有界六周期和独立画布，不新增服务、数据库、秘密、依赖或研究引擎；新HTTP已登记Atlas，原三CI/安装及排空/保全拓扑保持。", "diagrams": []} -->

<!-- architecture-review {"group": "datahub", "structure": "unchanged", "reason": "分钟K沿原Host资产UI/DataHub/Broker/固定天软及不可变快照链，有界六周期和独立画布，不新增服务、数据库、秘密、依赖或研究引擎；新HTTP已登记Atlas，原三CI/安装及排空/保全拓扑保持。", "diagrams": []} -->

<!-- architecture-review {"group": "verification-workflow", "structure": "unchanged", "reason": "分钟K沿原Host资产UI/DataHub/Broker/固定天软及不可变快照链，有界六周期和独立画布，不新增服务、数据库、秘密、依赖或研究引擎；新HTTP已登记Atlas，原三CI/安装及排空/保全拓扑保持。", "diagrams": []} -->

本地阶段复核：完整Research Web JS1203通过、3原skip；近处Python306通过，新增严格请求/消费者取消见证另18项通过。Router15项本地门通过；Ruff/Black/isort近处通过。Python/JS独评前次问题已复核无新增高优先缺陷；浏览器六周期/三种复权真绘图，负例失败保留旧图及口径已验。最终CI与Mac安装仍待候选，常驻仍未切换。
