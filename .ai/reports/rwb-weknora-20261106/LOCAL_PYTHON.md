# 本地 Python Router 验证

- 状态：completed；宿主 macOS；WIP 验证，不能作为 exact-SHA 验收。
- HEAD基线：`f1939eccdcfe924ed661cff7314ccb8ddf7eebc4`；工作区存在本任务源码/文档改动，不自认证最终候选。
- 冻结清单 SHA-256：`77487d1b9f044410d33afc095ef4d56694b2b8e1b04865480cbdb595c454eb19`，753个node IDs，未裁剪。
- 收尾完成 38/38批、753/753 node IDs；JUnit 753：752 PASS、1 原有SKIP、0失败/错误；剩余0未完成。
- 受管批次累计637.459秒，含原第11批中断81.721秒，不含容量等待。

| 批次 | node IDs | tests/fail/errors/skips | 实际pytest/初次入口退出码 | 状态 | 秒 | 回执 |
| --- | ---: | --- | --- | --- | ---: | --- |
| router-python-001 | 20 | 20/0/0/1 | 0/0 | completed | 9.03 | `logs/weknora-router-python/private/router-python-001.receipt.json` |
| router-python-002 | 20 | 20/0/0/0 | 0/0 | completed | 4.95 | `logs/weknora-router-python/private/router-python-002.receipt.json` |
| router-python-003 | 20 | 20/0/0/0 | 0/0 | completed | 3.675 | `logs/weknora-router-python/private/router-python-003.receipt.json` |
| router-python-004 | 20 | 20/0/0/0 | 0/0 | completed | 3.487 | `logs/weknora-router-python/private/router-python-004.receipt.json` |
| router-python-005 | 20 | 20/0/0/0 | 0/0 | completed | 4.235 | `logs/weknora-router-python/private/router-python-005.receipt.json` |
| router-python-006 | 20 | 20/0/0/0 | 0/0 | completed | 3.197 | `logs/weknora-router-python/private/router-python-006.receipt.json` |
| router-python-007 | 20 | 20/0/0/0 | 0/0 | completed | 2.446 | `logs/weknora-router-python/private/router-python-007.receipt.json` |
| router-python-008 | 20 | 20/0/0/0 | 0/0 | completed | 2.317 | `logs/weknora-router-python/private/router-python-008.receipt.json` |
| router-python-009 | 20 | 20/0/0/0 | 0/0 | completed | 2.877 | `logs/weknora-router-python/private/router-python-009.receipt.json` |
| router-python-010 | 20 | 20/0/0/0 | 0/1 | completed（恢复） | 30.84 | `logs/weknora-router-python/private/router-python-010.receipt.json` |
| router-python-011 | 20 | 20/0/0/0 | 0/1 | completed（恢复） | 138.983 | `logs/weknora-router-python/private/router-python-011.receipt.json` |
| router-python-012 | 20 | 20/0/0/0 | 0/1 | completed（恢复） | 12.296 | `logs/weknora-router-python/private/router-python-012.receipt.json` |
| router-python-013 | 20 | 20/0/0/0 | 0/1 | completed（恢复） | 14.369 | `logs/weknora-router-python/private/router-python-013.receipt.json` |
| router-python-014 | 20 | 20/0/0/0 | 0/1 | completed（恢复） | 46.036 | `logs/weknora-router-python/private/router-python-014.receipt.json` |
| router-python-015 | 20 | 20/0/0/0 | 0/1 | completed（恢复） | 53.727 | `logs/weknora-router-python/private/router-python-015.receipt.json` |
| router-python-016 | 20 | 20/0/0/0 | 0/1 | completed（恢复） | 49.68 | `logs/weknora-router-python/private/router-python-016.receipt.json` |
| router-python-017 | 20 | 20/0/0/0 | 0/1 | completed（恢复） | 47.957 | `logs/weknora-router-python/private/router-python-017.receipt.json` |
| router-python-018 | 20 | 20/0/0/0 | 0/1 | completed（恢复） | 51.005 | `logs/weknora-router-python/private/router-python-018.receipt.json` |
| router-python-019 | 20 | 20/0/0/0 | 0/1 | completed（恢复） | 50.577 | `logs/weknora-router-python/private/router-python-019.receipt.json` |
| router-python-020 | 20 | 20/0/0/0 | 0/1 | completed（恢复） | 48.823 | `logs/weknora-router-python/private/router-python-020.receipt.json` |
| router-python-021 | 20 | 20/0/0/0 | 0/1 | completed（恢复） | 5.608 | `logs/weknora-router-python/private/router-python-021.receipt.json` |
| router-python-022 | 20 | 20/0/0/0 | 0/0 | completed | 1.895 | `logs/weknora-router-python/private/router-python-022.receipt.json` |
| router-python-023 | 20 | 20/0/0/0 | 0/0 | completed | 2.047 | `logs/weknora-router-python/private/router-python-023.receipt.json` |
| router-python-024 | 20 | 20/0/0/0 | 0/0 | completed | 2.528 | `logs/weknora-router-python/private/router-python-024.receipt.json` |
| router-python-025 | 20 | 20/0/0/0 | 0/0 | completed | 2.205 | `logs/weknora-router-python/private/router-python-025.receipt.json` |
| router-python-026 | 20 | 20/0/0/0 | 0/0 | completed | 2.125 | `logs/weknora-router-python/private/router-python-026.receipt.json` |
| router-python-027 | 20 | 20/0/0/0 | 0/0 | completed | 2.311 | `logs/weknora-router-python/private/router-python-027.receipt.json` |
| router-python-028 | 20 | 20/0/0/0 | 0/0 | completed | 2.178 | `logs/weknora-router-python/private/router-python-028.receipt.json` |
| router-python-029 | 20 | 20/0/0/0 | 0/0 | completed | 1.975 | `logs/weknora-router-python/private/router-python-029.receipt.json` |
| router-python-030 | 20 | 20/0/0/0 | 0/0 | completed | 2.273 | `logs/weknora-router-python/private/router-python-030.receipt.json` |
| router-python-031 | 20 | 20/0/0/0 | 0/0 | completed | 2.597 | `logs/weknora-router-python/private/router-python-031.receipt.json` |
| router-python-032 | 20 | 20/0/0/0 | 0/0 | completed | 2.069 | `logs/weknora-router-python/private/router-python-032.receipt.json` |
| router-python-033 | 20 | 20/0/0/0 | 0/0 | completed | 2.368 | `logs/weknora-router-python/private/router-python-033.receipt.json` |
| router-python-034 | 20 | 20/0/0/0 | 0/0 | completed | 9.948 | `logs/weknora-router-python/private/router-python-034.receipt.json` |
| router-python-035 | 20 | 20/0/0/0 | 0/0 | completed | 2.274 | `logs/weknora-router-python/private/router-python-035.receipt.json` |
| router-python-036 | 20 | 20/0/0/0 | 0/0 | completed | 4.003 | `logs/weknora-router-python/private/router-python-036.receipt.json` |
| router-python-037 | 20 | 20/0/0/0 | 0/0 | completed | 6.101 | `logs/weknora-router-python/private/router-python-037.receipt.json` |
| router-python-038 | 13 | 13/0/0/0 | 0/0 | completed | 2.447 | `logs/weknora-router-python/private/router-python-038.receipt.json` |

