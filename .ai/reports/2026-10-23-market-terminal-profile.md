# 市场终端 Native 部署 profile：文档与本地闭包

宿主Mac mini（macOS），任务为Web功能／Native部署工具闭包；不承担Windows/Linux原生适配。
本轮只补文档和执行既有测试，不修改profile常量、API、前端、依赖或常驻实例，不提交或发布。

## 固定候选与边界

工具检查基线为`d0769dd46309ae2c5abf90959d0b6cdb366b2692`。
`reviewed-market-terminal-v1`／`apply-market-terminal`当前固定PREVIOUS为
`0e0022ac792eba88fba0f233524f5c8d66024569`，暂存产品检查点为
`717d564d2e7016a4ec464435b9ba96900dbf3bcd`。
后者不是最终部署资格；PR201合入后由主任务固定实际产品PAYLOAD，重新绑定最新组合候选。
原version4维护锁、BirthFence、严格索引／元数据边界、全账号保全和恢复、旧profile、controller、
evidence及web.lock身份沿当前代码保持。没有安装包、访问秘密、启用数据库、运行apply或更新生产服务。

## 文档核对

已阅读部署模块、现有模块合同及architecture-map中的dual-runtime清单，补齐全部7份必要文档：
安装、Docker、01部署、02研究与恢复、03文件、05安全验证、平台支持；
同时补齐ARCHITECTURE、DEVELOPMENT_MAP、AGENT_WORKFLOW及gateway-upgrade模块文档。
仅新增封闭部署身份，不新增运行节点或数据通道，原01／12图仍准确；产品13图沿主任务已有更新。
没有修改主任务并发更新的指数目录／官方来源说明。
架构门发现同一操作员还属于private-multiuser，因此同时补齐AI资讯、04API和ETF周报的保全／不扩权说明。

## 实际本地命令及结果

只读复用已有批准的`ai-news-live-deploy-20261019/.venv/bin/python`，未安装依赖。
后端使用`python -m pytest --confcutdir=tests/research_web`运行
`test_market_terminal.py`、`test_market_service.py`、`test_market_reader.py`：
**130 passed，1条既有anyio弃用警告，3.15秒**。
日志：`logs/market-terminal-20261023/backend-profile-closure.log`。

操作员完整清单为`test_model_provider_upgrade.py`、`test_gateway_upgrade.py`、
`test_resident.py`、`test_multiuser_resident.py`，未按profile筛减。
首轮**1312 passed／19 failed，81.69秒**，保留原始失败日志
`logs/market-terminal-20261023/operator-profile-closure.log`。
19项冻结恢复子进程误加载donor venv已安装app包，在其runtime_contract路径核验失败，
trace明确指向donor site-packages；没有改测试或放松路径检查。
随后仅以`PYTHONPATH="$PWD"`为子进程显式指定当前候选源码，重跑同一完整清单：
**1331 passed，1条既有anyio弃用警告，92.80秒**。
日志为`logs/market-terminal-20261023/operator-profile-closure-source-root.log`。

定点架构文档门按操作员映射检查dual-runtime和private-multiuser组，最终`violations=[]`；
日志`logs/market-terminal-20261023/profile-architecture-final.log`。这只证明已补齐文档与结构复核，
不取代主任务最终完整changed-set Router或CI资格。

## 未验证项

最终PAYLOAD冻结、完整changed-set Router、独立评审、最终组合Project Constraints／Research Web Checks／
同候选macos-14干净安装、实际apply、双入口健康、真实认证页面及全账号保全／恢复均由主任务继续，
不得从本地测试或旧产品／工具CI移记为通过。本轮Docker产品和Windows/Linux原生保持各自未执行状态。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅在原Mac Native version4受管事务增加封闭terminal部署身份，复用原主实例/网关、维护锁、BirthFence、索引保全与恢复；没有新增运行节点、Docker边界或研究引擎，01/12图准确，产品13图已有终端数据边界。","diagrams":[]} -->

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"terminal仅增加同一Native操作员封闭身份，复用原私有网关认证、租户根、维护锁、全账号保全与恢复；资讯/周报接口、预算、日程及秘密namespace均不扩权，没有新部署或跨账号数据通道。","diagrams":[]} -->
