/** Host-only bootstrap on private stdin. argv/environment never receive passwords. */
import { startService,type ServiceBootstrap } from '../src/service.ts';

let service: Awaited<ReturnType<typeof startService>> | undefined;
try {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if(size>65536) throw Error('hot_bootstrap_limit');
    chunks.push(Buffer.from(chunk));
  }
  const input = JSON.parse(Buffer.concat(chunks).toString('utf8')) as ServiceBootstrap;
  service = await startService(input);
  process.stdout.write(JSON.stringify({ protocol:'rwb-hot/v1',state:'initialized',pid:process.pid,port:service.port,owner:service.owner })+'\n');
  const stop = async () => {
    try { await service!.close(); process.exitCode=0; }
    catch { process.exitCode=1; }
  };
  process.once('SIGTERM',()=>{ void stop(); });
  process.once('SIGINT',()=>{ void stop(); });
} catch {
  process.stdout.write(JSON.stringify({ protocol:'rwb-hot/v1',state:'failed',code:'hot_service_start_failed' })+'\n');
  process.exitCode=1;
}
