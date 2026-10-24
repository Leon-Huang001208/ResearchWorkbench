# 资产部署CI日志容量修复

资产V9只修复已复现的CI证据容量阻断：压缩下载仍限8MB，ZIP总展开仍限64MB/2000项，单job展开明确限16MB，保留完整流、UTF-8、CRC、唯一路径、checkout/tree与时限校验；超过新上限仍拒绝。固定产品b500fcbe、实际前版b4384470和新reader哈希，V1–V8旧身份保持；无新服务、HTTP、依赖、秘密、数据根或执行引擎，原图拓扑保持。完整候选须重新Router/独评/原三CI/Mac安装；实际空闲、全账号保全和认证页面另证。

真实Checks40051989169日志0_checks.txt为8045256字节；原8000000门拒绝，常驻仍b438。自动化RED为1失败1通过，失败明确为合法完整日志超限，未先修改实现。新V9固定已合并b500产品及新reader，不改V8恢复身份。新增容量边界/尾部checkout完整保全反例，保留伪造长度/CRC/路径/符号链接矩阵。所有资格、实际部署及锁屏实页分别取证；不安装包、不触发模型、不启用数据库或计划。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅更新原Native固定reader容量和封闭V9分派；version4事务、恢复、主实例网关与DSH拓扑不变，无新运行节点。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"CI日志解压有界容量调整不改变账号授权、数据根、BirthFence或全账号保全；原图拓扑与安全边界仍准确。","diagrams":[]} -->
