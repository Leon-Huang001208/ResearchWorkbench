/** Stdlib CLI validation bridge: stdin is non-secret JSON, stdout is normalized non-secret JSON. */
import { parseConfig,assertNodeRuntime } from '../src/config.ts';
try {
  assertNodeRuntime();
  let data = '';
  for await (const chunk of process.stdin) {
    data+=chunk;
    if(Buffer.byteLength(data)>65536) throw Error('hot_config_limit');
  }
  console.log(JSON.stringify(parseConfig(JSON.parse(data))));
} catch {
  console.log(JSON.stringify({error:'hot_config_invalid'}));
  process.exitCode=1;
}
