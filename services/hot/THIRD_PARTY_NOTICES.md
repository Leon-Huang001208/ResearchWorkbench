# Upstream reuse

AIHOT https://github.com/KKKKhazix/AIHOT
Commit: `8e34e05feb161cb5838e592ee22715f791c7f814`.

`src/material.ts` adapts URL identity and normalized content hashing from
`packages/backend/src/lib/url.ts`, `lib/text.ts`, `lib/ids.ts` and
`content/materials.ts`. RWB rejects URLs carrying credentials, preserves HTTP
versus HTTPS and validates explicit timezone/future publication times.

Upstream PostgreSQL revision, receipt-attempt and pg-boss designs are being
evaluated; their full application, frontend and provider secrets are not copied.
Historical materials will be eligible for long-term event linking in RWB; the
upstream historical exclusion and 14-day recall policy are not adopted.

The AIHOT name/logo are not licensed for this product. Feed content belongs to
its publishers. Store evidence for local research; public use needs the source's
rights. No upstream fonts, logo, screenshots or branding are included.

## MIT License

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
