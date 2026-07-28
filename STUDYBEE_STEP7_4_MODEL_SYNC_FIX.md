# StudyBee Step 7.4 — Report Model Sync Fix

This hotfix restores the ReportIssue model fields and methods required by:

- resources/admin.py
- resources/notifications.py
- migration 0017_report_resolution_notifications.py

It fixes Django admin errors for:
- resolution
- resolved_by
- resolved_at
- notification_sent_at
- notification_error

After copying:
1. Run `python manage.py makemigrations --check --dry-run`
2. Run `python manage.py migrate`
3. Run `python manage.py check`
4. Run `python manage.py test`
