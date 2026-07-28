# StudyBee Step 7.3 — Brevo Email Delivery

Render Free blocks outbound SMTP ports 25, 465, and 587, so Gmail SMTP
cannot send from the deployed free service.

This patch sends report-resolution messages through Brevo's HTTPS API.
Local development and automated tests still fall back to Django's configured
email backend.

Configuration variables:
- BREVO_API_KEY
- BREVO_SENDER_EMAIL
- BREVO_SENDER_NAME
