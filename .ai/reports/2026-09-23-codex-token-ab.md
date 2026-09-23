# Codex Token A/B — post-restart acceptance

## Decision

Do **not** promote the lean-medium profile. It reduced total input, output and reasoning tokens, but failed the predeclared hard gate because non-cached input and weighted usage increased. The live `config.toml` remains on the baseline profile (`high`; the eight candidate plugins remain enabled).

## Fixed task

At ResearchWorkbench commit `ad60a98e0e740335a75ab60968d53ba8f8be73ef`, a fresh `codex exec` process had to inspect the real verification planner/policy and report the route for unknown path `some/new/file.xyz`. Both arms returned the correct behavior:

```json
{"risk":"full-delivery","reason":"unknown_path"}
```

Both runs used the same model/config except for the candidate's `medium` reasoning and eight disabled low-frequency plugins. Both were read-only and ephemeral. No repository file was modified by either run.

## Results

| Metric | Baseline high/full | Lean-medium | Change |
| --- | ---: | ---: | ---: |
| Input tokens | 545,495 | 459,833 | -15.70% |
| Cached input | 480,256 | 392,064 | -18.36% |
| Non-cached input | 65,239 | 67,769 | **+3.88%** |
| Output tokens | 3,264 | 2,393 | -26.69% |
| Reasoning tokens | 2,453 | 1,745 | -28.86% |
| Weighted (`non-cached + output + reasoning`) | 70,956 | 71,907 | **+1.34%** |
| Command-execution items | 8 | 7 | -1 |
| Error items | 5 | 5 | unchanged |
| Quality | correct | correct | unchanged |
| Permissions | read-only | read-only | unchanged |

The first baseline already demonstrated the high-cost failure mode: a narrowly stated question expanded to repeated reads/commands and transport/model refresh errors. Because one sample consumed more than 545k input tokens and took about six minutes, the experiment stopped after the paired minimal test instead of spending roughly twelve similarly large runs. This is a cost-control ruling, not evidence that unrun task classes passed.

## Static context result

Fresh-host measurement must keep cwd constant because project Skills are part of the prompt. In the ResearchWorkbench cwd, after Skill portfolio cleanup and the 0.19.3 restart:

- prompt input: 67,993 → 61,047 bytes (-10.22%);
- `SKILL.md` references: 184 → 102 (-82);
- final prompt SHA-256: `ed8bd113f8bfbc38d0dd7422a737da57d9db2480fc83fe4148317e9bc8bf26cf`.

The earlier 53,617 / 93 measurement was taken in the `claude-engineering` cwd, which does not load ResearchWorkbench project Skills. It remains useful as a framework-cwd measurement but is not used for the ResearchWorkbench before/after percentage.

This fixed-context improvement is retained independently of the rejected profile.

## Evidence hashes

- Baseline JSONL: `e21f7dd59713588fe3e7b731d9739952f9cee6a99af19bec7e29bddbcdb49228`
- Candidate JSONL: `b3915560d98a06129b7b6da89c3db013bf61225ef4404a6fcfdf8bc458459c05`
- Baseline final JSON: `bc2a37c5bda99037c3a7e894d6ecee35d601db3a041082a81783f0de6d4cbe51`
- Candidate final JSON: `67e588695372c1e03592c0b11b85e720556819bf4ac97b810af45879ffd6e819`

Raw files remain local under `/tmp` and are not committed because they contain model/tool event detail. The report contains only aggregate metrics, expected answer and hashes.
