import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const catalogRoot = new URL(
  '../../docs/architecture/merged-platform/detailed/catalog/',
  import.meta.url,
);

const load = async (name) =>
  JSON.parse(await readFile(new URL(name, catalogRoot), 'utf8'));

const factEnvelopeFields = [
  'as_of',
  'observed_at',
  'available_at',
  'source_refs',
  'freshness_status',
  'quality_flags',
];

test('blueprint identifiers are unique and typed', async () => {
  const capabilities = await load('capabilities.json');
  const atlas = await load('api-atlas.json');
  const traceability = await load('traceability.json');
  const ids = [
    ...capabilities.capabilities.map((item) => item.id),
    ...capabilities.pages.map((item) => item.id),
    ...atlas.interfaces.map((item) => item.id),
    ...traceability.services.map((item) => item.id),
    ...traceability.data_owners.map((item) => item.id),
    ...traceability.events.map((item) => item.id),
  ];

  assert.equal(new Set(ids).size, ids.length);
  assert.ok(
    capabilities.capabilities.every((item) =>
      /^CAP-[A-Z]+-\d{3}$/.test(item.id),
    ),
  );
  assert.ok(capabilities.pages.every((item) => /^PAGE-P\d{2}$/.test(item.id)));
  assert.ok(atlas.interfaces.every((item) => /^API-[A-Z]+-\d{3}$/.test(item.id)));
});

test('every active capability and write API has an implementation trace', async () => {
  const capabilities = await load('capabilities.json');
  const atlas = await load('api-atlas.json');
  const traceability = await load('traceability.json');
  const traces = new Map(
    traceability.traces.map((item) => [item.capability_id, item]),
  );

  for (const capability of capabilities.capabilities) {
    const trace = traces.get(capability.id);
    assert.ok(trace, `missing trace for ${capability.id}`);
    if (capability.decision === 'remove') {
      assert.ok(
        trace.replacement_capability_ids?.length > 0,
        `${capability.id} must name its replacement`,
      );
      continue;
    }
    assert.ok(trace.page_ids.length > 0 || trace.local_interaction === true);
    assert.ok(trace.api_ids.length > 0 || trace.local_interaction === true);
  }

  for (const api of atlas.interfaces.filter((item) => item.method !== 'GET')) {
    assert.ok(api.idempotency.required, `${api.id} must declare idempotency`);
    assert.ok(api.service_id);
    assert.ok(
      api.write_data_owner_ids.length > 0 || api.effect === 'control-only',
    );
  }
});

test('all fact responses expose provenance and freshness', async () => {
  const atlas = await load('api-atlas.json');
  for (const api of atlas.interfaces.filter(
    (item) => item.response_kind === 'fact',
  )) {
    assert.deepEqual(api.fact_envelope_fields, factEnvelopeFields);
  }
});
