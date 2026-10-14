# 冻结来源接续为持续公开采集

macOS功能开发，hot-intel-continuation，父候选b364d77cc；本切片未提交。目标仍完整Goal，无新增依赖/预算。

真实缺口：原OpenAI/Fed为frozen_acceptance_subset，不参与public_feed调度。实现明确useCatalog+reason、固定目录同operator、版本/UUID审计与owner事务；JSONB合并保留原配置和大整数，普通worker无config权限。CLI与typed Host支持，旧参数/replay保持；来源表单新入口待补。

unit RED1FAIL→GREEN1PASS；真实PG activation/角色/旧owner/材料版本/指纹/大整数/目录不可用重放1PASS，TypeScript检查PASS，Python51PASS/1anyio warning。限定Python审查Approve；TS两P2（hash顺序与重放依赖目录）修复并加真实PG反例，复审确认关闭。治理111PASS、文档/项目约束/索引PASS。新增CLI专属测试第一次因未mock正常解释器准入失败（环境门正确拒绝），补夹具后继续验证，保留失败日志。

source-catalog-live-first-driver-error.json保留驱动误把manager.sources list当dict的失败，finally正常停止，未激活。修正后正常setup/start/签名source control四源真实采集成功。最终source-catalog-live-final-receipt.json证明OpenAI/Fed两次计划采集、inbox排空、零model调用。早期canonical-json-v1审计不重写；最终新审计为postgres-jsonb-text-v1。两次同参数UUID重放没有第二次写入，全部旧材料/研究快照保留。预算须最终复查18/77375/10464microUSD，上限20/100000/USD1。

最终CLI/Python52PASS/1anyio warning；治理111PASS，PG/TS及项目约束/文档/索引PASS，独立TS复审无新阻断。原库generation89已暂停，18calls/77375tokens/10464microUSD及日/累计限额均未变。完整目标仍需分页/有界补抓、事件发生/生效时间、真实评价审计、完整恢复重验、新镜像及当前MacCI/受管交付；不认证跨平台产品或旧CI为新代码PASS。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"在现有source.configure/controller/PG审计内添加固定目录的明确激活；DataHub来源归属、同一Hot worker和唯一队列保持，旧资料/研究快照不复制或删除，无新服务/依赖。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"现有CLI/typed Host传递显式flag及reason，controller仅增加sources.config列权限，旧SDK/Native/Docker进程及凭据归属保持，无新部署节点或模型权限。","diagrams":[]} -->
