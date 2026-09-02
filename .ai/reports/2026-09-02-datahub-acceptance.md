# DataHub真实验收记录

任务：task-75e24928-datahub。实现工作树codex/dsh-web-v1，基线708fbdb。实现与真实旅程完成；范围限本批轻量DataHub、基金资料共享和Web展示，不等于完整金融数据平台。

## 边界与预检

- 用户授权：仅代为允许本轮基金000001的净值、基本资料、分红、披露持仓四类公开只读审批。无账号/付费API，不外发附件或聊天。
- 新Provider真实解析对照见同目录`2026-09-02-datahub-source-probes.md`；不替代Web、原生审批、子Agent验收。
- 更新服务前预检：8088现有14会话，无运行中任务；专属DSH连接且credential_configured=true，模型deepseek-v4-flash。
- 当次端口PID：3081=22933、8088=22974；用户原3080=77454，不改动。更新前须再核对，不依据旧PID直接操作。
- 早期Python启动探针38291仍为UE，未自动重启系统或宣称已回收。

## 已执行的真实旅程

1. 新Web专用会话，父Agent逐项原生审批取得四来源并读取manifest；NAV确为13页243条，非单页20条冒充全年。
2. Web展示4张真实资料卡，来源、范围、缺失、hash与报告文件分离；实际点击净值CSV和最终XLSX下载，另对全部12个资料下载及三个最终文件HTTP返回做hash/重开校验。截图在本任务工具输出中，未声称生成独立截图文件。
3. Web升级Claw后新owner/new dataset ID，原始hash/取数时间保留，draft含新路径映射；两名真实原生子Agent共读资料，没有重复HTTP取数。
4. DOCX/HTML/XLSX/PNG已真实生成。最终三文件格式校验completed，XLSX底稿逐值、hash及主要计算独立验证。首次错误产物保留但不作为最终交付，详见下文。
5. 原生拒绝、等待审批时停止、重复提交、刷新恢复和跨会话拒绝真实验证；HTTP进行中取消、崩溃重放与覆盖不足由离线测试验证，没有混称真实服务故障注入。
6. 最终回归与整分支独立审查通过；Harness硬门结果由收尾命令另行记录。

## 已执行的上线预检与任务提交

- 后端ab007ff与审查修复364c0bc均通过独立规格/质量审查；实现者119Python/32JS回归记录见相关报告。
- 再次确认旧服务无活动会话后，仅TERM原专属8088/3081并用既定命令重启。新PID：3081=73729，8088=73899；原3080仍77454。
- 新服务runtime为connected/owned_runtime/credential_configured=true，model=deepseek-v4-flash。
- 实际API：capabilities列出5个固定来源；无认证internal query/cancel均403；旧Claw会话datasets为空而非模拟卡片。
- 从真实Web选择fund-evaluation Skill、无需文件，提交四来源准备任务；新FinGPT会话`118c9cc6-edc5-4c28-b03f-c3bd0102d514`。原生模型接受分阶段目标，没有提前开子Agent或生成报告。
- Web出现明确四种000001原生审批；主代理仅依据用户授权逐次允许。这不是取消其他来源的审批要求。

## 真实会话、资料与子Agent

