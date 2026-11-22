// Test-process transport fence, inherited by spawned Node children through NODE_OPTIONS.
// MockAgent calls never reach a real socket; every real TCP connection must be literal loopback.
import net from 'node:net';
import dns from 'node:dns';
import { syncBuiltinESMExports } from 'node:module';
const local = host => ['127.0.0.1','::1','localhost'].includes(String(host ?? 'localhost').toLowerCase());
const connect = net.Socket.prototype.connect;
net.Socket.prototype.connect = function (...args) {
  const values = Array.isArray(args[0]) ? args[0] : args;
  const first = values[0];
  const host = first && typeof first === 'object' ? first.host ?? first.hostname : typeof values[1] === 'string' ? values[1] : 'localhost';
  if (!local(host)) throw Object.assign(new Error('test_external_socket_forbidden'), {code:'RWB_TEST_NETWORK_DENIED'});
  return Reflect.apply(connect,this,args);
};
const lookup=dns.lookup;
dns.lookup=function(host,...args){
  if(!local(host)) {
    const callback=args.at(-1);
    const error=Object.assign(new Error('test_external_dns_forbidden'),{code:'RWB_TEST_NETWORK_DENIED'});
    if(typeof callback==='function'){queueMicrotask(()=>callback(error));return;}
    throw error;
  }
  return Reflect.apply(lookup,this,[host,...args]);
};
syncBuiltinESMExports();
