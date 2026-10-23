# 市场终端 A：最终开发页浏览器验收

- 宿主：macOS；任务类型：功能开发的前端验收。本报告仅认证本机离线开发页，不认证真实行情质量、常驻部署、生产认证或其他平台。
- 验收源码基线：`1ef85ee802f37d857d629a9fd2f4b586b6ab5c53`。本轮没有修改产品源代码、后端或部署 profile。
- 浏览器：CUA 唯一浏览器工具，Chrome；未操作用户的真实常驻标签页。子任务 IAB 不可用，使用独立 Chrome 验收标签页。
- 旧夹具 `57420` 的 PID `14077`、工作目录和启动命令均核实为本任务资源，经 `/fixture/shutdown` 优雅关闭。按原命令重新启动最终源码，随机端口为 `60038`，PID `2567`，进程 session `81349`，数据根仍为 `/tmp/rwb-market-terminal-20261023-fixture`。

## 结果：开发页 UI 已验证

| 检查 | 实际结果 |
| --- | --- |
| 指数搜索与分组 | 搜索“国企红利”得到 1 项；规模组 9 项；红利组 2 项；全部 24 项。 |
| 星标、持久化、恢复默认 | 取消国企红利后常用 6 项；恢复默认 7 项；新增国证成长后重载常用 8 项且仍置顶；最后恢复 7 项。 |
| 图表默认选择 | 24 个实际分时选择控件，默认勾选 3 个。 |
| 日内／波段／中期 | 日内显示六格真实夹具涨跌幅；浮点边界结果为“成长／价值差异较小”。波段、中期因夹具缺历史，六格均为缺口，风格和规模待确认。总分与权益区间始终待验证。 |
| 六轴公式 | 趋势、广度、情绪、资金、估值、风险均实际展开，包含公式字段。趋势详情显示 24 指数、均值 0.75、来源快照和历史不足状态。 |
| 板块成分 | 点击离线行业 8 后进入 `view=quotes&board_id=BK0008`，3 只实际匹配成分股，来源元数据保留。 |
| 排序与股票搜索 | 代码列 descending → ascending 状态改变；搜索 920000 得到 1 行，CSV 链接绑定同筛选和快照。 |
| 暂停／恢复 | 显示“自动刷新已暂停”，恢复后显示行情 30 秒／板块资金 60 秒。 |
| 明暗与窄屏 | 通过应用设置实际切换浅色／深色。1440×1000 与 390×844 均保存实际截图。390 下文档、body、main 宽度均为 390，未发生页面横向溢出；窄屏分组仍可操作。 |
| 错误与副作用 | 浏览器控制台捕获 warning/error 为 0；夹具 `session_creates=0`、`inflight=0`。 |

详细 29 条实际浏览器记录：`logs/market-terminal-20261023/browser-final-proof.json`。DOM、控制台及夹具状态分别留存在 `browser-final-dom.txt`、`browser-final-console.json`、`browser-final-fixture-state.json`。夹具日志：`browser-fixture-final.log`。

## 截图

`logs/market-terminal-20261023/` 下：

- `terminal-light-1440-final.png`：最终浅色 1440×1000；同时替换原 `terminal-light-1440.png`。旧错误尺寸／旧读数截图保存在 `terminal-light-1440-superseded.png`，不继续作为最终证据。
- `terminal-dark-1440-final.png`：最终深色 1440×1000。
- `terminal-light-390-final.png`、`terminal-dark-390-final.png`：最终浅色／深色 390×844。
- `terminal-dark-390-indices-final.png`：窄屏指数控件和卡片。
- `terminal-formula-final.png`：趋势公式和来源展开。
- `terminal-members-final.png`：板块成分匹配后的行情页。

## 回归与冻结

实际执行：

```text
node --test tests/javascript/research_web_market.test.mjs tests/javascript/research_web_market_navigation.test.mjs tests/javascript/research_web_market_terminal.test.mjs
```

结果：62/62 PASS。完整日志为 `logs/market-terminal-20261023/js-market-browser-final.log`。

验收绑定源码 SHA-256：

```text
market.mjs          4478113007d19313c1d7f5762876ed8da5c5e6b32aa58f8802c78b88415cc4c4
market-terminal.mjs 9f5551f4b639aa47fa0232e44938647c4f0ed0289fc533455779e46c83dc3d84
market.css          a84e7e43fd75e574d3b74b25acbf86c579f93d3a8bc4835fedc9a2ce44843f5a
market_analysis.py  e45ccdbd1830b4cc68225a653b721231b8031cac101a4e7cb8787c273dc15552
```

产品文件继续冻结，未发现需要新增前端修复的缺陷。浏览器临时视口已 reset，测试主题恢复跟随系统，自有验收标签页已关闭。夹具服务保留供主任务最终复核，未把资源状态宣称为 cleaned。

未验证：真实供应商完整性、生产认证页面、常驻部署、Windows/Linux 原生、Docker 产品验收；它们不是本次离线 UI 证据。
