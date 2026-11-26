/**
 * Automation-owned form submissions: delivery channels, automations, report schedules.
 *
 * All three build a payload from FormData, post it, then refresh the catalogs the
 * panel reads. The schedule builders are pure and exported so the hour/minute,
 * weekly and monthly shapes can be checked without a DOM.
 */

/**
 * Build the schedule object a saved automation runs on.
 *
 * `once` carries an absolute timestamp; the recurring kinds carry hour/minute
 * plus their own discriminator (weekday for weekly, day for monthly).
 */
export function buildSchedule(values) {
  const kind = String(values.get('schedule_kind') || 'daily');
  const schedule = {
    kind,
    timezone: String(values.get('timezone') || 'Asia/Shanghai'),
  };
  if (kind === 'once') {
    schedule.once_at = String(values.get('once_at') || '');
    return schedule;
  }
  const [hourText, minuteText] = String(values.get('time') || '09:00').split(':');
  schedule.hour = Number(hourText);
  schedule.minute = Number(minuteText);
  if (kind === 'weekly') schedule.weekday = Number(values.get('weekday'));
  if (kind === 'monthly') schedule.day = Number(values.get('day'));
  return schedule;
}

/**
 * Build the delivery-channel payload, which differs by transport kind.
 * SMTP carries host/port/recipients; everything else carries an endpoint.
 */
export function buildDeliveryChannel(values) {
  const kind = String(values.get('kind') || 'webhook');
  const body = { name: String(values.get('name') || ''), kind, enabled: true };
  const secret = String(values.get('secret') || '');
  if (secret) body.secret = secret;

  if (kind === 'smtp') {
    body.smtp_host = String(values.get('smtp_host') || '');
    body.smtp_port = Number(values.get('smtp_port'));
    body.smtp_username = String(values.get('smtp_username') || '') || null;
    body.sender = String(values.get('sender') || '');
    body.recipients = String(values.get('recipients') || '')
      .split(',')
      .map(value => value.trim())
      .filter(Boolean);
  } else {
    body.endpoint = String(values.get('endpoint') || '');
  }
  return body;
}

/**
 * Resolve the automation target and the output formats it supports.
 * Report workflows and capability targets store their defaults in different places.
 */
export function automationTarget(catalog, targetKind, targetId) {
  const target = targetKind === 'report_workflow'
    ? (catalog.reportWorkflows || []).find(item => item.id === targetId)
    : (catalog.capabilities || []).find(item => item.id === targetId && item.kind === targetKind);
  const outputFormats = targetKind === 'report_workflow'
    ? target?.delivery_formats || []
    : target?.metadata?.default_formats || [];
  return { target, outputFormats };
}

/**
 * @param {object} deps
 * @param {object} deps.api
 * @param {() => object} deps.getCatalog
 * @param {() => boolean} deps.isAutomationBusy
 * @param {(busy: boolean) => void} deps.setAutomationBusy
 * @param {() => void} deps.closeAutomationForm
 * @param {() => boolean} deps.isReportBusy
 * @param {(busy: boolean) => void} deps.setReportBusy
 * @param {(names: string[]) => Promise<void>} deps.loadCatalog
 * @param {() => void} deps.render
 * @param {(message: string) => void} deps.setSuccess
 * @param {(message: string) => void} deps.setError
 * @param {() => void} deps.clearMessages
 * @param {object} deps.reportOperations
 */
export function createAutomationForms({
  api,
  getCatalog,
  isAutomationBusy,
  setAutomationBusy,
  closeAutomationForm,
  isReportBusy,
  setReportBusy,
  loadCatalog,
  render,
  setSuccess,
  setError,
  clearMessages,
  reportOperations,
}) {
  return {
    /** Save an outbound channel. Secrets go to the OS credential store, never the catalog. */
    async saveDeliveryChannel(form) {
      if (isAutomationBusy()) return 'busy';
      const body = buildDeliveryChannel(new FormData(form));
      setAutomationBusy(true);
      clearMessages();
      render();
      try {
        await api.saveDeliveryChannel(body);
        setSuccess('外发渠道已保存到系统凭据库。');
        await loadCatalog(['deliveryChannels']);
        return 'saved';
      } catch (error) {
        setError(error.message);
        return 'failed';
      } finally {
        setAutomationBusy(false);
        render();
      }
    },

    /** Save an automation. It is created disabled until the user reviews its locked content. */
    async saveAutomation(form) {
      if (isAutomationBusy()) return 'busy';
      const values = new FormData(form);
      const [targetKind, targetId, versionText] = String(values.get('target') || '').split('|');
      const catalog = getCatalog();
      const { outputFormats } = automationTarget(catalog, targetKind, targetId);

      setAutomationBusy(true);
      clearMessages();
      render();
      try {
        await api.createAutomation({
          name: String(values.get('name') || ''),
          target_kind: targetKind,
          target_id: targetId,
          target_version: Number(versionText),
          input_template: String(values.get('input_template') || ''),
          workspace_id: 'research',
          output_formats: outputFormats,
          mcp_tools: [],
          schedule: buildSchedule(values),
          delivery: {
            channel_ids: values.getAll('channel_id').map(String),
            include_attachments: values.get('include_attachments') === 'on',
          },
        });
        closeAutomationForm();
        setSuccess('Automation 已保存并保持停用；确认锁定内容后再启用。');
        await loadCatalog(['automations', 'automationRuns']);
        return 'saved';
      } catch (error) {
        setError(error.message);
        return 'failed';
      } finally {
        setAutomationBusy(false);
        render();
      }
    },

    /** Save a report workflow schedule. */
    async saveReportSchedule(form) {
      if (isReportBusy()) return 'busy';
      const workflowId = form.dataset.reportScheduleForm;
      const values = new FormData(form);
      const kind = String(values.get('kind') || 'manual');
      const enabled = values.get('enabled') === 'on' && kind !== 'manual';
      const body = {
        kind,
        enabled,
        timezone: 'Asia/Shanghai',
        once_at: kind === 'once' ? String(values.get('once_at') || '') || null : null,
        weekday: kind === 'weekly' ? Number(values.get('weekday')) : null,
        hour: kind === 'weekly' ? Number(values.get('hour')) : null,
        minute: kind === 'weekly' ? Number(values.get('minute')) : null,
      };
      await reportOperations.saveSchedule(workflowId, body);
      return 'saved';
    },
  };
}
