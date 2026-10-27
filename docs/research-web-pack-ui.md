# 九个研究组合包的前端消费

本轮为 macOS Mac mini 上的 Web 功能实现，复用现有资产／资讯入口、研究场景抽屉、能力中心、原会话 Send、文件和资产档案。唯一执行引擎仍为 DSH。九包 UI 可操作不表示 62 Skill／78 Tool 或整批 Seek 对齐完成。

## 入口与研究输入

资产页“研究场景”、原研究草稿“选择研究场景”和能力详情“配置此组合包并查看方法”读取当前账号 `/scenarios`。九包为持仓排雷、预期差、短线情绪、调研前置、事件复盘、海内外舆情、估值体检、筹码结构、财报季前瞻；原八场景与基金旧交接保持。

Host `pack_catalog.ui_methods` 是从固定方法合同派生的只读表单投影。方法、版本、必要资料类型、参数类型及限额一起展示。研究证券范围由用户明确填写代码／市场／资产类别／币种，不从证券简称猜测；日期窗口、交易日数、最少样本数、原件行 ID、复权口径、报告期采用类型化控件，不提供任意 JSON 或 records 输入。

研究日 `as_of` 保持原自然日合同。`research_scope.cutoff_at` 必须由用户明确填写带时区的完整时间，换算到上海后须属于同一自然日。界面不默认午夜或日终。研究范围参数不授予来源、owner、rights、qualified、passed、provider、披露时刻或覆盖权限；风险关联方法的 category_coverage 仍是来源核验缺口，不能在表单中手填。

数据快照模式的材料来自当前会话／观察已经返回的本人快照及既有带原件引用的资料合同。勾选结果形成 `material_ids` 与原 `dataset_ids`；浏览、筛选、勾选不会发起供应商查询、MCP probe、模型或收费调用。

能力中心或独立研究上下文可明确选择本人已有材料的原会话，再读取原 `detail.datasets` 并逐项勾选；选择会话不自动全选材料。来源读取失败、切换或迟到结果不会保留上一会话资料。已有资产观察／原件资料合同锁定的上下文不开放这一切换，避免把另一证券材料默带到当前对象。

## 预览、草稿与原发送

1. 明确材料与参数后点击“只读资格预览”，POST `/scenarios/{id}/prepare`。
2. 展示真实 `pack_qualification` 的 partial／blocked、可执行方法、逐类型／逐来源缺口、原件 hash、时点、转换与冻结能力版本。
3. 无可执行方法或 blocked 时不开放“明确准备研究草稿”。受审映射包括 BaoStock 不复权日线子集和两包的已保存原文版本；不把其他资料“已取得”写成“已接好”。
4. 明确准备仍走原 `/handoffs` 幂等合同，Host 重读原件并重新验证。准备成功后用户确认进入原研究草稿；只有原 Send 才启动离线夹具或真实运行。

编辑证券、日期、材料、方法参数或场景使旧预览失效，保留其他输入。预览迟到响应受账号、打开代数与输入版本约束。能力／许可／原件在服务端变化时，准备和发送仍由原 Host 门拒绝；浏览器不替代持续授权校验。

未知创建结果持有完整原 request_key/body，关闭、重开、刷新均只能查询原请求。普通 404、网络错误和错误码不能解锁重发；只有服务端锁内证明 `not_created` 才恢复编辑，并要求重新预览。Enter 在输入框不隐式创建；IME 确认保持输入法行为，Escape／Tab 沿原抽屉键盘合同。

## 已保存原文模式（C6b）

调研前置与海内外舆情在原抽屉提供明确的“数据快照／已保存原文”选择。两模式保留各自勾选和当前问题、主体、截止与方法参数，但请求只发送当前模式资料；切换使资格预览失效。原文 ID 不进入 dataset_ids，正文不复制成上传文件。资产观察与既有 workspace_material 锁定上下文继续原合同，独立组合包入口可配置原文材料。

原文模式读取当前账号会话目录，再通过 `GET /source-selections/sessions/{sid}` 读取安全 metadata。可跨本人会话勾选1–20份；键为 SID＋source ID，同 URL／hash 在不同会话保持独立。第一份所选来源的会话是原交接 anchor，必须已具备 datahub／uploads／web 三项范围；缺少时前端拒绝预览请求，绝不隐式开启权限。

