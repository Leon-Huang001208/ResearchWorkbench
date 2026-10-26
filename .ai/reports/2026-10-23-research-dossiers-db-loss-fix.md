# 档案库缺失／零字节保全修复

macOS Web保全边界最小修复，基于Core `5fed393ab`。只修改storage、对应单测、模块文档与本回执；未合并Root新接口、未联网、未处理凭据／服务、未安装依赖。

只读代码核对及独立临时账户探针先复现：真实create＋bind后把metadata.sqlite3截成0，原list变空且retained_by从含档案ID变为空。新增回归修复前为 **3 failed**，日志 `/tmp/rwb-dossier-db-loss-red.log`。

修复：既有目录下数据库缺失或为空时，统一稳定503 `dossier_storage_uninitialized`，普通读取、写入、备份与purge不再推断为新库。首次目录创建的当前初始化事务可提交schema，但首次事务失败留下空库不会自动重建。显式restore仅在原备份hash、owner、完整性、pin和raw验证后允许替换损坏目标。

回归涵盖外删／截0后list、retained_by、create、patch、purge、backup全部拒绝，原件不动，随后显式恢复原备份并证明旧pin仍阻止purge。首次正常惰性创建和已初始化事务回滚保持。

实际运行现有批准venv、隔离Store及内存keyring、MCP关闭：`python -m pytest tests/research_web/test_dossiers.py --confcutdir=tests/research_web -q`，**20 passed，1.98s**；日志 `/tmp/rwb-dossier-db-loss-green.log`。Store近处回归 **13 passed，0.23s**，日志 `/tmp/rwb-dossier-db-loss-store.log`。定点Black、isort、Ruff与git diff --check通过。未宣称组合CI、真机部署或正式恢复已执行。
