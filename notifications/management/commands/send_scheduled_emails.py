from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import MagicLoginToken
from notifications import scheduler

TOKEN_RETENTION = timedelta(days=30)  # promised in the privacy policy


class Command(BaseCommand):
    help = "Send due next-block, nudge, door-open and weekly-progress emails. Safe to run hourly."

    def handle(self, *args, **options):
        counts = scheduler.run()
        total = sum(counts.values())
        detail = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "nothing due"
        self.stdout.write(f"Sent {total} email(s): {detail}")
        purged, _ = MagicLoginToken.objects.filter(created_at__lt=timezone.now() - TOKEN_RETENTION).delete()
        if purged:
            self.stdout.write(f"Deleted {purged} old login link record(s)")
