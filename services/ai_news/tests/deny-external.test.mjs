import test from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import http from 'node:http';
import dns from 'node:dns';
import './deny-external.mjs';
test('acceptance transport fence blocks public sockets and DNS before any external request',async()=>{
  const socket=new net.Socket();
  try {assert.throws(()=>socket.connect(443,'203.0.113.7'),/test_external_socket_forbidden/);}
  finally {socket.destroy();}
  const error=await new Promise(resolve=>dns.lookup('provider.invalid',err=>resolve(err)));
  assert.equal(error.code,'RWB_TEST_NETWORK_DENIED');
  const server=http.createServer((_req,res)=>res.end('local-fake-provider'));
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try {const response=await fetch(`http://127.0.0.1:${server.address().port}`);assert.equal(await response.text(),'local-fake-provider');}
  finally {await new Promise(resolve=>server.close(resolve));}
});