列表仅显示标题、来源会话、host、hash、取得时刻、日级发表日期和捕获状态。取得时刻未知、精确发表时刻未知、上游完整性未知与语言／地域／原创角色／历史 PIT 未核验分别说明；Host 捕获完整性不等于上游完整性或研究质量。列表不显示正文、路径、下载 URL 或私有 proof。空会话、权限撤回、缺失、410删除、完整性变化和一般来源失败分开呈现；跨会话旧选择和其他研究输入保留，消失的已选原文显示不可用并允许明确取消。

“只读资格预览”调用 `/source-selections/preview`，以真实 `qualification` 展示可执行方法、缺口、input／closure hash与当前1.1.0方法版本；没有文件或Native创建、模型、供应商或网页抓取。“明确准备研究草稿”调用 `/source-selections/freeze`，绑定原请求、preview_sha256及唯一 Idempotency-Key，再由后端进入原 create_handoff。文件发布不等于已准备；成功 prepared 才开放原草稿导航，原 Send 保持独立。

403／409等错误只有携带后端锁内 `handoff_outcome=not_created` 证明才恢复编辑并清除旧预览，保留来源选择与其他输入。真正 Native 创建未知、文件发布未知、丢失响应或无证明错误保留完整原 key/body，刷新后仍只查原 `/handoff-requests/{key}`，不自动重发、换key或显示已冻结。

新验收入口为 `tests/javascript/research_web_source_picker.test.mjs` 与 `tests/e2e/research_web_source_picker_real_backend.mjs`；后者通过明确合成账号、真实Host、stdlib HTTPResponse同进程捕获和自有Chrome验证两宽度、深浅主题、三主体、跨会话、预览零创建、403／409／410、真正server unknown和丢响应lookup及原Send。所有材料为冻结fixture，不操作用户Chrome或真实账号；真实模型、生产服务、全62／78项、CI和跨平台继续独立验收。

## 计算回执、文件与质量

`scenario_pack_ui.project` 在 `service.detail` 已完成当前账号和祖先来源校验后投影，旧八场景不增加该字段。只消费当前私有 receipt 中与 task／call／context／input 绑定的 pack_executions。saved 必须再次通过 B1 `read_artifacts` 的完整 schema、输入、计数、hash 与文件读回校验；公开下载引用还必须匹配原文件索引。前端不按文件名、stdout、卡片、runtime_verified 或模型声明判定成功。

公开 `research_pack` 仅包含资格状态、执行状态、计算状态、计数、原 receipt 的 preview／omitted 统计、缺口代码与已登记文件 ID／URL／hash／大小；不公开 launcher、命令、环境、控制路径、binding 或正文。未知执行不开放成功文件；产物变化显示 invalid；来源撤权沿原 detail／文件读取门拒绝。

结果界面分别显示会话状态、完整文件保存、计算 partial／complete 与原研究质量 passed／incomplete／invalid。128 仅为行预览上限，实际全量／遗漏由原回执显示，full-result 不冒充原始来源。事件收益、基金穿透与财报监控继续保留原 blocked 门。

“查看原会话文件”“质量回看”沿原面板。资产档案入口携带可核对的来源会话 ID 供原“关联已有研究成果”流程使用；先预览再确认，保留原质量状态，不直接修改 thesis／quality。

## 视觉与状态边界

扩展现有抽屉而非新应用或新主导航。沿用现有主题 token、紧凑字段组、原按钮层级与自然滚动。设计取向：低装饰、低色彩复杂度、高信息密度、原导航、高可核对性。窄屏保持一列抽屉与两列证券属性，无横向溢出；Light／Dark／System 继承原主题。

状态覆盖包含 loading、empty、error、stale、blocked、partial、unknown、not_created、invalid、当前账号变化和旧输入保留。生产登录、真实模型与供应商来源、常驻部署、Mac 安装 CI 及其他平台证据各自验收。

场景抽屉由现 App 重绘时，同一场景保留独立滚动位置；正在编辑且未禁用的数字输入节点保留，避免数字框无法通过 selectionStart 恢复的光标倒序。文本继续使用原焦点／selection 恢复，切换场景或关闭重开从顶部开始。逐键浏览器回归 `tests/e2e/research_web_packs_scroll_real_backend.mjs` 使用真实临时 Host 与390px页面，断言每键的可见位置、scrollTop、焦点、数字中间插入、文本 selection、长文本、Tab、场景切换与关闭重开；不以一次 fill 替代输入旅程。

验证入口：`tests/javascript/research_web_packs_ui.test.mjs`、`tests/research_web/test_pack_ui_projection.py`、`tests/e2e/research_web_packs_real_backend.mjs`。后者使用全新临时账号、真实 Host 与合成快照，拒绝非 loopback 网络；真实模型 NOT_RUN，截图始终标识合成验收材料。
