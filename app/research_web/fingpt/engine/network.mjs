import { AsyncLocalStorage } from 'node:async_hooks';
const requests = new AsyncLocalStorage();
export const withSignal = (signal, fn) => requests.run(signal, fn);
export function requestSignal(ms = 15000) {
  const signal = requests.getStore();
  signal?.throwIfAborted();
  return signal ? AbortSignal.any([signal, AbortSignal.timeout(ms)]) : AbortSignal.timeout(ms);
}
