# WeKnora DataHub 业务工具实现

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"沿原 DataHub/Broker/Provider/MarketStore 增加固定岗底斯行情 binding 与规划纯函数，不增加服务、数据库、调度器或执行节点。","diagrams":[]} -->
<!-- architecture-review {"group":"inbound-mcp-readonly","structure":"unchanged","reason":"沿原 OAuth、账号 Host、查询提交/status/分页和快照链注册业务工具，原 scope 与物理拓扑不变；未部署。","diagrams":[]} -->

宿主：macOS arm64，功能开发；本平台范围为本地 Python/原 MCP 与 DataHub 合同、
现有 CI 和 macOS 安装。Windows/Linux 产品未验，不作为本轮 Mac 开发前置。
任务：weknora-datahub-complete-20261125；基线 9c3d8085。

## 结果与范围

- B1 修正交易日合并：周五/周一连续缺失不拆请求，已覆盖交易日仍是边界。
- WarehouseBridge 复用该函数，保留原来源/授权上下文；Wind 缺口按60自然日切段。
- 原 manifest.provider_metadata 写有界计划摘要；不冒充未实现的覆盖/证明计数。
- 注册 9 个业务工具，无 rwb_ 前缀；复用原提交/状态/分页，不另建取数任务。
  K 线固定规范 CNY/股原始日线语义；source/capability 由服务端决定。
- 岗底斯正式 ext_finance_mcp/market_bars/gangtise_raw_daily 绑定、归一化和仓库来源准入。
  原外部 envelope 路径及默认来源顺序不变；不接受复权/PIT/backtest。
- 明确财务字段字典：已核 CNY 字段与未知比率尺度分开；不把原生比率当完整现金流量表。
- 新闻/公告/MySQL 三个候选工具按条件不注册。注册9个不代表12个全交付。
- 代码与真实 WeKnora 目录刷新/常驻部署分别记录；未修改生产配置、权限或服务。

## 实际验证

- 新规划 29 个、任务参数 11 个、金融行情投影7个、既有仓库6个 unittest 通过。
  后续新增 Wind 分段用例，最终候选需复验；不将初轮结果称为最终 exact-SHA 验收。
- 原 MCP HTTP/OAuth → 账号 Host → DataHub → Finance MCP 模拟协议 → 冻结快照/status
  的完整集成通过；幂等同键同参只有一次工具调用。
- contracts3：12 个逐项登记的集成/权限/仓库/来源用例通过，临时根已正式回收。
- 真实岗底斯 600519.SH、2026-11-10～13：原始4行；与 BaoStock OHLC/成交量一致，
  成交额差异≤1元。total=4 与4行一致；归一化入口另一次真实查询 complete。
  单位是有限跨源样本核验，不是厂商完整字典或稳定性/复权/PIT认证。
- ruff 检查通过；最终格式、文档与候选检查在交付时追加。

## 实际失败与处理

- 早期新用例发现 ProviderError 未转换成安全输入错误，已修正并通过参数用例。
- 首轮集成夹具漏处理 MCP tools/list，补齐真实协议夹具后通过，未改变产品判断来放行。
- 测试批次 contracts2 pytest 实际 exit0/8 passed，但登记类名导致节点数与JUnit数不一致，
  回收合同失败。如实保持实际exit0和原结果，按正式retire函数恢复为批次失败并回收根；
  未将该回执改成PASS。contracts3 用12个精确用例重新通过并回收。
- finance_list_tools 缺 service 的一次发现请求失败；后续通过 tools/list 查明契约，
  不将该失败归因于供应商行情不可用。

## 未执行与边界

尚未发布/合并/部署；真实WeKnora本轮未刷新目录。9个工具是源码注册，
真实行情验证为独立适配入口，不冒充生产MCP调用成功。
未解释 adjustFactor，未开放 qfq/hfq、自定义基准日、PIT或回测。
后复权/因子统一视图、公告/新闻正式绑定与MySQL工具不在本批已交付功能内。

Product-Progress: not-required — 本批交付后端MCP技术接口与契约；未更新常驻产品和Web用户界面。

## 最后本地检查

- 完整入站 MCP 验证闭包与新增/仓库模块：236 个 Python 用例通过；正式 CI 分区 runner
  保留两份 JUnit/result/计划，验证 owner/inode、进程已退出、无打开文件后回收408MiB夹具。
  部分 fixture 目录只读，恢复本任务目录用户写权限后完成回收；未触碰运行服务。
- L4 JavaScript 架构、文档治理、Actions 和跨平台仓库合同：211 个通过。
- 最后补充当日K线边界：业务工具仅接受截至昨日的历史日线，避免把盘中日K当作完成日K；
  当日应走快照。该变更后12个业务参数用例通过，原236结果不冒充此后全量重跑。
- README入口及复核回执同步；无新依赖，requirements/web.in、web.lock、setup_web.py
  无需改动，干净安装兼容性仍须同候选macos-15 Bootstrap证明。
- Windows/Linux 原生产品验收为 NOT_RUN；通用仓库门与macOS候选CI分别记录。
