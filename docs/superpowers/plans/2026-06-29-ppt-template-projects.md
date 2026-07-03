# PPT Template Projects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a static PPT template project type to the report generation center while keeping existing Word projects compatible.

**Architecture:** Report projects gain a `project_type` discriminator. Word projects keep the current DOCX generation path; PPT projects use a small OpenXML projection that scans and replaces `{{placeholder}}` text in `.pptx` templates without requiring animation or slide editing support.

**Tech Stack:** FastAPI, Pydantic, YAML project folders, Python stdlib `zipfile`/XML for PPTX projection, existing frontend static JS workbench, pytest.

---

### Task 1: Project Type and PPT Asset Resolution

**Files:**
- Modify: `reporting/projects/project_manager.py`
- Test: `tests/unit/test_report_project_manager.py`

- [ ] Add failing tests proving old projects default to `word`, PPT projects resolve `active_ppt_template`, and PPT generated reports use `.pptx`.
- [ ] Add `project_type`, `template_path`, and optional `ppt_template_path` fields to `ReportProject`.
- [ ] Load `project_type` from `project.yaml`, defaulting missing values to `word`.
- [ ] Validate `.docx` only for Word and `.pptx` only for PPT.

### Task 2: PPT Projection

**Files:**
- Create: `reporting/projections/ppt.py`
- Test: `tests/unit/test_ppt_template_projection.py`

- [ ] Add failing tests for extracting `{{title}}` placeholders from a minimal PPTX package.
- [ ] Add failing tests for saving a PPTX copy with text placeholders replaced.
- [ ] Implement the projection with stdlib ZIP/XML operations and explicit logging/error handling.

### Task 3: API Shape, Upload, Render, Download

**Files:**
- Modify: `app/api/routes/report_projects.py`
- Test: `tests/unit/test_report_projects_api.py`

- [ ] Add response fields: `project_type`, `template_path`, `template_filename`, `ppt_template_path`, `ppt_template_filename`, `ppt_placeholders`.
- [ ] Update upload to accept `project_type` plus either `.docx` or `.pptx`.
- [ ] Dispatch `/render` by project type. Word keeps current behavior; PPT uses the new projection and writes `.pptx`.
- [ ] Return correct PPTX download MIME type.

### Task 4: Frontend Workbench

**Files:**
- Modify: `app/web/templates/index.html`
- Modify: `app/web/static/js/templates.js`
- Modify: `app/web/static/style.css`
- Test: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] Add upload UI for selecting Word or PPT project type.
- [ ] Show generic template filename plus type label in the project list/detail.
- [ ] Use `ppt_placeholders` for PPT projects and keep `word_placeholders` for Word projects.
- [ ] Adjust generation/download/preview copy to say PPT where appropriate.

### Task 5: Documentation and Verification

**Files:**
- Modify: `docs/modules/reporting.md`
- Modify: `docs/modules/app_api.md`

- [ ] Document `project_type: word | ppt` and PPT static template behavior.
- [ ] Run targeted pytest for project manager, PPT projection, API, and frontend static wiring.
