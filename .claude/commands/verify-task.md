# Verify task

从仓库根目录调用项目规划器；每个改动文件重复传入一个仓库相对路径：

```bash
node scripts/plan_verification.mjs --project . \
  --changed-file <changed-file> \
  --changed-file <another-changed-file>
```

读取规划器输出的 JSON，按其中 `tests`、`documentation`、`ci` 与 `risk` 实际执行或升级交付，并保留真实结果。规划器只生成计划，不执行测试、Git、CI 或发布。

规则唯一真源是 `.agents/verification-policy.json`；本入口不得复制或覆盖路由规则。
