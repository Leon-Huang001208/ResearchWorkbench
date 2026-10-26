# Wind启动保全热修复报告

最后更新：2026-10-22。任务`wind-startup-preservation-20261022`，08aa基线。宿主macOS Mac mini，既有Web/Native启动兼容功能修复；本平台范围是本机回归、原通用仓库门、同候选Mac安装CI，以及root另行执行的精确恢复/实际部署。Windows/Linux产品原生及实机未执行，保持NOT_RUN。本文为文档分工检查点，不提前认证主任务的最终候选或恢复/部署。

## 故障证据与修复边界

主任务对真实v3部署的只读对账确认：原24项业务键与12个账号完全未变；Store内存setdefault新增asset_history_jobs/asset_history_keys/chart_preferences后，Automation启动沿原合同无条件save，使原磁盘缺失键被物化。严格保全门据此拒绝切换；立项时自动回滚后仍fenced，需要root走既有受管精确恢复，不能把该状态写为已部署。

文档分工实际读取共同目录`/Users/leon/Desktop/Projects/ResearchWorkbench/.git/leon-engineering/deployments/wind-workspace-20261022/model-upgrade-result.json`：704字节，SHA-256 `f843eb003b513ddfc61fa537a4c870610964e1933adac8c9630147316a2cecd1`，末尾真实状态`recovery_required`。24键/12账号对账及之后的恢复终态由root另存，本文未重算账号或业务内容，也不接触秘密。

之后root已完成正式恢复。文档分工仅读取同目录`recovery-complete.json`汇总，SHA-256 `9dfdba0b4e186a46a492ccd82cdd19c8ce1be7f0a89dd8dde7ee4af4a4dd661f`：frozen正式recover为`rolled_back`，恢复revision5495e64c0be08c9db58e336705db90584f8ba8b5、preserved=true；恢复index SHA-256为`676b5b716f572d40da1cd86669c32ec43034c40d2dc927b9fa35d850f47b38ae`，主事务与网关journal均已移除。8088/8089均HTTP200且revision5495，网关deployment_fenced=false。没有为本报告读取敏感index；这是旧版本恢复完成，不能称热修复或Wind产品部署成功。

修复仅限Store序列化。旧磁盘未有且仍精确为默认值（JSON类型也一致）的3个可选键仅在内存提供，启动或其他服务save不使它们落盘。某键第一次真实变化才写入；仅在原子替换成功后更新已持久化键集合。原有键含空对象/空列表/null，以及成功写入后恢复默认的键，永不因该优化删除。失败继续原日志/异常和原子写语义，不提前登记持久化。保全门、immutable controller、Automation启动合同、API、Provider、快照、依赖及部署流程均保持，不以跳过摘要、忽略键、清洗磁盘或改现场控制器解决。

## 变更—验证映射

| 源变更 | 回归与实际状态 | 对应文档 |
| --- | --- | --- |
| app/research_web/store.py的可选默认键/持久键集合/save payload | tests/research_web/test_store.py覆盖旧索引启动close字节保全、重复save、原有空键、实例默认值独立、写失败、真实使用后清空、零值/布尔型差异；实际执行结果由实现者/主任务回填，本文不预写PASS | ARCHITECTURE、DEVELOPMENT_MAP、03-data-files、DataHub |
| 文档合同与故障/恢复状态 | doc-sync、governance和Python索引只读核对；执行后追加结果 | AGENT_WORKFLOW、actions-budget、本报告 |

本轮不新增图节点/协议或持久格式，既有Store/快照数据流仍准确；不改图、架构HTML/PNG、CI结构或强制门。

## 安装合同核对

文档分工已只读检查以下五文件存在并记录当前字节/摘要到`logs/wind-startup-preservation-docs/installation-contract-files.json`，未编辑它们。当前任务没有新增依赖、安装入口或流程变化；这项核对不能替代同候选Mac干净安装、固定DSH构建、3081/8088健康和doctor，后者等待root真实证据。

| 文件 | 当前SHA-256 |
| --- | --- |
| requirements/web.in | `0ce60ea2ec5e945d23540ae74eb2aabc6448ac1c218a7e509af222cec321c4d5` |
| requirements/web.lock | `533f629afa9550a81345c2ed1e5bca17a50c7f581ae463ad0e5380f47cac2d92` |
| scripts/setup_web.py | `eee2aedf56469b92163a8d93d9795ba8ef3c464b8bd4ae52c8304799ac2de01e` |
| docs/research-web-installation.md | `a8d3ce2b50f06e56458c4c1ade59dc65a7878fcf9e484bf82a4072efb5cbda21` |
| .github/workflows/research-web-bootstrap.yml | `31666f9a10958361cd9c1b9de8045901bd98afe086de132abb55c69f6a5ff53e` |

## 文档分工实际命令与证据

