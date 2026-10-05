"""Signed, login-free unsubscribe tokens."""

from django.contrib.auth import get_user_model
from django.core import signing
from django.urls import reverse

SALT = "first5k.unsubscribe"


def make_token(user) -> str:
    return signing.dumps(user.pk, salt=SALT, compress=True)


def user_for_token(token: str):
    try:
        pk = signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None
    return get_user_model().objects.filter(pk=pk).first()


def unsubscribe_path(user) -> str:
    return reverse("notifications:unsubscribe", args=[make_token(user)])
