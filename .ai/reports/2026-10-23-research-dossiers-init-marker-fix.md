# 根级初始化保护标记

基于Core fbb248247继续修复整目录外移后重启丢失pin保护的HIGH。仅修改storage、对应测试、模块文档和本回执；未合Root、改扫描/API/UI、联网、安装依赖或操作常驻账户。

先用真实create＋bind的独立临时账户复现：dossiers整个目录外移后重建Store，list与retained_by返回空且assert_deletable错误通过。新回归修复前2项失败，日志 `/tmp/rwb-dossier-marker-red.log`。

新增root/.dossiers-initialized，在首次显式初始化的保全锁内O_EXCL写入0600、文件与根fsync，再创建目录／SQLite。属性marker、marker_size=123、marker_sha256零I/O提供给Root保全。canonical UTF-8 JSON精确绑定format与账户owner_binding，严格检查文件类型、链接数、uid、私有权限、大小、SHA256、路径inode；GET不补写标记。

已标记但整个目录、数据库缺失或为空一律503，不重建或跳过保全；初始化失败保护态保留。显式恢复在来源备份hash／owner／pin／raw全通过后可重建缺失目标，marker保持或受控补齐，恢复后旧pin继续拦purge。

已实际使用现有批准venv、隔离Store及内存keyring、MCP关闭跑原Core单测：**28 passed，3.06s**，日志 `/tmp/rwb-dossier-marker-green.log`。其后增加foreign-owner-binding拒绝回归，最终Core＋Store为 **42 passed，2.06s**，日志 `/tmp/rwb-dossier-marker-final.log`。定点Black、isort、Ruff及git diff --check通过。不宣称组合CI、正式恢复或部署通过。
