# AI资讯自主原引擎与零调用评测准备

宿主macOS；任务类型功能开发。验收范围为Mac本地与适用macOS CI，Windows/Linux产品验收NOT_RUN。

固定原版AIHOT 26d436497d9ddba9e7dd88eed255cfe0105ce368，保留652原文件、MIT许可、源哈希与最小适配补丁。RWB原阅读和管理走本机引擎，阻断原网站接口/图片/历史后备。隔离PG17新库60份迁移，预算持久回执与原双评分/事件/报刊流水线保留；本阶段不调用模型或付费源、不更新常驻。

用户已单独授权任务npm依赖、声明的Python测试工具、隔离PG17容器卷及新*_test数据库迁移。真实模型、生产切换及Hot重叠信源交接尚未执行。

已观察：Node适配8项与原后端71项通过；完整upstream standalone因未构建独立SSR产物失败，保留日志。焦点Python197项通过，管理及阅读JS31项通过（后续新增回归待复核）。原文50篇含10中文、20关系候选，参考标注均needs_review，所有模型结果NOT_RUN/null。详细证据在logs/与services/ai_news/logs/；最终候选CI/最终汇总尚待完成，不用早期结果冒充交付通过。

<!-- architecture-review {"group": "dual-runtime", "structure": "changed", "reason": "新增本机原版资讯采编引擎、私有Host桥和独立数据库，部署关系由新图12记录；研究引擎与现有平台归属保留。", "diagrams": ["12-ai-news"]} -->

<!-- architecture-review {"group": "ui", "structure": "changed", "reason": "新增本机原版资讯采编引擎、私有Host桥和独立数据库，部署关系由新图12记录；研究引擎与现有平台归属保留。", "diagrams": ["12-ai-news"]} -->

<!-- architecture-review {"group": "research-api", "structure": "changed", "reason": "新增本机原版资讯采编引擎、私有Host桥和独立数据库，部署关系由新图12记录；研究引擎与现有平台归属保留。", "diagrams": ["12-ai-news"]} -->

<!-- architecture-review {"group": "documentation", "structure": "unchanged", "reason": "本轮补充自主资讯边界与接口索引，保持该模块既有执行、授权、存储和恢复拓扑，不改变其运行归属。", "diagrams": []} -->

<!-- architecture-review {"group": "verification-workflow", "structure": "unchanged", "reason": "本轮补充自主资讯边界与接口索引，保持该模块既有执行、授权、存储和恢复拓扑，不改变其运行归属。", "diagrams": []} -->

<!-- architecture-review {"group": "ai-news", "structure": "changed", "reason": "新增本机原版资讯采编引擎、私有Host桥和独立数据库，部署关系由新图12记录；研究引擎与现有平台归属保留。", "diagrams": ["12-ai-news"]} -->


独立评审反例已修复：初始化中断续跑、进程指纹稳定性、Popen失败清理、migrate/seed超时整组终止与不确定恢复栅栏；标注重复覆盖、混合split请求与云端传输仍在最后评审；管理草稿/连续保存/迟到响应/重复创建反馈与历史显示。新增自主chronicle经原Module扩展重新检查当前主题归属、撤回与修订，明确三种日期及80条证据范围。

真实本地：Host与阅读联合回归82项、阅读44测试、安装目标回归已过；原API新库60迁移/seed幂等/密码sessionCSRF/预算拒绝/六RSS/备份原子恢复已过；9适配、71原后端、82原PG不变量、7原成刊测试分别通过。89项原PG测试使用pristine vendor和回环fake providers，RWB补丁另有不授权0dispatch与unknown不重发证据，不混称完整补丁版PG验收。

当前resident兼容清单对本轮完整changed set返回false，确认合并源码不会获得自动常驻更新资格；没有修改静态兼容清单。

最终源码前本地复核：完整JavaScript838/838，零skip；Host/阅读/安装204项通过，通用平台/协议与生命周期1056项通过（1个条件skip，7个subtest）。Ruff/Black/isort全20个变更Python文件通过，mypy8源文件通过，架构/文档/索引/完整changed-set Constraints通过。原版引擎RSS真实免费试抓OpenAI返回1298候选、20项预览、未入库，实际模型与付费请求为0。补丁+阅读/管理46项通过，最后源码checkpoint后仍需集成验证和macOS CI。

评测39项离线测试及7个真实冻结输入/原prompt dry-run通过，均PREPARED_NOT_SENT；参考集50原件、51条逐字事实提案、20关系（3同次发生/3同故事/14无关），40/10事件组隔离。参考仍待人工复核，所有模型质量NOT_RUN。独立评审修复跨split请求与DNS重绑定（数值地址固定，原hostname TLS认证）。

最终单次焦点回归实际122 tests、7 subtests PASS，JUnit分类：Host39、评测39、阅读44；没有将重叠测试运行次数累加为不同测试数量。此前worker所称82为Host/阅读联合运行，非82个独立Host测试。最终对应日志 ai-news-final-focused.log 与JUnit。

源码检查点：`c38582fd827b36bc20a321eb4e4777143c7825f8`。图源12已9/9 showcase、零错误与警告，四视口包含检查通过，实际查看1440浅色与2048深色截图。源码链接绑定此检查点，最终生成物交付提交另记。

交付前公开CLI复核补充：已用反例先红证明setup早期分派误留宿主Python，会依赖全局keyring；改为复用既有Native环境归属校验与受控reexec，并覆盖无效环境拒绝、Native内部不递归、doctor无需venv/凭据。新增4项public CLI回归通过；测试使用stdlib输出捕获，尊重pytest.ini既有no:capture设置。首次集成候选7bcf8d2本地848JS、1281Python/7subtests通过（Windows-only一项保留skip），其后源码修补需对最终候选重新验收。

最终公开CLI修复后的源码检查点 `4b1fc631df582c9d20f00eca2f31f68888396f79`；Host43项全通过，含4个公开CLI环境分支；拒绝测试遵循原bootstrap的issues数组合同，不改变产品响应。图册源码链接更新到此检查点。
