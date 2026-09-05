/** Start AlphaFoundry's isolated DSH Web Host after verifying secret boundaries. */

import { dirname, resolve } from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const vendor = resolve(root, 'vendor/deepseek-harness')
const runtimeHome = resolve(root, '.runtime/dsh-home')
const deploymentPath = resolve(runtimeHome, 'alphafoundry-deployment')
const required = [
  'ALPHAFOUNDRY_BACKEND_URL',
  'ALPHAFOUNDRY_DSH_BRIDGE_TOKEN',
  'ALPHAFOUNDRY_DSH_TOOL_TOKEN',
]
const missing = required.filter(name => !process.env[name])
if (missing.length > 0) {
  throw new Error(`Missing required DSH runtime environment variables: ${missing.join(', ')}`)
}

const child = spawn('pnpm', [
  'dsh', '--profile', 'alphafoundry', '--host', '127.0.0.1', '--no-open',
  '--port', process.env.ALPHAFOUNDRY_DSH_PORT ?? '3280',
], {
  cwd: vendor,
  env: {
    ...process.env,
    DSH_HOME: runtimeHome,
    DSH_TELEMETRY_DISABLED: '1',
    ALPHAFOUNDRY_DSH_DEPLOYMENT_PATH: process.env.ALPHAFOUNDRY_DSH_DEPLOYMENT_PATH ?? deploymentPath,
    ALPHAFOUNDRY_DSH_SKILLS_DIR: process.env.ALPHAFOUNDRY_DSH_SKILLS_DIR ?? resolve(runtimeHome, 'skills'),
  },
  stdio: 'inherit',
})
child.once('error', error => console.error(`AlphaFoundry DSH Host failed to start: ${error.message}`))
child.once('exit', code => { process.exitCode = code ?? 1 })
