/** Verified repository pin for the existing delivery and resource contracts. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath, pathToFileURL} from 'node:url';

const defaultRoot = fileURLToPath(new URL('./vendor/leon-engineering/', import.meta.url));
const files = ['iteration-delivery.mjs', 'resource-lifecycle.mjs', 'harness-storage.mjs', 'lib/resources/lifecycle.mjs', 'schemas/resource-lifecycle-v1.schema.json'];
const sourceCommit = '3913ddb9ac612760fb95bf8d8f7102f948c32d0f';

function regularFile(root, relative) {
  let filename = root;
  for (const part of relative.split('/')) {
    filename = path.join(filename, part);
    if (fs.lstatSync(filename).isSymbolicLink()) throw new Error('runtime alias');
  }
  if (!fs.lstatSync(filename).isFile()) throw new Error('runtime file missing');
  return fs.readFileSync(filename);
}

export function verifyProjectDeliveryRuntime({runtimeRoot = defaultRoot} = {}) {
  try {
    const root = path.resolve(runtimeRoot);
    if (fs.realpathSync(root) !== root || !fs.lstatSync(root).isDirectory()) throw new Error('runtime directory alias');
    // The upstream adapter also supports its source-tree layout. A sibling
    // engine would take precedence over the verified installed-layout pin.
    if (fs.existsSync(path.resolve(root, '../lib/resources/lifecycle.mjs'))) throw new Error('runtime engine ambiguous');
    const manifest = JSON.parse(regularFile(root, 'manifest.json'));
    if (manifest.schemaVersion !== 2 || manifest.frameworkVersion !== '0.19.4' || manifest.sourceCommit !== sourceCommit || !manifest.files
      || Object.keys(manifest.files).length !== files.length) throw new Error('runtime manifest invalid');
    for (const name of files) {
      const hash = crypto.createHash('sha256').update(regularFile(root, name)).digest('hex');
      if (manifest.files[name] !== hash) throw new Error('runtime checksum mismatch');
    }
    return {valid: true, runtimeRoot: root, version: manifest.frameworkVersion, sourceCommit};
  } catch (cause) {
    throw Object.assign(new Error('DELIVERY_RUNTIME_UNVERIFIED', {cause}), {code: 'DELIVERY_RUNTIME_UNVERIFIED'});
  }
}

export async function loadProjectDeliveryRuntime() {
  const {runtimeRoot} = verifyProjectDeliveryRuntime();
  return import(pathToFileURL(path.join(runtimeRoot, 'iteration-delivery.mjs')).href);
}

export async function loadProjectResourceRuntime() {
  const {runtimeRoot} = verifyProjectDeliveryRuntime();
  return import(pathToFileURL(path.join(runtimeRoot, 'resource-lifecycle.mjs')).href);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    if (process.argv.length !== 2) throw new Error('Use project_delivery_runtime.mjs without arguments');
    process.stdout.write(`${JSON.stringify(verifyProjectDeliveryRuntime())}\n`);
  } catch (error) {
    process.stderr.write(`${JSON.stringify({component: 'project-delivery-runtime', code: error.code ?? 'ARGUMENT_ERROR'})}\n`);
    process.exitCode = 1;
  }
}
