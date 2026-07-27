# Report Configuration Detail Regression Design

## Goal

Restore the report configuration detail view so a selected placeholder displays its real unified configuration near the top of the panel, without reintroducing legacy configuration schemas or Query fallbacks.

## Cause

The configuration editor is a grid whose direct children are the toolbar, status strip, issue queue, and detail form. Its two-row definition gives the status strip the flexible row, pushing the detail form to the bottom. Later CSS also overrides the intended compact detail-form sizing.

## Decisions

- Keep `report_config.yaml` with `placeholders` mapping and `prompt_templates.md` as the only configuration sources.
- Change the editor shell to a column flex layout so toolbar, status, issue queue, and selected-detail form flow in document order.
- Preserve the readable detail card and its edit entry points. It shows the real Prompt binding, retrieval state, writing limits, fixed template/Excel fields, and writing structure when configured.
- Keep long data-source lists collapsible; do not restore old inline Query, section-list, V1, or V2 behaviour.

## Verification

- Static tests assert the editor shell does not reserve its flexible row for the status strip and that the readable detail renderer remains in the main form.
- Existing frontend static tests and JavaScript syntax checking pass.
- Visually check the 华安 ETF report project when the local development server is available.

## Non-goals

- No report-config schema, API, generation, or prompt-library change.
- No changes to the left navigation or report-generation workflow.
