# 资产v5业务索引预检修复

宿主macOS Mac mini，Web部署工具修复。任务 `asset-v5-index-fix-20261022`，基线PR186合并240bbac。实际apply-assets-v5停机前拒绝 `resident_record_invalid`：verify_primary误用1 MB元数据读取器读取业务index。服务仍为51f09，无journal、无业务索引裁剪。原失败日志保留于Git common delivery evidence与用户home logs/model-upgrade.log。

仅将v5加入已有64 MiB业务读取绑定，保留普通文件、非符号链接、大小、JSON对象校验及全部保全/恢复门；旧profile不变。新增真实故障回归在修复前1失败2通过，另保留五种旧读取绑定回归。初次测试误载legacy根conftest缺SQLAlchemy，随后采用现有CI的confcutdir，不安装依赖。完整本地回归、Router、独立评审、原三CI与Mac干净安装及实际部署待最终证据分别绑定。Windows/Linux原生未执行，不冒充通过。

没有新服务、HTTP、数据流、持久格式、依赖或权限；controller/evidence字节及固定PREVIOUS/PAYLOAD不变，图文拓扑保持准确。常驻切换继续遵循既有授权、空闲与全账号保全检查。
