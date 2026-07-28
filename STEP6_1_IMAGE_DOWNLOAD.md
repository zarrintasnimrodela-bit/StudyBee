# Step 6.1 — Image Zoom and Direct Downloads

- Adds image preview zoom controls from 50% to 300%.
- Keeps images scrollable when zoomed.
- Adds a same-origin Django download endpoint for uploaded files.
- Uploaded PDF, image, DOC, DOCX, PPT, PPTX, XLS, XLSX, ZIP, and other stored files download directly.
- Uploaded solution files download directly too.
- External links remain “Open Original” because third-party sites control their own download behavior.
- Removes duplicate resource ordering in `course_detail()`.
