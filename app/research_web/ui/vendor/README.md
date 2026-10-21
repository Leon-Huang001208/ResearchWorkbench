# Local chart dependencies

User-authorized fixed distributions for the AlphaFoundry indicator migration:

- ECharts 5.5.0: five-panel market terminal and estimated chip distribution.
- Chart.js 4.4.7: capital-flow composition when the real inputs form a valid partition.

Files are extracted from the official versioned npm tarballs after checking the
registry SHA-512 integrity. `asset-vendor-lock.json` pins the distributed bytes
and attribution files. Run `node scripts/check_asset_vendor.mjs` from the source
root to verify them offline. The Web installation includes these files and loads
them from its own `/static/vendor/` origin; no CDN is used.

Retain each included LICENSE and NOTICE when redistributing. AlphaFoundry's
indicator layout and algorithms are migrated from the user-provided local
project; its database, coordinator, synthetic theme data and Agent engine are
not part of these third-party chart distributions.
