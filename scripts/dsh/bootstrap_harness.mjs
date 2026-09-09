/** Bootstrap AlphaFoundry's isolated DeepSeek Harness checkout and profile. */

import { access, mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const vendor = resolve(root, 'vendor/deepseek-harness')
const plugin = resolve(root, 'runtimes/dsh/plugin')
const runtimeHome = resolve(root, '.runtime/dsh-home')
const deploymentPath = resolve(runtimeHome, 'alphafoundry-deployment')
const profilePath = resolve(runtimeHome, 'profiles/alphafoundry/package.json')
const pinnedRevision = 'b150a551b8d465e31e418e1b2eaf5e79bbb7d28e'
const upstream = 'https://github.com/deepseek-ai/deepseek-harness.git'

function run(command, args, options = {}) {
  return new Promise((resolveRun, reject) => {
    const child = spawn(command, args, { stdio: 'inherit', ...options })
    child.once('error', reject)
    child.once('exit', code => {
      if (code === 0) resolveRun()
      else reject(new Error(`${command} ${args.join(' ')} exited with ${code ?? 'unknown status'}`))
    })
  })
}

async function exists(path) {
  try {
    await access(path)
    return true
  } catch {
    return false
  }
}

async function output(command, args, options = {}) {
  return new Promise((resolveOutput, reject) => {
    const child = spawn(command, args, { stdio: ['ignore', 'pipe', 'inherit'], ...options })
    let stdout = ''
    child.stdout.on('data', chunk => { stdout += chunk })
    child.once('error', reject)
    child.once('exit', code => {
      if (code === 0) resolveOutput(stdout.trim())
      else reject(new Error(`${command} ${args.join(' ')} exited with ${code ?? 'unknown status'}`))
    })
  })
}

async function prepareProfile() {
  let profile = {
    name: 'dsh-profile-alphafoundry',
    private: true,
    dsh: { profile: { bundles: [] } },
  }
  if (await exists(profilePath)) {
    profile = JSON.parse(await readFile(profilePath, 'utf8'))
  }
  const bundles = Array.isArray(profile?.dsh?.profile?.bundles) ? profile.dsh.profile.bundles : []
  profile.dsh ??= {}
  profile.dsh.profile ??= {}
  profile.dsh.profile.bundles = [
    '@deepseek-ai/dsh-base',
    '@deepseek-ai/dsh-web-app',
    ...bundles.filter(bundle => !['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app'].includes(bundle)),
  ]
  await mkdir(dirname(profilePath), { recursive: true })
  await writeFile(profilePath, `${JSON.stringify(profile, null, 2)}\n`, 'utf8')
}

if (!await exists(vendor)) {
  await mkdir(dirname(vendor), { recursive: true })
  await run('git', ['clone', '--depth', '1', '--branch', 'dsh-v0.1.1-rc.2', upstream, vendor])
} else {
  const actual = await output('git', ['-C', vendor, 'rev-parse', 'HEAD'])
  if (actual !== pinnedRevision) {
    throw new Error(`Refusing to alter existing vendor/deepseek-harness at ${actual}; expected ${pinnedRevision}`)
  }
}

await run('pnpm', ['install', '--frozen-lockfile'], { cwd: vendor })
await run('pnpm', ['run', 'build'], { cwd: vendor })
await run('pnpm', ['install', '--frozen-lockfile=false'], { cwd: plugin })
await run('pnpm', ['run', 'build'], { cwd: plugin })
await mkdir(runtimeHome, { recursive: true })

const runtimeEnv = {
  ...process.env,
  DSH_HOME: runtimeHome,
  DSH_TELEMETRY_DISABLED: '1',
  ALPHAFOUNDRY_DSH_DEPLOYMENT_PATH: process.env.ALPHAFOUNDRY_DSH_DEPLOYMENT_PATH ?? deploymentPath,
  ALPHAFOUNDRY_DSH_SKILLS_DIR: process.env.ALPHAFOUNDRY_DSH_SKILLS_DIR ?? resolve(runtimeHome, 'skills'),
}
await prepareProfile()
await run('pnpm', ['dsh', 'plugin', '--profile', 'alphafoundry', 'add', plugin], {
  cwd: vendor,
  env: runtimeEnv,
})
const projectPython = resolve(root, '.venv/bin/python')
const python = process.env.ALPHAFOUNDRY_PYTHON ?? (await exists(projectPython) ? projectPython : 'python3')
await run(python, [
  '-m', 'runtimes.dsh.deploy',
  '--deployment-path', deploymentPath,
  '--dsh-home', runtimeHome,
], { cwd: root, env: runtimeEnv })

console.log(`AlphaFoundry DSH bootstrap complete: ${runtimeHome}`)