日志目录`logs/wind-startup-preservation-docs/`。已实际执行：

- `gh api repos/Leon-Huang001208/ResearchWorkbench`：成功，PUBLIC/private=false，原JSON在repository.json。
- `gh api 'repos/Leon-Huang001208/ResearchWorkbench/actions/runs?status=success&per_page=5'`：成功，最近39725433303/39725433385/39725433371/39724266491/39724188738，56/562/409/643/64秒；只是先前基线/profile记录，不认证本候选。
- Python只读解析共同部署结果及五份安装合同文件，计算SHA-256，未改原件。
- `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/generate_py_file_index.py --check`：首轮FAIL，旧生成索引过期；首轮日志保留python-index-check.log，未跳过该门。
- 经root明确授权扩展索引文件责任后，执行`/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/generate_py_file_index.py`：成功，python-index-generate.log。再执行同脚本`--check`：PASS，python-index-final-check.log；未手改生成内容。
- `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/check_doc_sync.py`：首轮架构/API/图文及治理PASS、索引FAIL，doc-sync-initial.log；生成后再次运行整体PASS，doc-sync-after-index.log，11项变更无违规、785文件/100 current治理无违规、Python索引核验PASS。未改图、CI或门禁规则。

文档分工在六份指定文档、授权生成索引及报告之外，按最后一项真实constraints失败补齐`docs/architecture/research-web/readme-review.json`。已实际复核README的Web/安装/厂商可选/账号保全/部署说明，结论unchanged且原因具体，根README本身无需修改。原本地5门4PASS、constraints唯一FAIL `readme_review_not_changed`的日志保留；新增回执纳入完整12路径变更集，不放宽检查器。

## 已验证的本机检查点

源码在独立评审后未修改。当前Store SHA-256 `24c98033738b06d03dfde0309304ea50f1f160e7ec3f510c2e66a670e1b2cd29`，与`logs/wind-startup-independent-review/review.json`一致；另两测试文件也按该review的摘要核对。

| 检查 | 真实结果与来源 |
| --- | --- |
| 修复前红测 | 7 FAIL，`logs/wind-startup-preservation/store-red.log`保留 |
| Store＋历史目标回归 | 38 PASS，store-history-green.log |
| 18模块相关回归 | 527 PASS / 70.89秒、退出码0，related-regression.log；保留既有xlwings退出回调解析`[ NULL ] bundle path`的ValueError，不将该轮测试说成厂商可调用证明 |
| 独立复核目标回归 | 38 PASS / 7.91秒，`logs/wind-startup-independent-review/pytest.log` |
| 独立Ruff/Black/isort、Store mypy | PASS；mypy范围Store `--follow-imports=silent`，review.json，不宣称整仓mypy通过 |
| 独立评审 | APPROVE，critical/high findings为空；评审不替代常驻部署或同候选Mac CI |

README回执补齐后，以完整12路径重建Router计划：`--base 08aacb6d1723961a2846727627d569fd97a481f2 --task-context logs/wind-startup-final/task-context.json --signal unexpected_behavior --signal validation_failure`，每路径分别传入`--changed-file`。实际完整命令数组在`logs/wind-startup-final/plan-command.json`，新plan.json为schema4/L4，保留supplemental research-web-bootstrap；没有降级或移除门。原失败plan/constraints/local-results保存在同目录`.before-readme-review`副本。

完整变更清单`logs/wind-startup-final/changed-files.json`为12路径；按新计划实际并行重跑全部5门，完整命令/退出码/计时/日志摘要见local-results.json：

| 本机门 | 重跑结果 |
| --- | --- |
| research-web-architecture | PASS / 5.808秒 |
| project-constraints-local | PASS / 0.221秒；原readme_review_not_changed已真实修复 |
| research-web-verification-full | PASS / 5.810秒 |
| documentation-governance | PASS / 0.163秒 |
| python-file-index | PASS / 0.737秒 |

五门全部PASS是当前本机检查点，不是候选GitHub CI或新产品部署。文档分工未修改上述3个已审源码/测试文件，也未执行Git提交。

## 尚未完成的证据

热修复候选原三CI及同候选Mac安装、热修复实际部署/新版本认证浏览器和收尾尚待root另取证。旧5495正式恢复与解除fence已由上述汇总证明，本机源码/回归/独立评审与部署证据仍分层记录。本分工不Git发布、不部署、不供应商/模型、不读写秘密，不将旧版本恢复或本机通过冒充新产品部署成功。Windows/Linux产品和真实安装NOT_RUN，资源收尾未执行。

<!-- architecture-review {"group":"files","structure":"unchanged","reason":"仅修复Store旧盘缺失且精确默认三可选键的序列化时机，既有键及空值保留，原数据根/快照/原子写/严格保全门不变，没有新节点、协议或持久格式，现有资料流图准确。","diagrams":[]} -->
