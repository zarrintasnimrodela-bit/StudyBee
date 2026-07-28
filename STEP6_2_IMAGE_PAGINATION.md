# Step 6.2 — Adaptive Image Zoom and Pagination

- Image 100% now means “fit the entire image inside the available viewer area.”
- Both portrait and landscape images resize using width and height.
- Zoom ranges from 50% to 300%.
- Zoomed images remain centered and become scrollable when larger than the viewer.
- Course resources are paginated at 10 items per page.
- Pagination preserves category, syllabus, question type, and search parameters.
- Search values in filter URLs are URL-encoded.
- Added an automated pagination test.
