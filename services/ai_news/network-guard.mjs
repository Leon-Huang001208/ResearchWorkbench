// Loaded before upstream modules in both processes. Original guardedFetch also checks each redirect.
export function assertDestination(input) {
  const url = new URL(input instanceof Request ? input.url : input);
  const host = url.hostname.toLowerCase().replace(/\.$/, '');
  if (host === 'aihot.news' || host.endsWith('.aihot.news')) throw new Error('rwb_outbound_origin_forbidden');
  return url;
}
const originalFetch = globalThis.fetch;
globalThis.fetch = async function rwbFetch(input, options = {}) {
  assertDestination(input);
  // Native fetch is used for credential-bearing providers. Refuse implicit redirects altogether.
  return originalFetch(input, { ...options, redirect: 'error' });
};
