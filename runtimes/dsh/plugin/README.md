# AlphaFoundry DSH Plugin

`index.ts` is an installable DSH Bundle for AlphaFoundry's **project-managed,
isolated** DSH Host pinned to `dsh-v0.1.1-rc.2`. The project bootstraps the
upstream checkout under `vendor/deepseek-harness/`, and runs it with an isolated
`.runtime/dsh-home`; it never reads a user's pre-existing `$DSH_HOME`.
`runtimes.dsh.deploy` materializes the canonical Core `ToolSpec` / `SkillSpec`
deployment manifest and `$DSH_HOME/skills/<skill>/SKILL.md` files.
The Bundle mounts that generated directory through DSH `customSkillDirs` with
default roots disabled, so AlphaFoundry's deployment is the only Skill source
for this Host.

The bundle uses `ctx.webServer` for an authenticated loopback bridge, converts
allowlisted `ToolSpec` values to DSH `defineTool` registrations, and calls only
the loopback AlphaFoundry API with the **DSH-to-AlphaFoundry tool token**.
The reverse direction uses a separate **AlphaFoundry-to-DSH bridge token**.
Input and output are validated by both sides; a skill may complete only by
calling `alphafoundry_submit_skill_result` with its declared JSON Schema.

The embedded FinGPT page uses an exact-origin `postMessage` handshake before
it sends a one-time `launch_id`. The DSH frame then performs its own same-origin
loopback request; this request is accepted only when its HTTP `Origin` equals
the DSH frame origin. Parent-origin validation remains in the frame message
handler, so neither the browser route nor the message channel accepts an
arbitrary remote origin.

## Project-managed Host setup

Bootstrap uses a pinned DSH checkout and does not add the DSH SDK to
AlphaFoundry's root `package.json`:

```bash
npm run dsh:bootstrap
```

Set `ALPHAFOUNDRY_BACKEND_URL`, `ALPHAFOUNDRY_DSH_BRIDGE_TOKEN`,
`ALPHAFOUNDRY_DSH_TOOL_TOKEN`, then start the loopback Host with
`npm run dsh:web`. `ALPHAFOUNDRY_DSH_DEPLOYMENT_PATH` defaults to
`.runtime/dsh-home/alphafoundry-deployment`. Configure AlphaFoundry with
`ALPHAFOUNDRY_DSH_BRIDGE_URL=http://127.0.0.1:<port>` and the matching bridge
token. Never put either token in a profile, manifest, API response, or log.

The plugin does not contain market-data, research-method, workflow, evaluator,
or renderer logic. Those remain in AlphaFoundry Core Domain.
