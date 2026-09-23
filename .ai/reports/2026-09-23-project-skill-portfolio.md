# Project Skill portfolio migration

## Scope

- Added sanitized project-owned copies of `cls`, `cnstock`, and `data-connector-development`.
- Retained the existing project-owned `wind-find-finance-skill` and `wind-mcp-skill`; comparison with the former global copies found only `scripts/update-state.json` presence/content differences, so runtime state was not copied.
- Did not add `multi-format-rag`: its global tree mixed 31.5 MB of Chroma databases, binary indexes, spreadsheets, caches, provider experiments, and dependency declarations. It is preserved in private quarantine for rollback, not deleted.
- `zq` remains in its earlier private quarantine. Plaintext credential rotation is still an external prerequisite; no `zq` file was copied into this repository.

## Sanitization receipt

| Skill | Included files | Excluded state files | Final tree SHA-256 |
| --- | ---: | ---: | --- |
| `cls` | 17 | 37 | `db6fb6e74c03581c76c143f98d8e352e5286434277c296510434eb732effd47c` |
| `cnstock` | 7 | 15 | `52dd8eba8a967ef6eacaa88afacd0e3dcbcc3ea0887229ca1751dccff1fbeaee` |
| `data-connector-development` | 1 | 0 | `d1ec6109cea4b61c8c0f54e7b23a81116e5277331a3489d1a424c0585ddb98fe` |

Excluded classes include `.env`, `config.yaml`, locks, logs, outputs, test outputs, caches, Chroma state, binary indexes, SQLite files and spreadsheets. A literal-secret scanner found no included assignment in the migrated trees. No crawler/network command and no dependency installation was executed.

## Boundaries

The three migrated Skills are maintenance workflows for the legacy ingestion/Connector layer. They do not make a source callable in current Research Web. Current availability remains governed by DataHub Provider state, contracts, safe connection projection and real acceptance evidence.

The Python `quick_validate.py` bundled with the system Skill could not run because PyYAML is not installed. No dependency was installed. Repository Node governance tests provide the structural and boundary check for this change.
