# Wind工作区v3部署profile交付报告

最后更新：2026-10-22。任务：`wind-workspace-deploy-20261022`；基线master `a0ff3ae2e2ab92bad10ba8547e45027687ec7cc1`。宿主macOS Mac mini，任务为既有Native显式部署工具功能扩展，本平台范围为本机回归、通用仓库检查、同候选Mac CI及授权后的实际切换/认证页面/数据保全。Windows/Linux产品原生验收保持NOT_RUN；Ubuntu通用仓库门不充当Linux产品证据。

## 固定合同与边界

- 新mode仅`reviewed-asset-observation-v3`，CLI仅`apply-assets-v3`；PREVIOUS精确`5495e64c0be08c9db58e336705db90584f8ba8b5`，PAYLOAD精确`a0ff3ae2e2ab92bad10ba8547e45027687ec7cc1`。最终工具候选仍须最新基线、独立评审与原三门，不接受任意SHA替换。
- 仅操作员及相应测试/文档变化；已合并PR177产品、依赖、workflow、controller、evidence及架构HTML/PNG保持。旧v1/v2固定身份、历史恢复包、v4 journal、锁、BirthFence、空闲、全账号索引保全和自动白名单不扩大。
- 用户本轮明确授权常驻部署；真正apply只由root完成最终验收后持锁复核全部研究/日程/私有池/观察/DataHub/历史及真实Future空闲、冻结数据再执行。本分工不Git、不deploy、不厂商/模型、不引入依赖；当前常驻仍5495，v3候选CI与实际部署尚未执行，不能写PASS。

## v3本机验证

实现者完整operator模块398项通过；operator、resident、gateway近处组合590项通过，Ruff/Black/isort及diff检查通过。独立Python评审同组合590项通过并APPROVE，绑定operator `90f0684ac671f500bc5feea1c32e6b8871906a7cc43f4aeb707cee59834e27d9`及测试 `ad75f9d6ad507e3c60585002c0728d6d4daadc19c3b5a55ef855c4a5c260632c`。controller/evidence与产品基线逐字节相同。

Mypy候选与独立HEAD shadow均为原有两项PID可空类型错误，仅行号移动；新增错误为零，整体检查仍保留FAIL。完整18路径Router为L4；本地三项门全部通过，另行完整路径Project Constraints也通过。同候选约束、Checks及Mac Bootstrap三门仍待发布后实测，不使用产品候选的CI替代。

日志：`logs/wind-v3-impl/`、`logs/wind-v3-review/`和`logs/v3-local-gates/`。本报告不声称CI或真实部署已经完成。

## 产品既有证据与v3验收分开

主任务回报产品本地17项Router、真实6版本2261/6025行、浏览器17、Python/JS独立评审已通过；本报告没有重新执行这些工作。产品共同副本为`/Users/leon/Desktop/Projects/ResearchWorkbench/.git/leon-engineering/deployments/wind-workspace-20261022/`，不用旧feature worktree持续存在作为后续前提：

| 已实际读取文件 | SHA-256 | 可证明内容 |
| --- | --- | --- |
| product-ci-summary.json | `9ac26eab270ab1fd0b3f98c3f103b6acce4bc64b33c95d8107f5bbbf52a1a849` | 产品候选7218ac79e340d115087a1bf2bb4c5e52edf25070；checkout0a3eec3d6ea3c403be3362a67ddfca10da61e97e；tree617871648e289740d831c855129e104cef49e742；39720391600/39720391522/39720391774三门PASS |
| product-verification-result.json | `95704cb3dd95e59540ffe119e03b9d4e948a30db4eae81ecb694e4164e12841f` | 产品hostAcceptance/mergeReady为PASS/true，aggregateAcceptance仍NOT_READY、releaseReady=false；其中Linux标记只对应Ubuntu通用门，不是Linux产品原生验收 |
| profile-readiness.json | `b557973bbba7f54a1602dc74d5a817d1a866233044357cfafa31d9c993ed22b7` | 合并前READ_ONLY_PREPARATION_COMPLETE方案，内部payload仍UNKNOWN_UNTIL_REVIEWED_PRODUCT_MERGE；原件不改写，不当作当前v3实现/CI/部署PASS |

产品merge为a0ff3ae2；产品CI的Mac实际checkout及父5495/7218关系由主任务原证据维护。本次profile候选和部署回执必须重新绑定，不把旧产品tree/运行成功直接复制为工具通过。

## 变更与验证映射

| 范围 | 测试/检查 | 对应文档与结构判断 |
| --- | --- | --- |
| resident/model_provider_upgrade.py封闭v3常量/分派 | test_model_provider_upgrade.py既有真实Git/精确blob/拒绝范围/保全/恢复矩阵扩到v3 | 部署、安装、开发地图与架构01–05关联说明；不增进程/API/数据流，图及Atlas不变 |
| README及部署/安装宽映射文档 | check_doc_sync、governance、Python index --check | v3与旧v1/v2分开，产品/工具/实际切换分开；不改原生成HTML/PNG |
| actions-budget | 只读仓库与最近5成功run API | PUBLIC及墙钟时长；本轮不改CI结构、依赖或预算上限 |

## 文档分工实际执行命令

日志目录`logs/wind-workspace-deploy-docs/`。

