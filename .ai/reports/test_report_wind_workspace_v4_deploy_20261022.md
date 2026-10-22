# Wind工作区v4部署profile报告

最后更新：2026-10-22。任务`wind-workspace-v4-deploy-20261022`，产品固定PR180真实merge `9b436613aad9136f4959c992c89dd72fc7354ed5`。宿主macOS Mac mini，本任务为既有Native操作员功能扩展。合并前依赖的654fa6只保留为历史草稿检查点；文档分工只改docs、README、自己的报告及必要生成索引，不改其他worker的操作员/测试，不Git发布、不部署、不调用厂商/模型、不处理秘密或服务。

## 合并依赖与固定合同

新profile `reviewed-asset-observation-v4`，CLI `apply-assets-v4`，PREVIOUS精确固定`5495e64c0be08c9db58e336705db90584f8ba8b5`，PAYLOAD精确固定`9b436613aad9136f4959c992c89dd72fc7354ed5`。主任务已fetch核定PR180真实merge的父为08aac/654fa，tree `1aff5360808c835a6096af751e942b6692497bfa`，与候选654fa6和PR preview2e069相同；不使用任意SHA、候选或preview替代正式产品身份。

历史草稿检查点：文档初轮只读PR180 API时state=open、merged=false、head=654fa6dc7d63fdafc67c96f7f1b6755d100c1d2f，未将当时的merge_commit_sha当真实合并。原响应保留在`logs/wind-v4-docs/product-pr180.json`；它是历史记录，不覆盖已获正式merge事实。操作员/测试由其他worker正式repin后重新验证；先前草稿677项局部回归与条件APPROVE仍是草稿检查点，不能转写为最终pin通过。

旧v1/v2/v3固定PREVIOUS/PAYLOAD及恢复语义、现有version4 journal、controller/evidence字节、锁/BirthFence、严格全账号索引保全和依赖/CI结构均保持。profile版本4不表示journal格式升级。只允许封闭payload/干净源码/完整路径并集/blob/模式/祖先和原发布仓库身份，不能部署任意SHA或附带额外产品/依赖/workflow/图表HTML/PNG差异。

## 已合并产品的真实CI证据

共同来源为`/Users/leon/Desktop/Projects/ResearchWorkbench/.git/leon-engineering/deployments/wind-workspace-20261022/startup-ci/`，本分工已只读核对summary及三个proof。summary.json SHA-256 `d4062fa5de30fa1555e4e4ef4ea7c32f93769d6e1f38f7937e5c0a47bc950092`，绑定候选654fa6、preview2e069及同tree；主任务的正式merge父/tree核验另存，不伪称由本分工运行Git。

| 产品门 | 实际运行及checkout | proof SHA-256 |
| --- | --- | --- |
| Project Constraints | 39730343750 PASS；自动PR checkout2e0690152d0ac18f06fe5e7cf7d54b2f9bfaaafe | `5ee4efd4b21a06077eb91dab901f1a2eeb5505cb41e6699f0c54b007b1c529d1` |
| Research Web Checks | 39730343679 PASS；自动PR同一checkout；Python1803通过/11条件跳过，JS871通过/2跳过 | `ed71513abb06ccec0dca74348071cc23225b53a2d1e734f52fb886c54ae36ab5` |
| Mac Bootstrap | 39730452006 PASS；手动Mac实际checkout654fa6dc7d63fdafc67c96f7f1b6755d100c1d2f，581秒 | `30c36ceefad6b9e22fb04d10ed6cd24130fa3b30fecb535f6e8f1c535a8bb931` |

Mac安装artifact12405650153，artifact SHA-256 `8a1a04cf8c6a0e7603e7f1ef53523c06052ee726505d7beea4b804280bcde6e1`；Doctor ready、3081/8088、DSH `7ecf564f2e09b829240c5553687223bdd1e2df73`及其16098文件闭包/锁一致性、15项静态资源字节匹配均已通过。CJPY0.5.2依赖就绪，天软未配置且不可调用的投影已通过；不表示真实厂商调用成功，modelAcceptance仍NOT_RUN。

共同startup-verification-result.json的schema3 validator为hostAcceptance PASS、mergeReady=true，aggregateAcceptance NOT_READY、releaseReady=false。其中Linux PASS仅对应Ubuntu通用仓库门；Windows/Linux产品原生/实机仍NOT_RUN。这些产品证据不认证v4操作员最终pin后的本机/独立评审/候选CI/安装或部署。

## 旧v3失败与正式恢复

旧v3实际部署因Store启动物化三项默认键而触发严格保全拒绝。已有启动热修复的38目标/527相关回归及独立APPROVE详见原报告；这些是产品热修复证据，不转写为v4工具验收。

