# Hot 外部 TLS 身份核验修复

macOS功能开发，第二轮候选b29778ca之后的隔离feature修复。原数据库、stage五卷、dev/g2b和模型scope不变，新增付费请求0，上限20calls/100000tokens/USD1不增加。

真实复现：新隔离PG17使用原固定image3645570c、384MiB/1CPU/128PIDs、独立标记卷和回环58272。仅DNS localhost的证书链可信时，旧poolOptions配置host127.0.0.1仍建立TLS1.3连接；hostname_rejection_not_proven保存在before-fix-tls-receipt.json。postgres.js对IP不设servername，socket-based Node TLS发生localhost回退，rejectUnauthorized只凭默认目标不能证明配置IP身份。

修复保留rejectUnauthorized=true，并以Node标准checkServerIdentity显式核对config.host。新增近处回归先RED（缺绑定函数），修后测试验证DNS匹配、IP SAN匹配和配置IP与DNS证书不匹配。真实TLS复验：可信localhost连接TLS1.3/TLS_AES_256_GCM_SHA384；错误IP ERR_TLS_CERT_ALTNAME_INVALID；明文28000；无信任CA UNABLE_TO_VERIFY_LEAF_SIGNATURE。schema20受限worker健康ready。无关闭验证、系统CA修改或全局依赖安装。

本地62项Hot单元通过；首轮类型检查发现隐式any，明确使用string/PeerCertificate后类型检查PASS。正常startService在可信TLS上启动真实worker，签名RPC status返回running/schema20，池连接TLS1.3；close后该隔离实例paused=true，证据service-receipt.json。独立TS限定审查批准，配置5项单测及类型复核通过。测试CA/密钥与测试角色凭据仅私有logs/tls-proof/private，未进入源码、PR或报告。fixture容器已停止、独立卷/证书保留；旧数据库不受影响。这是外部TLS代码路径真实证据，不认证未指定的远端用户数据库。

证据位于旧prepared候选logs/tls-proof/{receipt,before-fix-tls-receipt,after-fix-tls-receipt,fixed-receipt}.json及接续worktree logs/hot-resume/tls-hostname-{red,green,all-unit,types}.log。修复后的commit/CI/新镜像须重新绑定，不能复用旧候选b29778ca的PASS认证新代码。困难关系真实模型仍未完成，整体Goal INCOMPLETE。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"沿唯一poolOptions补齐配置主机的TLS身份校验，保留存储/队列/接口与凭据归属，无新配置字段或依赖。","diagrams":[]} -->