| 命令 | 真实结果 |
| --- | --- |
| `gh api repos/Leon-Huang001208/ResearchWorkbench` | 成功，PUBLIC/private=false，repository.json |
| `gh api 'repos/Leon-Huang001208/ResearchWorkbench/actions/runs?status=success&per_page=5'` | 成功，最近5成功run39721709695/39720391774/39720391600/39720391522/39717416229，50/509/63/419/73秒，recent-success-runs.json |
| `python3`只读解析共同product-ci-summary/product-verification-result/profile-readiness并计算SHA-256 | 成功，摘要/语义见上表；未修改共同原件 |
| `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/generate_py_file_index.py --check` | PASS，现有生成索引已兼容本轮封闭常量/分派变化，无需重写，python-index-check.log |
| `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/check_doc_sync.py` | PASS，18项变更架构/API/图文无违规；治理784文件/100 current无违规，Python索引核验PASS，doc-sync-initial.log |

本轮API/图文完整性检查只读核对既有生成图，没有改图、重建HTML/PNG或重写Python索引。各文件本次交接hash保存在本分工`owned-paths-sha256.json`与完整`changed-paths-sha256.json`日志；本报告自hash由外部清单绑定，避免递归摘要。主任务后续编辑须重算最终候选清单。

## 尚未执行/限制

v3工具本机测试/格式/Router/独立评审、最终三门及同候选macos-14安装、实际apply/版本/全部账号数据保全/认证浏览器与资源收尾仍待主任务取证。产品已merge与旧产品CI不替代这些层级；Windows/Linux产品原生及实机NOT_RUN。用户已授权部署的范围保留，执行前仍需真实空闲和固定身份，未知状态不转成false或跳过。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅扩充原macOS Native显式操作员的固定v3身份与CLI分派，旧v1/v2/controller/evidence和v4事务保持，无新服务节点、协议、依赖或数据流，不重画现有图。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"原主实例及私网网关角色、账号Store/凭据隔离与索引保全不变，v3只绑定5495到固定产品a0ff3ae2，实际切换仍持锁证明空闲，不增加权限或拓扑。","diagrams":[]} -->

## 本次交接的全部改动路径与摘要

以下为静态检查点，不自动认证主任务后续修改；本报告自身hash见外部清单。

| 路径 | SHA-256 | 责任 |
| --- | --- | --- |
| `README.md` | `388ff8dd4e9ae94b1bff745503bfe09e989b90e52593896e5fdf7ea19e28ab1c` | documentation |
| `docs/ARCHITECTURE.md` | `41c9d76328417152171c25056cb5894b295532a5fa5194bab8d6e9602fceb2d7` | documentation |
| `docs/DEVELOPMENT_MAP.md` | `e2eebf2d6278c296c429106d79d827b9642ef3ab1e633971a22f78d33770644a` | documentation |
| `docs/actions-budget.md` | `18f9057df9b7f83452575df2f832196f19ce97bc231646c23d74bb6d8deeeaf9` | documentation |
| `docs/architecture/research-web/01-system.md` | `c33844a519899d61a908b477c5549e57fd7e174c3d2a0ce28a9725fc3ecdacb0` | documentation |
| `docs/architecture/research-web/02-research-runtime.md` | `88ce7085cd53854c35739fdd28b79e99a2fb06d983b2e3519f78f7f030869f03` | documentation |
| `docs/architecture/research-web/03-data-files.md` | `c06ee6bdf9bdedc7521a4c8cc02f230d128642005b921f035559d75ffc843b7a` | documentation |
| `docs/architecture/research-web/04-api.md` | `535682169f595ed005ce8b8cfd6739e3d72f51445e2bc8f775f889a932748952` | documentation |
| `docs/architecture/research-web/05-security-validation.md` | `224a91701cea3d84dc6b818ef1bac6ae7e361f5a4a04dafa3baec80257fb7227` | documentation |
| `docs/architecture/research-web/readme-review.json` | `24277a153055d9cdf5902b93ff8444ef6b36ad9682e1279a2ce2c5986ecd9803` | documentation |
| `docs/research-web-ai-news.md` | `f24e3cf8838bef175583b4e39a5e957c26adcd39f4e6acdb6fa473346c5f813b` | documentation |
| `docs/research-web-docker.md` | `8d800007865158db61da88a1d8d3be898f83217b6da3cc85e335b8b7e43debd4` | documentation |
| `docs/research-web-gateway-upgrade.md` | `6046e4dee9e392477bb43c1eef6a3e6a97fbddeb036ac30e97b56b81f5101d01` | documentation |
| `docs/research-web-installation.md` | `a8d3ce2b50f06e56458c4c1ade59dc65a7878fcf9e484bf82a4072efb5cbda21` | documentation |
| `docs/research-web-platform-support.md` | `1f57cd4988ae2c516cc53f044abf6da605c70de7ff9e4c024582a745fc87e287` | documentation |
| `research_workbench_entrypoint/resident/model_provider_upgrade.py` | `90f0684ac671f500bc5feea1c32e6b8871906a7cc43f4aeb707cee59834e27d9` | operator-worker |
| `tests/research_web/test_model_provider_upgrade.py` | `ad75f9d6ad507e3c60585002c0728d6d4daadc19c3b5a55ef855c4a5c260632c` | operator-worker |
| `.ai/reports/test_report_wind_workspace_deploy_20261022.md` | 外部changed-paths-sha256.json绑定 | documentation |
