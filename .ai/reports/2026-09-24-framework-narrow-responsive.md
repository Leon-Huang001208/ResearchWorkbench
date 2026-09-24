# Research Framework narrow-screen evidence

## Scope

This task corrects the existing Gold and Dollar framework detail pages at narrow browser widths. At 900px and
below, the hero and snapshot summary now stack, metadata dates remain on one line, and the closed framework Bot
entry occupies a dedicated 44px slot at the right edge of the horizontal anchor rail. The Bot entry therefore
remains reachable without covering chart evidence. The open Bot, framework routes, data and snapshot contracts,
chart renderers, desktop layout, runtime, and backend APIs are unchanged.

The product shell remains the page's only `main` landmark. Both dedicated renderers preserve the
`.framework-canvas` styling contract while exposing their continuous canvas as a named `section` region.

## TDD evidence

The first focused RED run produced 9 passes and 3 expected failures for the missing named canvas region, Bot
accessible name, and 900px compact contract. The first GREEN run passed 12/12 after the minimal renderer and CSS
change. Screenshot review then found that a compact fixed button could still cover a chart. A second focused RED
added a docked-layout contract; GREEN passed 12/12 after moving the single closed button into the canvas layout
and assigning it an independent anchor-rail grid slot.

## Browser evidence

`node tests/e2e/research_web_goldar_v0.mjs` passed in real local Chrome for Gold and Dollar across light/dark at
1440x900, 1280x720, 1024x768, 768x1024, and 390x844. The run observed one `main` landmark, a named `SECTION`
canvas, no document or product-main horizontal overflow, at least 44px anchor targets, and chart-local overflow
readiness in every case. At 768 and 390 both frameworks stacked the hero, kept all metadata within its cells,
rendered a 44x44 Bot entry named `问当前框架`, and reported no intersection between that entry and the canvas.
Keyboard anchor traversal, reduced-motion behavior, closed/open Bot, and the two-card hub also passed with zero
console or page errors.

Evidence is stored under `outputs/frameworks-v1/verification.json`; screenshots include light/dark 768px and
390px overviews plus the existing desktop and mobile Bot captures. Manual image review confirmed the 768px and
390px light/dark layouts and the mobile open Bot remain legible and non-overlapping.

## Incremental validation

The project planner initially selected local-only L1. Documentation governance then failed because the user's
untracked `.venv.broken-20260911/` contains third-party Markdown; the repository content itself was not the
cause. Replanning with `validation_failure` expanded the closure to L2. The final documentation run used a
temporary Git exclude containing only that exact unrelated directory and passed without deleting or modifying
it.

The planned Python command first failed because the installer-owned product environment intentionally has no
pytest. The preserved development environment provided pytest, but its first run inherited a SOCKS proxy and
failed because that environment does not contain `socksio`. The final process-local run removed proxy variables
for this offline test only; it did not mutate system proxy settings or install a package, and passed 9/9.

The complete post-change L0-L2 closure passed:

| Plan ID | Level | Result | Duration |
| --- | --- | --- | ---: |
| `documentation-governance` | L0 | passed; 520 files, 69 current, 0 violations | 0.13 s |
| `python-file-index` | L0 | passed; generated index verified | 0.91 s |
| `research-web-architecture` | L1 | passed; 62/62 | 2.23 s |
| `research-web-frameworks-ui` | L1 | passed; 12/12 | 0.11 s |
| `project-constraints-local` | L2 | passed; 29 paths, 0 violations | 0.16 s |
| `research-web-frameworks-python` | L2 | passed; 9/9 | 23.29 s |

The planner selected no external gate. This Web-only local task therefore does not claim GitHub, Windows,
desktop, Tauri, sidecar, or installer verification. The supplementary Chrome run passed in 20.70 s and is kept
outside the receipt IDs because the policy did not select a separate browser validation item. The 16 generated
files under `outputs/frameworks-v1/` are included in the 29-path plan and receipt as low-risk framework artifacts.

## Architecture review

The change stays within the existing native UI renderer and responsive CSS boundary. It adds no service,
dependency, route, API, data flow, persistence boundary, or runtime component, so architecture diagrams remain
current.

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"The change only corrects responsive layout and landmark semantics inside the existing Gold and Dollar native UI renderers; system components and data flow are unchanged.","diagrams":[]} -->
