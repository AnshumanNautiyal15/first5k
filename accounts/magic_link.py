"""Passwordless login: issue, rate-limit and redeem magic links."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import MagicLoginToken

TOKEN_TTL = timedelta(minutes=15)
RATE_LIMIT = 5
RATE_WINDOW = timedelta(hours=1)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_rate_limited(email: str, ip: str | None, now=None) -> bool:
    now = now or timezone.now()
    since = now - RATE_WINDOW
    recent = MagicLoginToken.objects.filter(created_at__gte=since)
    if recent.filter(email=email).count() >= RATE_LIMIT:
        return True
    if ip and recent.filter(ip=ip).count() >= RATE_LIMIT:
        return True
    return False


def issue_token(email: str, ip: str | None, onboarding: dict | None = None) -> str:
    """Create a token row and return the raw token (never stored)."""
    raw = secrets.token_urlsafe(32)
    MagicLoginToken.objects.create(
        email=email,
        token_hash=hash_token(raw),
        ip=ip,
        onboarding=onboarding or {},
        expires_at=timezone.now() + TOKEN_TTL,
    )
    return raw


def verify_path(raw: str) -> str:
    return reverse("accounts:verify", args=[raw])


@dataclass
class Redeemed:
    user: object
    created: bool
    onboarding: dict


def find_valid(raw: str, now=None) -> MagicLoginToken | None:
    now = now or timezone.now()
    return MagicLoginToken.objects.filter(
        token_hash=hash_token(raw), used_at__isnull=True, expires_at__gt=now
    ).first()


def redeem(raw: str) -> Redeemed | None:
    """Mark the token used and return (or create) its user. None if invalid/expired/used."""
    User = get_user_model()
    now = timezone.now()
    with transaction.atomic():
        # Conditional update makes redemption single-use even under concurrent requests.
        token = find_valid(raw, now)
        if token is None:
            return None
        claimed = MagicLoginToken.objects.filter(pk=token.pk, used_at__isnull=True).update(used_at=now)
        if not claimed:
            return None
        user, created = User.objects.get_or_create(email=token.email, defaults={})
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        # Any other outstanding links for this email are now pointless.
        MagicLoginToken.objects.filter(Q(email=token.email) & Q(used_at__isnull=True)).update(used_at=now)
    return Redeemed(user=user, created=created, onboarding=token.onboarding)
