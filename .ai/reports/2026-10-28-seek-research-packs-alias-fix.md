# C1/C2 SPEC P1二次修复：孤儿capture不可降级上传

base `1eae76fb8da015f1dea85826e57ee3570c2885b0`；task起始ID/日志目录仍20261027。
macOS Web本地修复，无push/部署/新依赖/网络/模型/秘密/业务数据库/新源身份系统。
不开始C6或QUALITY，完成后交同一SPEC复核。前两轮P1及恢复fixture失败报告保留，不改成PASS。

## 真实缺口及最小闭环

SPEC在正文目录sync第二次注入StoreError：旧rollback只包index保存，raw+proof已存在而无
web_evidence；Store.files自动登记后，uploads-only经真实Dossier type=file读到网页正文。
原P1 EOF修复已关闭，但这项权限降级不能用之前local PASS掩盖。

本波try覆盖proof创建、body exclusive创建/write/flush/fsync、目录sync、读回、index发布。
_write_capture_body在创建后立即保存文件与父目录dev/inode；_rollback_capture_body只有
同父目录/同inode/独立普通文件才unlink，已有文件/替换对象不删。全部异常恢复原files与
source记录；cleanup自身失败日志明确保留并继续抛原错误，私有proof保持immutable。

防线不依赖清理：source_file_identifier纯metadata识别固定inputs/web-24hex.txt及既有
source path标记，不依赖是否发布或proof有效。未发布受管来源不会被Store.files发现/登记/
展示成uploads；陈旧files索引也不能授权。Dossier file alias固定拒受管来源；Claw普通
file-reference拒绝改名复制，source/Dossier原身份交接保持。Store.file_path/open_file
作为HTTP预览/下载和现消费者共用边界：先核已发布身份/当前web权限/metadata+proof，再在
已授权时核实际正文hash，无递归调用。缺/坏proof或无pub记录均不能在web-enabled时降级。

普通真实上传具有API产生的UUID前缀，不匹配受管命名。已发布web source在原web权限下
HTTP/source读取保留，撤web则拒正文；普通上传及其文件引用仍合法。没有新8场景合同、
source identity迁移或通用HTTP/备份重构，固定operator/kernel/Native/output/140table不改。

## 实际TDD和验证

- RED：4 failed/15.53s，正文sync回滚和真实合法orphan的valid/missing/corrupt proof均复现。
- 首目标GREEN：5 passed/19.28s，新增cleanup自身失败仍拒alias；每种orphan用uploads-only
  与web-enabled分别测试真实Dossier file、HTTP preview/download和Claw文件再复制。
- 邻近单轮：19 passed、1 fixture failed/49.84s，涵盖post-create write/readback/index
  失败、已有inode保护、原atomic/元数据权限/旧source质量与Claw项目。唯一正例fixture
  使用本来不支持的.txt上传获400；改为受支持.md，不改变产品附件格式或源权限断言。
- 普通上传fixture的手写web-*.txt改为upload-web-*以符合真实上传UUID前缀与保留命名差异；
  最终正例另走真实上传API，不靠改scope或伪metadata让上传通过。
- 最终格式后目标与两Native结果记于下方；源SHA绑定该候选，没有旧run改标新候选。
- Ruff/Black六文件/isort/pyindex生成及check/diff check通过；首次cleanup blind-except
  lint失败保留，收窄实际IO异常后通过。Mypy仍NOT_RUN，无安装。

全部HTTP内容沿现source_capture_fixture同进程真实HTTPResponse/reader及deny_external，
无公共fetch子进程。模拟2026-10-28 capture clock及对应Shanghai as_of保持，历史/future
反例未放宽。真实Native各自Darwin marker，portable权限/alias用例不整体skip。

## 交接边界

证据在`logs/research-packs-aliasfix-20261027/`，protected review根只读不清理。
前轮捕获证明/worker IPC/legacy proofless不回填与保全边界保持；source_coverage、角色、
地域、发表时点未知不变。完整性总门仍ROOT_PENDING；live/model/CI/部署及其它平台NOT_RUN。
本轮临时资源收尾不等于全任务cleaned。最终本地候选交原SPEC，未获复核不冒称可交付。

<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"The fix closes orphan source aliases inside existing Host publication, file access and source handoff boundaries without new APIs, engines or identity systems.","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"Existing Store/Dossier/HTTP shared file authorization now preserves managed source identity before body access, including failed and crashed publications; normal uploads remain unchanged.","diagrams":[]} -->

## 最终回执

格式后生产4文件不再改变。两真实Native **2 passed/40.37s**，source9SHA回执保留于
alias-final-receipt.json；同轮10个alias setup errors为ruff移除未显式使用的pytest fixture
导入所致，不记作功能PASS。恢复fixture后alias **10 passed/42.46s**，日志SHA
`8ef3103d382a7985273a65a4ba95aaf0a0e77b0f236dd35deca13d22e459ed00`。
随后仅改fixture绑定为项目惯例api=fixtures.api解决PLC0414，未改任何生产文件或断言；
合法source/真实UUID上传/文件引用最终正例 **1 passed/4.53s**，日志SHA
`1a9309b6fbc7f735019ae728ac0f62df6f51fab599bf669879904fe2b3b45482`。
对应alias-positive-final-receipt source9SHA绑定最终源码并unchanged=true；Native使用相同
4份生产字节，未机械重复Native或此前19通过的邻近。6文件Ruff/Black/isort、pyindex及
差异空白检查最终通过，保留fixture导入/风格预检失败日志，不伪改前轮结果。

6个本轮明确owner/PID/UID的opaque根，在原dev/inode与无open复查、118份必要索引/source/
proof/Native产物归档且hash读回后回收1,356,049,975字节。alias-owned-closeout.json保留
各原路径和归档/原件SHA；未操作protected review根、旧50、Docker、常驻或其它worktree。
仅本轮临时资源完成，不将全任务标cleaned。
