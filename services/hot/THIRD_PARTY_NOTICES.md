# Upstream reuse

AIHOT https://github.com/KKKKhazix/AIHOT
Commit: `8e34e05feb161cb5838e592ee22715f791c7f814`.

`src/material.ts` adapts URL identity and normalized content hashing from
`packages/backend/src/lib/url.ts`, `lib/text.ts`, `lib/ids.ts` and
`content/materials.ts`. RWB rejects URLs carrying credentials, preserves HTTP
versus HTTPS and validates explicit timezone/future publication times.

Upstream PostgreSQL revision, receipt-attempt and pg-boss designs are being
evaluated; the full upstream application and provider secrets are not copied.
The bounded frontend adaptation is documented below.
Historical materials will be eligible for long-term event linking in RWB; the
upstream historical exclusion and 14-day recall policy are not adopted.

The AIHOT name/logo are not licensed for this product. Feed content belongs to
its publishers. Store evidence for local research; public use needs the source's
rights. No upstream fonts, logo, screenshots or branding are included.

## Frontend reading-pattern adaptation (2026-10-13)

Reference commit: `652bd6bf4190df0030824dd86a982ea96f5623d5` from the same AIHOT repository.
`app/research_web/ui/hot-reader.css` adapts semantic light/dark colour tokens and
reading density from `apps/web/app/app.css`; `hot-reader.mjs` adapts the ranked
strip/date-rail/card organization from `features/feed/HotTopics.tsx`, `Timeline.tsx`
and `FeedItem.tsx`. RWB keeps its own identity, native JS controllers, data contracts,
eight external columns and private runtime. Observation time is explicitly distinct
from publication/effective time, and rankings are labelled as a page subset.
No AIHOT name/logo, upstream private data, model leaderboard, Codex reset monitor,
or site-specific operational module is incorporated. The license text below covers
this adaptation as well as the earlier backend reuse.

## MIT License text

Copyright (c) 2026 数字生命卡兹克

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
