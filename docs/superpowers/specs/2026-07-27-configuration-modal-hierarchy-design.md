# Configuration Modal Hierarchy Design

## Goal

Make every system-configuration modal explain its current state before asking the user to edit it, while keeping secrets safe and removing repeated card-like form rows.

## Shared Structure

Every modal uses the same order: a compact header, an optional concise startup-lock notice, the primary content, and the existing action footer. The primary content is either a compact collection table or a small settings grid. The footer continues to own cancel, test, and save actions.

## Collections

- LLM services, ZhiQiu accounts, iFinD accounts, and web-search keys use a compact table/list surface. Column labels appear once; existing entries are rows, not nested cards.
- Add buttons reveal an inline editing row at the top of the relevant table. Existing entries remain concise and editable in place.
- Account-pool scheduling and iFinD connection settings appear as separate compact settings blocks after the collection, with no empty reserved area.

## Database

- The API still never returns a raw database URL or password.
- The database field displays `已配置` plus a safe source label. If the value is managed by startup configuration, it says `由启动配置管理` and the input remains locked.
- A non-sensitive connection summary is derived in the UI only from existing server-provided fields: it must never reconstruct or expose a connection string. The empty input is labelled as a replacement value, not the current value.
- The restart note appears only for an editable replacement value, and uses short plain language.

## Visual Rules

- Remove saturated section accent bars, dotted labels, and repeated field borders from collection rows.
- Use one surface border per table, a quiet divider between rows, and one consistent action treatment.
- Keep modal content below a readable width, use a two-column settings grid where space permits, and collapse safely on small screens.

## Non-goals

- No secret rehydration, clipboard bypass, or change to configuration API payloads.
- No changes to connection testing, validation, or restart semantics.
