# StudyBee Step 7.2 — Report Resolution and Reporter Notifications

## Admin workflow

All moderation is handled from **Admin → Report issues**.

Available actions:

- **Resolve: fix issue and republish resource**
- **Resolve: confirm removal and keep resource hidden**
- **Dismiss report and republish resource**
- **Resend resolution email to reporter**

A linked resource remains hidden while a report is pending. Resolving or dismissing the report can republish it. Confirming removal keeps it hidden.

## Reporter notification

If the reporter entered a contact email, StudyBee sends the outcome automatically after the admin resolves the report. If no email was entered, the report still resolves but no notification can be sent.

`admin_response` is optional. When blank, StudyBee uses an outcome-specific default message.

## Email configuration

Run:

```powershell
python .\tools\configure_report_email.py
```

Local development falls back to Django's console email backend until SMTP credentials are configured.
