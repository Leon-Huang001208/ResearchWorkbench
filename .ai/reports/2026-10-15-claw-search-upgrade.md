# Claw 原生搜索升级

宿主：macOS arm64；类型：Web 功能与固定 DSH 升级。用户已授权推送、更换 pin 和部署。

Native 候选 `7ecf564f2e09b829240c5553687223bdd1e2df73` 增加显式部分搜索、授权范围交集和有界覆盖报告。RWB 传当前产品/模式会话范围并严格验证覆盖计数。旧 descriptor-v2 本身仍不搜索、不恢复，源文件不改写。

本地 Native 查询/RPC 103 项、Web 搜索 Python 49 项、固定新 DSH 下完整 JS 581 项（零失败、零跳过）、完整 API 199 项、安装 121 项及容器/启动合同 235 项通过。真实独立 Native 候选通过公开安装器，已验证实际 HTTP 命中和零命中受限提示，旧格式夹具字节、修改时间及目录不变。Windows/Linux 产品验收由对应设备接手，不能视作 Mac 证据。

<!-- architecture-review {"group": "dual-runtime", "structure": "unchanged", "reason": "保留现有唯一DSH、私有RPC、产品归属索引和Automation，新增显式搜索覆盖信息与请求范围，不引入持久正文库、数据库迁移、新执行服务或调度节点。", "diagrams": []} -->

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "保留现有唯一DSH、私有RPC、产品归属索引和Automation，新增显式搜索覆盖信息与请求范围，不引入持久正文库、数据库迁移、新执行服务或调度节点。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "保留现有唯一DSH、私有RPC、产品归属索引和Automation，新增显式搜索覆盖信息与请求范围，不引入持久正文库、数据库迁移、新执行服务或调度节点。", "diagrams": []} -->

<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "保留现有唯一DSH、私有RPC、产品归属索引和Automation，新增显式搜索覆盖信息与请求范围，不引入持久正文库、数据库迁移、新执行服务或调度节点。", "diagrams": []} -->

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"在既有macOS Bootstrap空搜索冒烟增加真实覆盖字段断言，不新增workflow或runner，保留原concurrency、超时及跨平台dispatch边界。","diagrams":[]} -->

## 真实模型与文件证据

候选运行新固定 DSH `7ecf564f2e09b829240c5553687223bdd1e2df73`，沿此前批准的本机 Keychain 复用执行一次最小工具回合。正式 Key 和模型选择未修改。原生 turn/end 为 completed（seq 23），research_run_script 实际完成，最终回答非空。下载 native-pin-check.md 为30字节，SHA-256 `7c4b0607acfb2632318df5bbfb9c892779bd0c5d85b36a4074d3b9efb579a594`。不查询市场数据，不创建日程。精确工具准入只绑定已验证的新提交、官方 provider 与 deepseek-flash。

候选浏览器验证真实正文命中和零命中的部分覆盖提示；390px/1050px 文档均不横向溢出，临时视口已恢复。

## 发布与限制

Native Git HTTPS 上传失败后，通过 GitHub Git 数据 API 非强制更新任务分支；远端提交7ecf564f与本地已审9c65de70的文件树均为 `769b1aeca14e03b7c0d7084adc953a31b301fa9f`，提交身份差异来自服务端时间元数据。RWB只固定真实远端SHA，不使用本地伪造版本。

完整导入链 mypy 报告14项未触及代码的既有错误；与原master基线逐项复现一致。修改模块的定向 mypy、Ruff、Black、isort通过；没有修改错误代码屏蔽配置，也不将该结果称为全仓mypy通过。

CI、合并和正式部署结果以绑定最终候选的私有交付回执为准；源码报告不将未执行外部门认证为PASS。原始旧格式正文仍不读取、不迁移、不恢复执行；两类未搜索数量分别来自格式拒绝与请求范围中原生不可见记录，页面合计提示。
