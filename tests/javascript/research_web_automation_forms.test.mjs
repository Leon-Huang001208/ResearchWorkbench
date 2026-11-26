import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  automationTarget,
  buildDeliveryChannel,
  buildSchedule,
  createAutomationForms,
} from '../../app/research_web/ui/automation-forms.mjs';

function values(map) {
  return { get: k => (k in map ? map[k] : null), getAll: k => map[k] ?? [] };
}

test('a daily schedule carries hour and minute but no weekday or day', () => {
  const s = buildSchedule(values({ schedule_kind: 'daily', time: '08:30' }));
  assert.deepEqual(s, { kind: 'daily', timezone: 'Asia/Shanghai', hour: 8, minute: 30 });
});

test('weekly adds a weekday; monthly adds a day', () => {
  assert.equal(buildSchedule(values({ schedule_kind: 'weekly', time: '09:00', weekday: '3' })).weekday, 3);
  assert.equal(buildSchedule(values({ schedule_kind: 'monthly', time: '09:00', day: '15' })).day, 15);
});

test('a once schedule uses an absolute timestamp instead of a time of day', () => {
  const s = buildSchedule(values({ schedule_kind: 'once', once_at: '2026-12-01T09:00' }));
  assert.equal(s.once_at, '2026-12-01T09:00');
  assert.equal(s.hour, undefined);
});

test('the timezone is overridable and defaults to Shanghai', () => {
  assert.equal(buildSchedule(values({})).timezone, 'Asia/Shanghai');
  assert.equal(buildSchedule(values({ timezone: 'UTC' })).timezone, 'UTC');
});

test('smtp channels carry host, port, sender and split recipients', () => {
  const body = buildDeliveryChannel(values({
    kind: 'smtp', name: '邮件',
    smtp_host: 'smtp.example.com', smtp_port: '465',
    smtp_username: '', sender: 'a@example.com',
    recipients: ' x@example.com , y@example.com , ',
  }));
  assert.equal(body.recipients.length, 2);
  assert.deepEqual(body.recipients, ['x@example.com', 'y@example.com']);
  assert.equal(body.smtp_port, 465);
  assert.equal(body.smtp_username, null, 'blank username becomes null, not empty string');
  assert.equal(body.endpoint, undefined, 'smtp must not also set an endpoint');
});

test('non-smtp channels carry an endpoint and never smtp fields', () => {
  const body = buildDeliveryChannel(values({ kind: 'webhook', name: 'hook', endpoint: 'https://x.test' }));
  assert.equal(body.endpoint, 'https://x.test');
  assert.equal(body.smtp_host, undefined);
});

test('a secret is only included when provided', () => {
  assert.equal(buildDeliveryChannel(values({ kind: 'webhook' })).secret, undefined);
  assert.equal(buildDeliveryChannel(values({ kind: 'webhook', secret: 's3' })).secret, 's3');
});

test('output formats come from delivery_formats for workflows and metadata for capabilities', () => {
  const catalog = {
    reportWorkflows: [{ id: 'w1', delivery_formats: ['pdf'] }],
    capabilities: [{ id: 'c1', kind: 'analysis', metadata: { default_formats: ['md'] } }],
  };
  assert.deepEqual(automationTarget(catalog, 'report_workflow', 'w1').outputFormats, ['pdf']);
  assert.deepEqual(automationTarget(catalog, 'analysis', 'c1').outputFormats, ['md']);
  assert.deepEqual(automationTarget(catalog, 'analysis', 'missing').outputFormats, []);
});

