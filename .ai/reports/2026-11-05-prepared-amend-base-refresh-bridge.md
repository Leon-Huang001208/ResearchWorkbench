# 未发布prepared amendment与正式base refresh组合修复

宿主macOS；仅仓库交付薄入口，不是产品部署或平台适配。未修改真实ledger、全局安装、生产Python/profile或运行服务。

实证：正式回执先以prepared-amend将a1fa48→7881收养（base604），之后正式base-refresh推进191259（base546）并原样保留旧history。下一原--amend-prepared在旧epoch比较当前base/末端处报PREPARED_AMEND_HISTORY_INVALID。旧epoch snapshot/proof/hash/manifest均一致，正式base-refresh旧快照恰好封闭旧history；不是丢失证据或应重建task。

最小修复在scripts/git_safety.mjs：每epoch仍检查自身snapshot/proof/base、raw merge chain、anchors与sealed backup；仅末端base断点时查同task唯一私有base-refresh快照，并严格验证允许字段投影及所有raw祖先/feature包含边。快照目录集合与文件原inode/bytes并入后续revalidation/CAS，不加schema字段，不清历史；原restore、新备份与unpublished-null/远端不可见性/锁硬门保持。

真实相邻组合RED：1测试1失败、PREPARED_AMEND_HISTORY_INVALID，logs/prepared-refresh-amend-red.*。同用例修复后GREEN1/1（包括新epoch与同候选replay），logs/prepared-refresh-amend-green.*。负例及完整两Node文件回归待真实结果补充；未执行正式amend或部署。
