# Step 6 — Preview Security Hardening

Changes:

- Upgraded PDF.js from 3.11.174 to 5.7.284.
- Loads PDF.js as an ES module before loading `course.js`.
- Replaced database-originated preview titles, URLs, images, and iframe markup with safe DOM creation.
- Allows only HTTP and HTTPS preview URLs.
- Uses exact-host-or-subdomain checks instead of unsafe `hostname.includes(...)`.
- Validates YouTube and Google Drive IDs before generating embed URLs.
- Adds `noopener noreferrer` to new-tab links.
- Replaces same-origin AJAX fragments without assigning through `innerHTML`.
- Keeps the existing adaptive scrollable PDF viewer unchanged.
