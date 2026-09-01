/* ============================================================
   Persisted desktop notifications — Tauri v2 global API only
   ============================================================ */

const PENDING_NOTIFICATIONS_URL =
    '/api/asset-observation/notifications?profile_id=local&status=pending';

async function updateDeliveryState(fetchImpl, notificationId, status) {
    const response = await fetchImpl(
        `/api/asset-observation/notifications/${encodeURIComponent(notificationId)}/delivery`,
        {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status }),
        },
    );
    if (!response.ok) {
        throw new Error(`notification delivery update failed with status ${response.status}`);
    }
}

async function recordOutcome(fetchImpl, records, status) {
    let updated = 0;
    for (const record of records) {
        try {
            await updateDeliveryState(fetchImpl, record.notification_id, status);
            updated += 1;
        } catch (error) {
            console.error('[desktop-notifications] delivery state update failed', {
                notificationId: record.notification_id,
                errorType: error?.name || 'UnknownError',
            });
        }
    }
    return updated;
}

export async function processPendingDesktopNotifications({
    fetchImpl = globalThis.fetch,
    tauriNotification = globalThis.window?.__TAURI__?.notification,
} = {}) {
    if (!tauriNotification) {
        return { outcome: 'not_tauri', processed: 0 };
    }

    let pending;
    try {
        const response = await fetchImpl(PENDING_NOTIFICATIONS_URL);
        if (!response.ok) {
            throw new Error(`notification inbox fetch failed with status ${response.status}`);
        }
        const records = await response.json();
        pending = Array.isArray(records)
            ? records.filter(record => record?.status === 'pending')
            : [];
    } catch (error) {
        console.error('[desktop-notifications] persisted inbox fetch failed', {
            errorType: error?.name || 'UnknownError',
        });
        return { outcome: 'desktop_failed', processed: 0 };
    }

    if (pending.length === 0) {
        return { outcome: 'empty', processed: 0 };
    }

    try {
        let granted = await tauriNotification.isPermissionGranted();
        if (!granted) {
            granted = (await tauriNotification.requestPermission()) === 'granted';
        }
        if (!granted) {
            const processed = await recordOutcome(
                fetchImpl,
                pending,
                'desktop_permission_denied',
            );
            return { outcome: 'desktop_permission_denied', processed };
        }
    } catch (error) {
        console.error('[desktop-notifications] permission check failed', {
            errorType: error?.name || 'UnknownError',
        });
        const processed = await recordOutcome(fetchImpl, pending, 'desktop_failed');
        return { outcome: 'desktop_failed', processed };
    }

    let delivered = 0;
    let failed = 0;
    for (const record of pending) {
        try {
            await tauriNotification.sendNotification({
                title: record.title,
                body: record.body,
            });
            delivered += await recordOutcome(fetchImpl, [record], 'desktop_delivered');
        } catch (error) {
            console.error('[desktop-notifications] native delivery failed', {
                notificationId: record.notification_id,
                errorType: error?.name || 'UnknownError',
            });
            failed += await recordOutcome(fetchImpl, [record], 'desktop_failed');
        }
    }

    if (failed > 0) {
        return { outcome: 'desktop_failed', processed: delivered + failed };
    }
    return { outcome: 'delivered', processed: delivered };
}

export async function initDesktopNotifications() {
    // The explicit global path documents the no-bundler Tauri v2 integration.
    const tauriNotification = window.__TAURI__
        ? window.__TAURI__.notification
        : undefined;
    return processPendingDesktopNotifications({ tauriNotification });
}
