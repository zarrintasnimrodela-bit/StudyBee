# StudyBee Step 7 — Major Features Bundle

This bundle adds:

1. Global course/resource search.
2. Structured semester term and year.
3. Student resource submissions with admin moderation.
4. Resource verification, needs-review, and broken statuses.
5. Browser-local favorite and recently viewed courses.
6. Clickable prerequisite course navigation.
7. Admin CSV bulk import and a command-line CSV importer.
8. A working non-JavaScript home search fallback.

Topic/chapter tags are intentionally not included.

## Important behavior

- Student submissions are **not public immediately**. They appear in:
  `Admin → Resource submissions`.
- Approving a submission publishes it as a community resource without an official verification badge.
- Reporting any linked resource immediately hides it publicly and marks it `Needs review` for the admin.
- Favorites and recently viewed courses are stored in the visitor's browser.
- CSV import supports external links, not uploaded binary files.
- Existing legacy semester text is migrated when it matches:
  `Spring 2026`, `Summer 2026`, or `Fall 2026`.
- Existing admin-managed resources are marked Verified during migration.

## Install

Run the commands supplied in the ChatGPT message accompanying this ZIP.

The included migration is:

`resources/migrations/0015_studybee_features.py`

Before running it, make a fresh database backup.

## Admin CSV import

Open:

`Admin → Resources → Bulk import CSV`

Required columns:

`course_code,course_title,title,category,external_link`

Optional columns:

`course_description,hard_prerequisite,soft_prerequisite,lab_type,exam_part,question_type,description,solution_link,semester_term,semester_year,verification_status`

A sample is included as:

`sample_resource_import.csv`

You can also run:

```powershell
python manage.py import_resources_csv .\sample_resource_import.csv
```

## Where bulk imports appear

CSV imports create normal Resource records immediately. They appear in:

- `Admin → Resources`
- The matching course page
- Global search

The included sample creates `Sample Lecture Notes` under `CSE260`.
With pagination, it may be on a later page, so global search is the quickest way to find it.
