from pathlib import Path

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from resources.importers import (
    BulkImportError,
    import_resources_from_csv,
)


class Command(BaseCommand):
    help = (
        "Import or update courses and resources "
        "from a UTF-8 CSV file."
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_path")

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])

        if not csv_path.exists():
            raise CommandError(
                f"CSV file not found: {csv_path}"
            )

        with csv_path.open("rb") as csv_file:
            try:
                result = import_resources_from_csv(
                    csv_file
                )
            except BulkImportError as exc:
                raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Processed {result['processed_rows']} rows. "
                    f"Created {result['created_resources']} resources, "
                    f"updated {result['updated_resources']}, "
                    f"created {result['created_courses']} courses."
                )
            )
        )
