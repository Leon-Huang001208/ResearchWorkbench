# Private Multiuser Implementation Plan

**Goal:** 邀请制私网用户登录同一Mac mini，独立使用FinGPT/Claw会话和服务器文件。

**Architecture:** 新增显式服务器入口、SQLite身份库和认证网关；每用户复用既有Web/DSH进程合同和独立数据根。默认单用户路径不改变。

**Tech Stack:** Python标准库sqlite3/hashlib/secrets、已有FastAPI/httpx、现有DSH/Seatbelt；无新增依赖。

1. [x] 身份库 `multiuser/accounts.py`：测试账号唯一性、scrypt摘要、登录令牌哈希、过期、停用/密码重置撤销及私有路径拒绝；最小实现后运行目标pytest。
2. [x] Runtime与后端profile：测试两用户不同root/端口/令牌、容量、启动失败与仅终止受管进程；限制宿主工具和native文档，验证internal直接调用也拒绝。
3. [x] 网关与浏览器：测试固定origin、会话cookie、CSRF/限速、管理员权限、登录路由、内部路径及代理header清洗；复用现有研究UI，增加独立账号页和退出入口。
4. [x] CLI及说明：交互式管理员初始化、服务器启动、Doctor，不把密码放CLI参数或日志；同步安装、安全、架构/API与报告。
5. [ ] 执行Router、原单用户与双用户集成回归、原生沙箱及浏览器检查；独立评审后经受管交付PR/CI/合并/安全收尾。真实模型、部署、数据迁移保持未运行。

Acceptance uses actual requests, distinct A/B sentinel files, revocation while SSE is open, and denied direct backend requests. Fixture transport is recorded separately from real DSH and browser evidence. No receipt may label missing platform/model evidence PASS.
