"""Account self-service: data export and deletion."""

from django.db import transaction

from .models import MagicLoginToken


def export_data(user) -> dict:
    data = {
        "account": {
            "email": user.email,
            "created_at": user.created_at.isoformat(),
            "timezone": user.timezone,
            "is_subscribed": user.is_subscribed,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        },
        "journey": None,
        "emails_sent": [
            {"kind": e.kind, "sent_at": e.sent_at.isoformat()} for e in user.email_logs.order_by("sent_at")
        ],
    }
    journey = getattr(user, "journey", None)
    if journey:
        data["journey"] = {
            "start_activity": journey.start_activity,
            "start_jog_ability": journey.start_jog_ability,
            "age_group": journey.age_group,
            "current_level": journey.current_level,
            "blocks_completed": journey.blocks_completed,
            "created_at": journey.created_at.isoformat(),
            "completed_at": journey.completed_at.isoformat() if journey.completed_at else None,
            "blocks": [
                {
                    "index": b.index,
                    "level": b.level,
                    "status": b.status,
                    "feedback": b.feedback,
                    "unlocks_at": b.unlocks_at.isoformat(),
                    "started_at": b.started_at.isoformat() if b.started_at else None,
                    "completed_at": b.completed_at.isoformat() if b.completed_at else None,
                    "days": [
                        {"day": d.day_number, "kind": d.kind,
                         "completed_at": d.completed_at.isoformat() if d.completed_at else None}
                        for d in b.days.all()
                    ],
                }
                for b in journey.blocks.prefetch_related("days")
            ],
            "milestones": [{"key": m.key, "achieved_at": m.achieved_at.isoformat()} for m in journey.milestones.all()],
        }
    return data


@transaction.atomic
def delete_account(user) -> None:
    """Delete the user and everything tied to them. Funnel rows keep only anonymous answers."""
    MagicLoginToken.objects.filter(email=user.email).delete()
    user.delete()  # cascades: journey, blocks, days, milestones, email logs
