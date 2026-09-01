/* ============================================================
   Persisted desktop notifications — Tauri v2 global API only
   ============================================================ */

const PENDING_NOTIFICATIONS_URL =
    '/api/asset-observation/notifications?profile_id=local&status=pending';
const DESKTOP_NOTIFICATION_POLL_MS = 60_000;

let pollingInitialized = false;
let notificationPollInFlight = null;

async function updateDeliveryState(
    fetchImpl,
    notificationId,
    status,
    expectedStatus,
    deliveryClaimToken = undefined,
) {
    const payload = { status, expected_status: expectedStatus };
    if (deliveryClaimToken !== undefined) {
        payload.delivery_claim_token = deliveryClaimToken;
    }
    const response = await fetchImpl(
        `/api/asset-observation/notifications/${encodeURIComponent(notificationId)}/delivery`,
        {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        },
    );
    if (response.status === 409) {
        return null;
    }
    if (!response.ok) {
        throw new Error(`notification delivery update failed with status ${response.status}`);
    }
    return response.json();
}

async function recordOutcome(
    fetchImpl,
    records,
    status,
    expectedStatus,
    deliveryClaimToken = undefined,
) {
    let updated = 0;
    for (const record of records) {
        try {
            const transitioned = await updateDeliveryState(
                fetchImpl,
                record.notification_id,
                status,
                expectedStatus,
                deliveryClaimToken,
            );
            updated += transitioned ? 1 : 0;
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
                'pending',
            );
            return { outcome: 'desktop_permission_denied', processed };
        }
    } catch (error) {
        console.error('[desktop-notifications] permission check failed', {
            errorType: error?.name || 'UnknownError',
        });
        const processed = await recordOutcome(
            fetchImpl,
            pending,
            'desktop_failed',
            'pending',
        );
        return { outcome: 'desktop_failed', processed };
    }

    let delivered = 0;
    let failed = 0;
    for (const record of pending) {
        let claimed = false;
        try {
            const claim = await updateDeliveryState(
                fetchImpl,
                record.notification_id,
                'desktop_delivering',
                'pending',
            );
            claimed = claim?.delivery_claim_token || null;
        } catch (error) {
            console.error('[desktop-notifications] delivery claim failed', {
                notificationId: record.notification_id,
                errorType: error?.name || 'UnknownError',
            });
        }
        if (!claimed) {
            continue;
        }
        try {
            await tauriNotification.sendNotification({
                title: record.title,
                body: record.body,
            });
            delivered += await recordOutcome(
                fetchImpl,
                [record],
                'desktop_delivered',
                'desktop_delivering',
                claimed,
            );
        } catch (error) {
            console.error('[desktop-notifications] native delivery failed', {
                notificationId: record.notification_id,
                errorType: error?.name || 'UnknownError',
            });
            failed += await recordOutcome(
                fetchImpl,
                [record],
                'desktop_failed',
                'desktop_delivering',
                claimed,
            );
        }
    }

    if (failed > 0) {
        return { outcome: 'desktop_failed', processed: delivered + failed };
    }
    return { outcome: 'delivered', processed: delivered };
}

function runNotificationPoll(options) {
    if (notificationPollInFlight) {
        return notificationPollInFlight;
    }
    notificationPollInFlight = processPendingDesktopNotifications(options)
        .finally(() => {
            notificationPollInFlight = null;
        });
    return notificationPollInFlight;
}

export function initDesktopNotifications(options = {}) {
    // The explicit global path documents the no-bundler Tauri v2 integration.
    const globalTauriNotification = typeof window !== 'undefined' && window.__TAURI__
        ? window.__TAURI__.notification
        : undefined;
    const tauriNotification = options.tauriNotification ?? globalTauriNotification;
    if (!tauriNotification) {
        return Promise.resolve({ outcome: 'not_tauri', processed: 0 });
    }
    const pollOptions = {
        fetchImpl: options.fetchImpl ?? globalThis.fetch,
        tauriNotification,
    };
    if (pollingInitialized) {
        return notificationPollInFlight
            ?? Promise.resolve({ outcome: 'already_initialized', processed: 0 });
    }
    pollingInitialized = true;
    const setIntervalImpl = options.setIntervalImpl ?? globalThis.setInterval;
    setIntervalImpl(
        () => runNotificationPoll(pollOptions),
        DESKTOP_NOTIFICATION_POLL_MS,
    );
    return runNotificationPoll(pollOptions);
}
