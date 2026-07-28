from django.core.management.base import BaseCommand, CommandError

from resources.notifications import send_studybee_email


class Command(BaseCommand):
    help = "Send a StudyBee notification test email."

    def add_arguments(self, parser):
        parser.add_argument(
            "recipient",
            help="Email address that should receive the test.",
        )

    def handle(self, *args, **options):
        recipient = options["recipient"].strip()

        if "@" not in recipient:
            raise CommandError(
                "Enter a valid recipient email address."
            )

        send_studybee_email(
            subject="StudyBee email test",
            body=(
                "This is a StudyBee transactional email test.\n\n"
                "If you received it, report-resolution notifications "
                "are configured correctly."
            ),
            recipient=recipient,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Test email request completed for {recipient}."
            )
        )