function harness({ throwOn = null } = {}) {
  const s = { success: '', error: '', busy: [], renders: 0, loads: [], closed: 0, saved: null };
  const api = {
    saveDeliveryChannel: async () => { if (throwOn === 'channel') throw new Error('渠道失败'); },
    createAutomation: async body => { if (throwOn === 'automation') throw new Error('自动化失败'); s.saved = body; },
  };
  return {
    s,
    forms: createAutomationForms({
      api,
      getCatalog: () => ({ reportWorkflows: [{ id: 'w1', delivery_formats: ['pdf'] }], capabilities: [] }),
      isAutomationBusy: () => false,
      setAutomationBusy: v => { s.busy.push(v); },
      closeAutomationForm: () => { s.closed += 1; },
      isReportBusy: () => false,
      setReportBusy: () => {},
      loadCatalog: async names => { s.loads.push(names); },
      render: () => { s.renders += 1; },
      setSuccess: v => { s.success = v; },
      setError: v => { s.error = v; },
      clearMessages: () => { s.success = ''; s.error = ''; },
      reportOperations: { saveSchedule: async (id, body) => { s.saved = [id, body]; } },
    }),
  };
}

function withFormData(map, body) {
  const original = globalThis.FormData;
  globalThis.FormData = class { get(k) { return k in map ? map[k] : null; } getAll(k) { return map[k] ?? []; } };
  try { return body(); } finally { globalThis.FormData = original; }
}

test('saving a delivery channel reports the credential store and refreshes channels', async () => {
  const h = harness();
  const form = { reset() {} };
  const outcome = await withFormData({ kind: 'webhook', name: 'h', endpoint: 'https://x' }, () => h.forms.saveDeliveryChannel(form));
  assert.equal(outcome, 'saved');
  assert.match(h.s.success, /系统凭据库/);
  assert.deepEqual(h.s.loads[0], ['deliveryChannels']);
  assert.deepEqual(h.s.busy, [true, false]);
});

test('saving an automation closes the form and leaves it disabled', async () => {
  const h = harness();
  const form = { reset() {} };
  const outcome = await withFormData({
    target: 'report_workflow|w1|3',
    name: '晚间报告',
    input_template: 'run',
    schedule_kind: 'daily',
    time: '18:00',
    channel_id: ['c1'],
    include_attachments: 'on',
  }, () => h.forms.saveAutomation(form));
  assert.equal(outcome, 'saved');
  assert.equal(h.s.closed, 1);
  assert.match(h.s.success, /保持停用/);
  assert.deepEqual(h.s.saved.output_formats, ['pdf']);
  assert.deepEqual(h.s.saved.delivery.channel_ids, ['c1']);
  assert.equal(h.s.saved.delivery.include_attachments, true);
  assert.equal(h.s.saved.target_version, 3);
});

test('a failed automation keeps the form open for correction', async () => {
  const h = harness({ throwOn: 'automation' });
  const form = { reset() {} };
  await withFormData({ target: 'report_workflow|w1|1', name: 'x' }, () => h.forms.saveAutomation(form));
  assert.equal(h.s.closed, 0, 'form stays open so the user can fix it');
  assert.equal(h.s.error, '自动化失败');
});

test('report schedule maps manual to disabled and weekly to explicit fields', async () => {
  const h = harness();
  await withFormData({ kind: 'manual', enabled: 'on' }, () => h.forms.saveReportSchedule({ dataset: { reportScheduleForm: 'w1' } }));
  assert.deepEqual(h.s.saved[1], {
    kind: 'manual', enabled: false, timezone: 'Asia/Shanghai',
    once_at: null, weekday: null, hour: null, minute: null,
  });

  await withFormData({ kind: 'weekly', enabled: 'on', weekday: '2', hour: '9', minute: '30' },
    () => h.forms.saveReportSchedule({ dataset: { reportScheduleForm: 'w1' } }));
  assert.deepEqual(h.s.saved[1], {
    kind: 'weekly', enabled: true, timezone: 'Asia/Shanghai',
    once_at: null, weekday: 2, hour: 9, minute: 30,
  });
});

test('a once report schedule carries once_at and nulls the weekly fields', async () => {
  const h = harness();
  await withFormData({ kind: 'once', enabled: 'on', once_at: '2026-12-01T09:00' },
    () => h.forms.saveReportSchedule({ dataset: { reportScheduleForm: 'w1' } }));
  assert.equal(h.s.saved[1].once_at, '2026-12-01T09:00');
  assert.equal(h.s.saved[1].weekday, null);
});
