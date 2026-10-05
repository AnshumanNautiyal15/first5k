from django.core.management.base import BaseCommand

from notifications import scheduler


class Command(BaseCommand):
    help = "Send due next-block, nudge, door-open and weekly-progress emails. Safe to run hourly."

    def handle(self, *args, **options):
        counts = scheduler.run()
        total = sum(counts.values())
        detail = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "nothing due"
        self.stdout.write(f"Sent {total} email(s): {detail}")
