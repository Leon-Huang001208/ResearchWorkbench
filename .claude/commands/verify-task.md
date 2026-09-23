# Verify task

从仓库根目录调用项目规划器；每个改动文件重复传入一个仓库相对路径：

```bash
node scripts/plan_verification.mjs --project . \
  --changed-file <changed-file> \
  --changed-file <another-changed-file>
```

读取 JSON 中的 `requiredLevel`、`validationsByLevel`、`impact`、
`uncoveredRisks` 与 `receiptTemplate`，按 L0→L4 顺序执行实际输出。局部验证失败或
出现非预期行为时，分别追加 `--signal validation_failure` 或
`--signal unexpected_behavior` 重新规划，不得沿用原低等级结论。

执行后保存 plan 与 receipt，再校验：

```bash
node scripts/validate_verification_receipt.mjs --project . \
  --plan <plan-json> \
  --receipt <receipt-json>
```

规划器与回执校验器都只读；它们不执行测试、Git、CI、发布或 JSON 中的命令。

规则唯一真源是 `.agents/verification-policy.json`；本入口不得复制或覆盖路由规则、
等级或门禁。
