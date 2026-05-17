# Module: app/web

## Responsibility

`app/web` provides the Web Workbench UI, including dashboard, research interface, candidate review, and learning center.

---

## Design Rules

- Keep frontend logic organized by feature
- Use consistent styling patterns
- Follow accessibility best practices
- Make API dependencies explicit
- Test main user flows in browser
- Update UI docs when surface changes

---

## Files

### `app/web/templates/*.html`

Purpose:
- Jinja2 templates for HTML pages
- Page structure and layout

Update this section when:
- New pages are added
- Layout structure changes
- Template organization changes

### `app/web/static/*.js`

Purpose:
- Frontend JavaScript logic
- API client interactions
- User interface behavior

Update this section when:
- New JS modules are added
- API interaction patterns change
- UI behavior changes

### `app/web/static/*.css`

Purpose:
- Styling for the web interface
- Visual design and layout

Update this section when:
- Visual design changes
- Layout styling changes
- New components are styled

### `app/web/main.py`

Purpose:
- FastAPI routes for serving the web interface
- Template rendering endpoints

Update this section when:
- New routes are added
- Template rendering logic changes

---

## Required Tests

- Browser verification via Playwright MCP
- Page load verification
- Main interaction flow testing

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/app_web.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`