# 多用户报告证据序列化修复

宿主：24GB Mac mini / macOS；类型：功能缺陷修复；本平台范围：离线回归、原生沙箱、macOS安装CI及另行受控的真实模型验收。Windows/Linux原生验收保持NOT_RUN。

## 复现与边界

已部署1739378版本的真实并发验收中，模型把范围限制写入missing，或为行数创建numeric_claim却未把原句放进对应section。原质量门正确返回incomplete，不能把这些报告称为交付通过。失败证据保留在Mac mini私有operator目录，不将用户会话、提示或密钥提交仓库。

## 修复

<!-- architecture-review {"group":"files","structure":"unchanged","reason":"显式格式helper沿同一会话resources生成证据字段；Host独立核验及原输出交付链保留，不新增节点、schema或可信数据来源。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"共享service仅补充模型报告组装提示，不增加HTTP端点或改变原冻结需求、一次补查及下载409合同。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"共享service的报告提示不改变Automation授权、调度、恢复或投递，不新增执行节点及模型预算。","diagrams":[]} -->

新增显式calculation_evidence格式helper：同一配方四项观测生成对应章节、逐字claim/operand.quote、notes与作者提供的coverage映射；行数有独立章节。helper不读取输入、认定观测可信、消除missing或写质量状态。Host原数值/来源/需求/字节/409检查不变。DSH仍为唯一研究引擎，补查预算不增加。服务提示说明helper调用及missing语义，真实限制和缺口均须保留。

## 验证与安装

回归复用既有test_research_calculations.py与Research Web Checks步骤，不新增CI job或依赖。验证状态与精确候选日志记录在本任务交付证据，完成后补充实际结果；单元或安装通过不能代替四用户真实生成验收。

已核对requirements/web.in、requirements/web.lock、scripts/setup_web.py、docs/research-web-installation.md及research-web-bootstrap.yml：无依赖/安装接口/凭据能力变更；固定资源仍由原会话resources复制流程提供。干净macOS安装须由同候选原Bootstrap证明，不能用现有全局环境代替。
