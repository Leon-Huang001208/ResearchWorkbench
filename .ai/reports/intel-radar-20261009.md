# 资讯雷达原生只读整合 · 2026-10-09

宿主：macOS。任务：Web 功能开发与本地部署。分支：codex/intel-radar。
基线：f32d6993af99652c76e9a77dbc6f44877e39cd1c。

## 行为与边界

新增资讯雷达主导航和 8 个栏目。原生页面共用既有主题/按钮/导航；事件与报告侧栏阅读，窄屏单列。
固定 Golddata 公开 API 由 Host GET 适配；不转发 Authorization/Cookie、不跟随重定向、20 秒总超时、16 MiB 响应上限。
接口具备有界参数验证、安全错误码与项目日志。无远端 POST、采集、AI、账号写入或自选股迁移。
事件概率保留原在线产品规划中状态。原参考 GitHub 仓库返回 404，接口/在线 UI 为核验来源。

## 架构复核

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"新增同一原生UI壳内的只读资讯页面；浏览器仍通过同源Host获取数据，不新增前端服务或更改DSH研究执行流程。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"固定公开来源GET适配器属于既有Host外部数据读取职责；没有新增部署节点、持久存储、调度器或第二研究引擎。已同步API清单与权威文档。","diagrams":[]} -->

## 验证记录

- Python：`test_intel.py` 与 `test_api.py`，83 passed；新接口参数、边界、超时、HTTP错误、非JSON、响应上限及无凭据转发均验证。
- JavaScript：资讯雷达、研究台、UI与主题相关测试，62 passed；包含取消旧请求、缓存按需加载、筛选、列表分页、游标去重、文本转义和安全链接。
- 真实接口：预览读取全部已有数据栏目、事件原文证据、研报详情/下一页、600519 新闻和公告。
- 浏览器：真实接口 8 栏目、详情、筛选、研报分页、见闻游标、代码查询、模拟超时/重试通过；Chrome无页面JS错误。
- 主题/布局：桌面浅色/深色、390px移动截图复核；body/main均无横向溢出。
- 架构、文档治理、完整changed-set项目约束与Python生成索引检查通过；治理测试145项首轮通过，1项因PATH缺Node失败，补工作目录Node后单项通过。
- 本地8088更新与回归结果待追加。

## 安装与平台状态

未新增产品依赖；复核 requirements/web.in、web.lock、setup_web.py 与 bootstrap workflow 仍消费既有 FastAPI/httpx。
开发测试工具只安装在工作目录隔离 validation-tools 环境。
本次不执行 GitHub push/PR/CI；macOS干净安装CI与Windows/Linux验收为 NOT_RUN，不将本地验证宣称为跨平台发布就绪。
