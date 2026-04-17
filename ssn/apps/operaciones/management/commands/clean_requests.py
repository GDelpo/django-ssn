import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...models import BaseRequestModel
from ...services import OperacionesService

logger = logging.getLogger("general")


class Command(BaseCommand):
    help = "Deletes unsent and empty requests older than X days"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Age in days to consider for deletion (default: 7)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.now() - timedelta(days=days)

        qs = BaseRequestModel.objects.filter(
            send_at__isnull=True, created_at__lt=cutoff
        )

        empty = []
        for req in qs:
            counts = OperacionesService.get_count_by_tipo(req)
            if all(count == 0 for count in counts.values()):
                empty.append(req)

        count = len(empty)
        if count != 0:
            deleted_ids = [str(req.uuid) for req in empty]
            for req in empty:
                req.delete()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Deleted {count} unsent and empty requests older than {days} days."
                )
            )
            logger.info(
                f"[clean_requests] Deleted {count} requests (UUIDs: {deleted_ids}) older than {days} days."
            )
