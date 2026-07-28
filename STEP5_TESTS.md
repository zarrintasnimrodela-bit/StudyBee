# Step 5 — Automated Test Suite

This replaces the old `SimpleTestCase` smoke test with database-backed Django tests.

Coverage includes:

- Home page and course search
- Course resource filtering
- Resource title/description search
- Missing-course 404 handling
- Resource model validation
- Upload extension and size validation
- Filename sanitization
- Report form submission
- Unsafe `next` URL protection

Run:

```powershell
python manage.py test
```
