import logging
import os
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger("general")


class Command(BaseCommand):
    help = "Deletes preview Excel files older than X hours"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=1,
            help="Age in hours to consider for deletion (default: 1)",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        cutoff = datetime.now() - timedelta(hours=hours)

        previews_path = os.path.join(settings.MEDIA_ROOT, "previews")
        if not os.path.exists(previews_path):
            self.stdout.write(self.style.WARNING("Preview folder does not exist."))
            logger.warning("Preview folder does not exist.")
            return

        removed_files = []
        for fname in os.listdir(previews_path):
            if fname.startswith("solicitud_") and fname.endswith(".xlsx"):
                fpath = os.path.join(previews_path, fname)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                    if mtime < cutoff:
                        os.remove(fpath)
                        removed_files.append(fname)
                except Exception as e:
                    logger.warning(f"Error removing file {fname}: {e}")

        count = len(removed_files)
        if count:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deleted {count} preview Excel files older than {hours} hours."
                )
            )
            logger.info(
                f"[clean_preview_excels] Deleted {count} files: {removed_files} older than {hours} hours."
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"No preview Excel files older than {hours} hours found."
                )
            )
            logger.info(
                f"[clean_preview_excels] No files to delete older than {hours} hours."
            )