证据：`logs/weknora-router-python/private/` 保存每批stdout/stderr/JUnit/result/正式收尾回执，成功根即时按身份回收。
第11批初次被3GiB容量门中断（-15，无JUnit），原nonce、active和初次证明保持至同nonce恢复成功。retry-1仅预检未运行；retry-2以同batchId/20 IDs在原根retry-active真实执行20 PASS、退出0，再经原入口退役；不覆盖原中断及预检证明。
资源UF_TRACKED恢复逐项验证nonce/uid/device/inode/nlink1/源文件SHA/无占用，仅对批准的合成resources副本清除0x40；前后inode/SHA相同，独立attribute-recovery证明，不改检查器或未知对象。
WIP阶段：前200例先于后续dispatcher origin、multiuser冷Doctor和knowledge maintenance guard修改执行；第11批retry-2及后续批次单独保留运行时源码blob映射。源码/HEAD变化如实记录；最终候选和新增CLI回归由主任务另外认证。
原有Windows-native skip：test_native_windows_runner_uses_real_host_detection_without_claiming_vendor_access，requires a native Windows runner。

最终复核：38/38正式回执均为retired；本任务受管临时根剩余0。753个固定node IDs全部完成（752 PASS、1原有Windows-native SKIP），0失败/错误，0 NOT_RUN。第12–38批运行期间源码blob前后漂移0；这些源码映射及第11批retry-2映射单列保留，仍不认证exact-SHA或未执行平台。

四模块覆盖：local_integrations 107、protocol 81、api 213、service_manager 352。全部批次累计637.459秒，含原容量中断81.721秒，不含暂停等待；原失败、容量预检、属性恢复及重试原件保留。
