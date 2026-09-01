import assert from 'node:assert/strict';
import test from 'node:test';

import {
    initDesktopNotifications,
    processPendingDesktopNotifications,
} from '../../app/web/static/js/desktop-notifications.js';

const persisted = (overrides = {}) => ({
    notification_id: 'notification-1',
    alert_event_id: 'event-1',
    profile_id: 'local',
    title: '来自持久化 API 的标题',
    body: '来自持久化 API 的正文',
    status: 'pending',
    created_at: '2026-09-01T09:30:00Z',
    delivered_at: null,
    ...overrides,
});

function response(body, ok = true, status = ok ? 200 : 500) {
    return {
        ok,
        status,
        json: async () => structuredClone(body),
    };
}

function createFetch(records) {
    const calls = [];
    const store = records.map(record => persisted(record));
    const fetchImpl = async (url, options = {}) => {
        const method = options.method || 'GET';
        calls.push({ url, method, body: options.body });
        if (method === 'GET') {
            return response(store);
        }
        assert.equal(method, 'PATCH');
        const id = url.split('/').at(-2);
        const target = store.find(record => record.notification_id === id);
        assert.ok(target, `unknown notification ${id}`);
        const payload = JSON.parse(options.body);
        if (target.status !== payload.expected_status) {
            return response({ detail: 'conflict' }, false, 409);
        }
        target.status = payload.status;
        return response(target);
    };
    return { calls, fetchImpl, store };
}

test('web environment is a no-op and never fetches notifications', async () => {
    let fetchCount = 0;
    const result = await processPendingDesktopNotifications({
        fetchImpl: async () => {
            fetchCount += 1;
            return response([]);
        },
        tauriNotification: undefined,
    });

    assert.deepEqual(result, { outcome: 'not_tauri', processed: 0 });
    assert.equal(fetchCount, 0);
});

test('granted permission sends only pending persisted payloads and records delivery', async () => {
    const { calls, fetchImpl, store } = createFetch([
        {},
        {
            notification_id: 'notification-old',
            title: '已发送',
            body: '不应重复发送',
            status: 'desktop_delivered',
        },
    ]);
    const sent = [];
    const result = await processPendingDesktopNotifications({
        fetchImpl,
        tauriNotification: {
            isPermissionGranted: async () => true,
            requestPermission: async () => assert.fail('permission already granted'),
            sendNotification: async payload => sent.push(payload),
        },
    });

    assert.deepEqual(sent, [{ title: persisted().title, body: persisted().body }]);
    assert.deepEqual(result, { outcome: 'delivered', processed: 1 });
    assert.equal(calls[0].method, 'GET');
    assert.match(calls[0].url, /profile_id=local/);
    assert.match(calls[0].url, /status=pending/);
    assert.equal(calls.filter(call => call.method === 'PATCH').length, 2);
    assert.equal(store[0].status, 'desktop_delivered');
    assert.equal(store[1].status, 'desktop_delivered');
});

test('denied permission records outcome but leaves notification in persisted inbox', async () => {
    const { calls, fetchImpl, store } = createFetch([{}]);
    let sendCount = 0;
    const result = await processPendingDesktopNotifications({
        fetchImpl,
        tauriNotification: {
            isPermissionGranted: async () => false,
            requestPermission: async () => 'denied',
            sendNotification: async () => {
                sendCount += 1;
            },
        },
    });

    assert.deepEqual(result, { outcome: 'desktop_permission_denied', processed: 1 });
    assert.equal(sendCount, 0);
    assert.equal(store.length, 1);
    assert.equal(store[0].status, 'desktop_permission_denied');
    assert.equal(calls.some(call => call.method === 'DELETE'), false);
    const inbox = await fetchImpl('/api/asset-observation/notifications?profile_id=local');
    assert.equal((await inbox.json())[0].notification_id, 'notification-1');
});

test('plugin delivery failure records desktop_failed', async () => {
    const { fetchImpl, store } = createFetch([{}]);
    const result = await processPendingDesktopNotifications({
        fetchImpl,
        tauriNotification: {
            isPermissionGranted: async () => true,
            requestPermission: async () => 'granted',
            sendNotification: async () => {
                throw new Error('native delivery failed');
            },
        },
    });

    assert.deepEqual(result, { outcome: 'desktop_failed', processed: 1 });
    assert.equal(store[0].status, 'desktop_failed');
});

test('concurrent consumers atomically claim one pending notification', async () => {
    const { fetchImpl, store } = createFetch([{}]);
    let sendCount = 0;
    const tauriNotification = {
        isPermissionGranted: async () => true,
        requestPermission: async () => 'granted',
        sendNotification: async () => {
            sendCount += 1;
        },
    };

    await Promise.all([
        processPendingDesktopNotifications({ fetchImpl, tauriNotification }),
        processPendingDesktopNotifications({ fetchImpl, tauriNotification }),
    ]);

    assert.equal(sendCount, 1);
    assert.equal(store[0].status, 'desktop_delivered');
});

test('initializer installs one 60-second single-flight poller that consumes later records', async () => {
    const { calls, fetchImpl, store } = createFetch([]);
    const timers = [];
    const sent = [];
    const options = {
        fetchImpl,
        tauriNotification: {
            isPermissionGranted: async () => true,
            requestPermission: async () => 'granted',
            sendNotification: async payload => sent.push(payload),
        },
        setIntervalImpl: (callback, delay) => {
            timers.push({ callback, delay });
            return 1;
        },
    };

    await Promise.all([
        initDesktopNotifications(options),
        initDesktopNotifications(options),
    ]);
    assert.equal(timers.length, 1);
    assert.ok(timers[0].delay <= 60_000);
    assert.equal(calls.filter(call => call.method === 'GET').length, 1);

    store.push(persisted({ notification_id: 'notification-later' }));
    await timers[0].callback();

    assert.equal(sent.length, 1);
    assert.equal(store[0].status, 'desktop_delivered');
});
