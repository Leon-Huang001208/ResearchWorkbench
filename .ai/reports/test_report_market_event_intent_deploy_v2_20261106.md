# 事件手动意图与市场入口修复：V2部署操作员

日期：2026-11-06。任务：market-event-intent-fix-20261106。宿主职责：macOS功能修复与已授权Native部署准备。
本子任务只修改原操作员、其原测试、gateway-upgrade合同及本报告；网关／sidebar产品由独立worker及根任务交付。
没有安装依赖、操作服务、Git提交／远端／部署或委派。

## 封闭身份与产品阶段

- 新入口：apply-market-live-v2／reviewed-market-overview-live-v2。
- PREVIOUS：a76ecfdfb1b1b7a35c508d15ccf16222ed20423c。
- P0：a2e97c3110b4495a0ae00df1123da400ab8a15e8，仅网关已有意图头转发及相关测试／文档。
- 最终P1：974628a808627a68d732f8d620c4b34ae10a9b3e，包含P0及sidebar五个可见入口修复。
- V2尚未提交／发布前，仅新V2的PAYLOAD、其新增固定值测试及新V2文档由P0更新至P1；PREVIOUS不变。
- EVENT、NAV、LIVE1原固定常量及EVENT旧组合祖先链与HEAD AST比较保持原样；LIVE1四逻辑ID测试整个AST不变。
- 实际Git已核验a76→P1祖先关系。产品P1→最终target、最终清洁源码与资格仍由正式交付复核。

## 运行与保全约束

复用原version4三锁、BirthFence、永久恢复source、独立primary/gateway仓库身份及目标对象存在检查。
全账号64MiB业务索引、@events、@dossiers、会话、模型配置与历史原件按原事务保全和恢复。
EVENT_SAFETY_MODES仅四个封闭身份；EVENT_PRESERVATION_MODES是同一集合别名。
MCP严格回滚子集为NAV／LIVE1／LIVE2：旧配置严格is False、前进和回滚local/private实际health严格is False，
保留loaded／PID／出生／源码／配置观察窗；错误码维持NAV专属或既有MKT专属分派。
旧EVENT/db2缺字段回滚豁免不扩至V2。所有Native严格空列表、Host／后台／Workflow／market inflight空闲门保持。
采集日程关闭原件证明在准备、空闲、切换、回滚和恢复边界重验；不启用采集、MCP、计划或模型，不进入TRIAL。
固定a76→P1→target祖先及两份diff完整路径并集的blob／模式冻结；P1后仅MODULE、原TEST、docs／报告可变。
额外app、scripts、其他tests、README、outputs、依赖、workflow、删除及不受支持模式继续拒绝。
锁文件实读SHA-256：7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102；
evidence实读：193f4fcc7e27ab1fd9fd87c4d30a0ca200476fe74c6cc4c6c7dad6bb8ce63988。
根任务记录a76现场双health MCPfalse与所有collectionoff；本子任务未重新观察现场，部署前须再读，不把源码测试代替现场状态。

## 已执行验证

- PASS：AST及旧固定赋值、EVENT祖先分支、LIVE1四ID测试AST保全核对。
- PASS：Black --check、Ruff check、isort --check-only，仅两个Python文件；git diff --check。
- P0 PASS：先真实collect-only再冻结20具体NodeID，正式test_artifact_retention.py run --mode wip运行20项。
  结果20 passed in 2.08s，exit0，JUnit tests20/failures0/errors0/skipped0。
  nonce=754156aff80e44f1b51131fd7d65151e，正式receipt status=retired，原临时root不存在。
  证据：logs/event-intent-v2-targeted-wip-receipt.json、logs/event-intent-v2-targeted-wip-v1.{xml,stdout,stderr,result.json}。
  使用指定临时.venv、PYTHONPATH本WT、PYTHONDONTWRITEBYTECODE=1和tmp_path_retention_policy=failed；未安装包。
- P1 PASS：仅collect-only，整文件3523唯一节点，其中V2相关186；未再运行pytest。
  证据：logs/event-intent-v2-p1-collect.stdout／stderr、logs/event-intent-v2-p1-all-nodeids.json。
  collection stdout SHA-256：a307103291ac7893afbab14900aa11bea542b1e454c857bec13bde7aa36ccc5b。
- P0测试原件保留；它们不能认证更新后的P1最终组合。最终exact-SHA完整受影响闭包、独评、三CI／Mac安装仍NOT_RUN，交由根任务。
- 实际Native切换／认证事件POST与五入口验收／现场MCP和采集关闭／保全／最终资源收尾：本子任务NOT_RUN。
- Windows／Linux原生及Docker产品：本子任务NOT_RUN，由对应范围任务负责。

## 静态冻结文件

- `research_workbench_entrypoint/resident/model_provider_upgrade.py`: `ed404fc859f81605dc6e0c895c1290b9f473110f95feda8c8c4eccf02cc887fc`
- `tests/research_web/test_model_provider_upgrade.py`: `f6b19ee4cd23196b6a2690b13a610ab57255e0beb17ac363049be579e1916506`
- `docs/research-web-gateway-upgrade.md`: `adb6150855e40045c8b0b86a1fd087122480bf7cf9581a2ffb0e5f3ab689f501`