已只读复核共同目录`/Users/leon/Desktop/Projects/ResearchWorkbench/.git/leon-engineering/deployments/wind-workspace-20261022/recovery-complete.json`，SHA-256 `9dfdba0b4e186a46a492ccd82cdd19c8ce1be7f0a89dd8dde7ee4af4a4dd661f`：精确SHA还原并由冻结正式recover得到rolled_back，revision5495e64c0be08c9db58e336705db90584f8ba8b5、preserved=true；恢复index SHA-256 `676b5b716f572d40da1cd86669c32ec43034c40d2dc927b9fa35d850f47b38ae`。主事务与网关journal已移除，8088/8089均HTTP200并为5495，网关deployment_fenced=false。文档分工未读取敏感index或修改任何恢复原件。旧版恢复完成与v4产品/工具部署未完成分开。

## 文档与验证映射

| 源码责任 | 对应验证 | 文档合同 |
| --- | --- | --- |
| model_provider_upgrade.py的v4封闭常量/previous/payload/CLI分派，由其他worker负责 | 原test_model_provider_upgrade.py扩展固定范围、四profile矩阵及恢复/保全；正式产品pin后重新绑定结果 | gateway-upgrade、README、开发地图及架构01–05 |
| 文档/安装/平台范围和README复核 | doc-sync/governance/Python索引静态检查；只认证文档一致性 | README与readme-review、安装/Docker/AI资讯/平台、AGENT_WORKFLOW/actions-budget |

部署/产品/API/资料流拓扑未变，无新运行进程、HTTP或业务schema，不重画图、不改架构HTML/PNG或Atlas；旧固定恢复字节和严格门不削弱。

## 安装与Actions核对

五文件已按现有合同只读核对：requirements/web.in、requirements/web.lock、scripts/setup_web.py、docs/research-web-installation.md、.github/workflows/research-web-bootstrap.yml。本轮仅安装文档新增v4固定版本说明，其余机器文件不改，没有新增依赖/入口/流程。当前摘要留`logs/wind-v4-docs/installation-contract-files.json`；产品Mac安装已按上节通过，v4操作员最终同候选仍须原Mac安装门，不能用产品或当前已有环境替代。

预算核对时GitHub API为PUBLIC/private=false，最近5成功run39730343750/39725433303/39725433385/39725433371/39724266491为64/56/562/409/643秒，历史原件保留。产品随后取得三门PASS，v4操作员仍须自己的最终候选门；沿原三个CI，不新增job/runner/timeout/依赖，本分工不手动rerun或派发Windows/Linux产品任务。

## 本分工实际命令与当前状态

日志目录`logs/wind-v4-docs/`。已实际执行`gh api repos/Leon-Huang001208/ResearchWorkbench`、`gh api 'repos/Leon-Huang001208/ResearchWorkbench/actions/runs?status=success&per_page=5'`和`gh api repos/Leon-Huang001208/ResearchWorkbench/pulls/180`，均只读成功。Python只读核安装五文件及共同recovery-complete摘要，未修改秘密/恢复文件。

已实际执行`/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/generate_py_file_index.py --check`：PASS，python-index-check.log，原生成索引已兼容，无需改写。随后`/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/check_doc_sync.py`整体PASS，doc-sync-initial.log：19项任务变更无架构/API/图文违规，文档治理786文件/100 current无违规，Python索引核验PASS。该结果只认证当前草稿文档一致性，不认证v4固定产品身份或工具运行。

另按完整19路径逐项`--changed-file`实际运行`node .agents/project-constraints.mjs --project .`，退出0、violations为空；完整命令数组在constraints-command.json，输出constraints.log。文档责任共17路径：15份docs、README及本报告，精确路径/字节/摘要留owned-paths-sha256.json；操作员与测试另外2路径由其他worker维护，未覆盖。后续真实merge/阶段修订须按最终changed set重新核验。

正式9b4366产品pin后，操作员677项本机回归PASS/41.19秒；最终独立评审APPROVE、677项PASS/46.76秒，runtime/test摘要与冻结源码一致，证据`logs/wind-v4-independent-review/final/review.json` SHA-256 `fc62bd600f3b180637608fd5b4358b7975c864631053532e1b53c1d5cf54eeaf`。Ruff/Black/isort及silent目标mypy通过；独立完整imports仍有14项/6文件既有错误，与同HEAD shadow归一化完全一致、无新增，不与实现者另一2项scope混淆。v4候选原三CI/Mac安装/实际部署仍待root证据，不提前写PASS；Windows/Linux产品原生/实机NOT_RUN，资源收尾未执行。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"v4只为既有macOS Native操作员增加封闭旧5495及PR180真实merge产品身份，旧profiles/controller/evidence和version4事务保持，无新运行节点、协议、依赖或数据流，不改图。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"主实例/私网网关、每用户Store和凭据隔离、严格全账号索引保全均复用原合同，产品CI与旧恢复不代替v4最终资格，无新权限或拓扑，原图准确。","diagrams":[]} -->
