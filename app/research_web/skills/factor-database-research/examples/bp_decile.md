# BP 十分位分组示例

1. 使用 `datahub_get_database_schema` 逐级确认数据库、表，以及证券代码、交易日和 BP 列的真实名称。
2. 调用 `datahub_query_table`，显式选择上述三列，以日期参数过滤并按 BP 升序；若超过单次上限，使用稳定排序和 `offset` 分页。
3. 在记录中保存完整查询参数、返回的 `dataset_id` 与 `manifest_sha256`。
4. 用 `research_run_script` 读取会话内 `rows.json`，剔除缺失 BP，说明重复证券处理规则，再以当期有效样本计算十分位边界。
5. 输出每组样本数、边界与后续收益统计；没有收益列或日期对齐证据时，不生成收益结论。

复现记录模板：

```text
database: <实际数据库>
table: <实际表>
columns: [<证券代码>, <交易日>, <BP>]
filters: <实际参数>
dataset_id: <DataHub 返回值>
manifest_sha256: <manifest 哈希>
```
