# 全市场组合表单重复事件修复

- 宿主：Mac mini / macOS；Web 最小缺陷修复，不新增依赖或 Python 改动。
- 原任务：market-terminal-20261023；本修复交付任务：market-preview-render-20261024。
- 真实复现：认证全市场页打开组合、导入 CSV，修改现金后，控制台重复出现 `NotFoundError: Failed to set the 'innerHTML' property ... Perhaps it was moved in a 'blur' event handler?`。旧服务、已有账户与持仓没有回退；验收 CSV 没有确认保存。
- 根因：控制器同时接收 input/change；替换聚焦表单会同步发出已应用过的 change，而原输入处理无同值判断，重入整个页面 render 并重复失效预览。
- 改动：仅在组合元数据和持仓单元格的输入分支忽略同值事件。实际改动仍走原预览失效及通知路径；不改变确认、账号或迟到响应守卫。
- RED：新增两条同步 blur-change 重入回归及一条有效预览保全回归，原代码 21 PASS / 3 FAIL，失败原因与真实异常调用路径一致。日志 `logs/market-preview-render-20261024/red.log`。
- GREEN：修复后三个行情相关 JS 模块共65项通过，无skip，实测57.312ms。日志 `logs/market-preview-render-20261024/green.log`。
- 文档：DataHub 的终端组合边界补充重复事件语义；无新节点、API、持久格式或数据流，现有架构/开发映射与13号市场图仍准确。
- 独立 JS 审查已批准当前四文件差异，独立重跑65项通过；最终候选SHA仍另行绑定。
- 真实浏览器复测：仅在本任务独立认证标签临时覆盖`/static/market-terminal.mjs`为候选文件，后端API保持真实。有效CSV预览、修改现金使旧预览失效、重新预览全部完成；复现路径控制台0 errors/0 warnings。随后撤除该单资产覆盖并重载，页面仍“未载入持仓”，未点击确认保存。该证据验证候选前端对真实后端的行为，不代表常驻修复部署；原线上异常日志保留。
- 待完成：完整 Router、同候选原三CI/macOS干净安装、发布及当前常驻版本兼容的部署判断。
- 真实验收原件位于主工作区 `output/playwright/market-terminal-20261024/`，窄屏、板块同批对账及 CSV 导入与新修复的部署状态分别记录。