- [FinGPT资料准备](http://127.0.0.1:8088/#/fingpt?session=118c9cc6-edc5-4c28-b03f-c3bd0102d514)：原生fund-evaluation，第一轮明确只取资料，无报告/子Agent。
- [Claw共享研究与最终文件](http://127.0.0.1:8088/#/claw?session=d918f34f-02bf-4c85-bc7a-a8b5880195b6)：实际UI升级，随后分工与修订。

| 来源 | 原FinGPT dataset_id | Claw复制 dataset_id | 实际资料 |
| --- | --- | --- | --- |
| fund_nav | 89c30f24-a052-4581-b0d4-c7a48ad13f72 | 7b5e6201-602b-49bd-8dc0-d9596e90e7d0 | 请求2025-01-01..12-31；实际01-02..12-31；243行/13页 |
| fund_profile | fc9ee103-1cd4-4199-9b21-1bfe0fa75814 | 46eafc41-b48b-4289-8d76-aaa97e17ce87 | 当前快照16项；规模截至2026-06-30，非2025时点 |
| fund_distributions | 36de9060-d4f7-4d2e-949b-5f1ba3664b79 | 8d8a9dd3-ecee-4b9a-8cbf-1c73a471effc | 25条，2025-09-22每10份0.1000元 |
| fund_holdings | b49be68e-4173-4290-ae46-90c5cc79745d | 74b3d6e3-2a1c-49b8-9cf6-71851199c2cb | 220条，四报告期10/100/10/100条，完整头寸未知 |

NAV的rows.json SHA256为`1a2486310858638f71666abfb7b9ec36ba6fa6b4d74a3d503e7f2fd9171840e6`；CSV为`2d50d66345d64169bc0947c1a69f501c99efab014daf5eaf2c6b9e97b89d7900`。
复制前后相同；Claw manifest为`bac70340e6b0ac9c61a84c8083c0d07715f79cee0cb17af89cf85bcaadcfe323`，保留原ID、原manifest hash与retrieved_at。

两名真实原生子Agent（非应用模拟编排）：

- 净值区间与回撤计算：`dc459e3d-3aed-4226-824e-cd71fa78aa27`，61.687秒、23372 tokens。
- 资料风险与缺失核对：`116b1592-c9c0-44be-9eab-85b082fd6530`，71.253秒、31788 tokens。

双方读取同一NAV新ID并校验hash，分别生成JSON/Markdown底稿，父任务汇总成报告。原生限制、模型与沙箱未放宽。

## 最终产物与独立核验

本批交付以`final`文件为准；原始v1、v2与子Agent草稿留在同一会话便于追查，不能当作同等质量已确认的文件。

- [Word](http://127.0.0.1:8088/api/research/sessions/d918f34f-02bf-4c85-bc7a-a8b5880195b6/files/652bbcce0b0721f36e58ec75/download)：fund_eval_000001_final.docx，40746 bytes，SHA256 `264b9afff820b85e25c4b16c2ce324fd26f6d79ed704f30a73e4555e98ff78d0`。
- [Excel底稿](http://127.0.0.1:8088/api/research/sessions/d918f34f-02bf-4c85-bc7a-a8b5880195b6/files/b1f757e822b4b6420ba59b7a/download)：fund_eval_000001_final.xlsx，30761 bytes，SHA256 `f06cb9c45442ab89e9489369958a5adc41118440b458f50447e5e35ad546c37e`。
- [HTML](http://127.0.0.1:8088/api/research/sessions/d918f34f-02bf-4c85-bc7a-a8b5880195b6/files/629e3e320fe2e4a2caa42821/download)：fund_eval_000001_final.html，8286 bytes，SHA256 `e1840cfbc08c6eeadd21cf3a6e3b68acb241a928d444e2cb9d4a44b4e07707fc`。
- 图表nav_drawdown.png：144113 bytes，1610×840；PIL verify通过，仍可从会话文件区下载。

独立校验使用现有Python、httpx、openpyxl、python-docx和PIL，不安装新包、不手工改写模型产物：

1. 三最终文件从下载API取得，HTTP成功、SHA256与delivery一致；Office实际重开，HTML正文读取。
2. Excel四原始表的全部单元格逐值对照CSV，空单元格按空串比较，记录数243/16/25/220完全一致；对应12个资料下载均验证hash在sources_hashes_v2表中。
3. Decimal从原始NAV独立重算：首末未复权净值变动`0.348692403486924034869240349`；逐点峰值回撤`-0.1247803163444639718804920914`。Excel B2/B3为数值，误差小于1e-14，number_format均为`0.00%`，全簿无无效公式单元格。
4. 2025-12-31前十持仓占净值合计逐行计算25.96%；DOCX/HTML关键数字、四dataset_id、时间口径和缺失项存在且对应同一资料。
5. Web实际打开HTML隔离预览；iframe sandbox为空权限集，界面声明脚本/表单/外部导航禁用。另有既有API/CSP及文件安全回归。
6. 完整页面重新加载后，4张资料卡、243条/13页、2名Agent及三final文件交付状态恢复，没有重提任务。

### 必须保留的质量事实

初版模型产物并非一次正确：曾将XLSX回撤百分比放大100倍、留未定义名称公式，子Agent草稿还误读每份分红与NAV分红字段；修订版曾在重新生成后丢失百分比显示格式。
主代理通过实际文件发现问题，在真实Web会话要求DSH重新读取原数据、修订并生成final，之后重新独立校验，未代替DSH手工生成文件。
报告仍是受限研究样例、存在文字修订痕迹；不能把结构检查completed当作所有文字与未来任务的语义正确性保证。未建设新Claim/Quality Gate。

## 异常与权限验收

专用会话`d1993215-db31-4eae-9594-2497dde125f3`：

- Web拒绝：原生工具错误明确`Public data approval rejected; HTTP not sent`，模型说明未取数；datasets/files为空，私有calls/snapshots目录不存在。
- Web等待授权时停止：状态cancelled，审批清空，原生工具明确`Public data approval cancelled; HTTP not sent`；无调用收据、快照或产物。
- 随后同一会话发送无需工具的短问答，两次相同Idempotency-Key均202，原生日志只有一条对应user消息和一次答复，最终completed；取消后可继续。
- 用原FinGPT sid请求Claw新dataset的CSV返回400，不能跨会话读文件；未认证internal query/cancel均403。
- 输入只读/私有control不可读由本次119项中的真实macOS Seatbelt canary验证；取消HTTP进行中、缓存/重放、崩溃中间态、坏分页/partial由离线契约测试验证，没有伪称实网故障注入。

## 最终工程验证与审查

在隔离工作树用现有项目venv实际运行：

- `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness python -m pytest tests/research_web --confcutdir=tests/research_web -q`：119 passed in 13.64s，日志`logs/datahub-final-python.log`。
- `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs`：34 passed/0 skipped，177.47ms，日志`logs/datahub-final-javascript.log`。
- `python -m ruff check app/research_web tests/research_web`、black相同目录`--check`（30文件）、isort`--check-only`通过。
- `python -m mypy app/research_web --exclude '/skills/' --follow-imports=skip`：18文件通过，保留untyped-body提示；DataHub额外`--check-untyped-defs`，6文件通过。不声称全仓strict typing。
- `git diff --check`、`python scripts/check_task_completion.py`、`python scripts/check_doc_sync.py`通过；doc_sync提示无匹配源码前缀，实际相关文档已人工同步。
- Task1先红后绿、独立审查3个P2修复复审PASS；Task2独立审查PASS；最终708fbdb→7857426全3744行/37文件审查Spec/Quality均PASS，无剩余P0/P1/P2。轻微空状态分支测试可后续补充。

## 启动与未实施项

当前8088/3081保留运行。若以后停止，在本隔离工作树、已有依赖环境两个终端启动：

```bash
python -m app.research_web.launch_runtime --source /Users/leon/Developer/deepseek-harness --data /Users/leon/.alphafoundry/research-web --source-mode --research-tools
python -m uvicorn app.research_web.main:app --host 127.0.0.1 --port 8088 --timeout-graceful-shutdown 5
```

本机已验证Python为`/Users/leon/Desktop/Projects/AlphaFoundry-runtime-agnostic-core/.venv/bin/python`；DSH源码提交/模型/权限沿用原锁定配置。不要在当前实例仍运行时重复启动。

未实施Seek-Alpha业务工具、DataHub原生MCP出口、基准时间序列、合同/报告原文服务、完整头寸、多用户/远程部署与桌面Windows；本批不宣称具备这些能力。
财联社既有公开来源纳入5项能力目录，新增桥接有离线回归；本批真实研究只新增四类基金来源，没有把前一批财联社实网验收当作新桥接的重新实网验收。
原3080 PID77454未变；旧探针38291仍UE，未重启系统或宣称已回收。没有删除历史资料、安装依赖、读取/复制已有模型密钥、合并或推送分支。
