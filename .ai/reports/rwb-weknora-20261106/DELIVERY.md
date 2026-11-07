# WeKnora 资料与报告证据候选：交付映射

Host: macOS / Mac mini；任务类型：feature-development。Python产品测试检查点：e06c884fbe38d15a6c03f5a4421013b794992172；合流Node检查点：8563c2dc619aadcef91508cee23daa037f165fe4。最终交付身份以受管回执及同候选CI为准。

| 源变更 | 验证与文档 | 实际状态 |
| --- | --- | --- |
| knowledge_backend 用户JWT/当前空间/检索读取 | client/service/api/integrity；research-web-weknora.md | 合成HTTP、双账号、撤权、过期、越界、原件/分块篡改回归通过；真实服务NOT_RUN |
| 独立证据写入与保全 | immutable SHA记录、binding16KiB门、resident SH lease、preservation | 测试通过，冻结不是现有四项只读MCP权限 |
| stdlib origin传递与冷Doctor | server/knowledge_configuration、multiuser CLI、安装与安全合同 | 原冷Doctor3例先FAIL，最窄共享helper修复后原批次PASS；原失败proof保留 |
| 设置数据页知识库卡片 | Node组合25、隔离浏览器1440/390视口 | PASS；绑定/清空JWT/错误脱敏/显式列库；不是完整WeKnora界面验收 |
| 固定上游0001/0002/0003 | exact pre/post SHA、Python artifact tests、上游Node8、独立Go/TS评审 | 静态及artifact检查通过；原生Go编译完成但CPU依赖初始化崩溃，Docker编译容量中断；Go业务运行未验 |
| 只读容量/盘点/20题对照工具 | candidate 15测试、合同输入和owner/hash检查 | 合成检查通过；真实金标/语料对照NOT_RUN |

## 本地结果与身份

- 完整changed-set Router为L4/full-delivery；保留Windows/Linux交接，未从Mac发送他平台dispatch。
- Router Python四模块753项：752 PASS、1原有Windows-native SKIP。
- WeKnora九模块及原multiuser_cli定点133项：133 PASS。
- 必需Node十一文件组合：325 PASS，Node24.22.1，显式RWB_TEST_PYTHON共享健康环境，30.378秒；先前错误环境超时回执保留。
- 设置卡片相关组合25 PASS；上游编辑器纯Node8 PASS。
- 合流候选8563的必需Node与设置卡片组合350/350 PASS，34.026秒；不把此前325与25的独立运行简单拼接为本次回执。
- Git安全四套完整回归338/338 PASS，495.262秒；修复前RED、首轮600秒超时及取消证据保留。原测试回执没有exact-SHA声明，另核对feature ddb1d5ac与合流8563的脚本及四个测试模块blob一致。
- 正式prepared amend已通过恢复备份核验并收养8563；该事实不是发布、CI、业务接受或清理完成。随后结构检查发现Python生成索引过期，按合流源码重新生成；原FAIL保留，修后检查独立记录。
- Black/isort/Ruff、相关mypy、项目约束、架构/文档/进展检查实际通过。
- 以上本地Python均按WIP记录其真实候选、blob映射、用例集合及过程SHA，不改称最终候选执行；最终Mac CI与远端交付仍需独立证据。
- 本地结果摘要见两工作树logs/weknora-local-delivery-summary.json；有界旧资料引用审计见integration的logs/weknora-legacy-inventory-audit.json。后者仅观察当前原件哈希，未找到既有内容哈希可比，归属和空间未映射，不能作为自动迁移清单。

## 待验与权限边界

- Go运行、Vue类型/完整前端构建、WeKnora实际实例、原生宿主、20题真实周报对照、完整Word/Excel及正式部署分开待验，详见BLOCKED.md。
- Node固定锁依赖安装已请求授权，尚无回复；不得将等待或预选项当同意。
- 未读取实际供应商/模型秘密、未调用真实模型、未迁移原件、未改变生产服务、未停旧链、未开启日程。
- 原报告窗口Wind日历导出未知，材料与明确交接未取得；本任务不重复生产其周报。

## 回退与资源

显式撤下RESEARCH_WEKNORA_ORIGIN可停用新出口，既有会话/模板/金融快照/报告和冻结证据继续保留；不得删除未知绑定或密钥。
成功pytest根已走原受管入口即时退休，失败/取消原回执及重试绑定保留。SDK临时容器及本任务新建digest引用已退役；仍被系统Virtualization VM打开的可再生模块保留，不停VM、不伪称cleaned。最终日志去向和容量由logs/evidence-retention.json补齐，不归档依赖缓存。
