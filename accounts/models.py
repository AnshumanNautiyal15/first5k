from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone as dj_timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        # Admins are the only accounts with a password (for /admin/).
        user = self.model(email=self.normalize_email(email).lower(), is_staff=True, is_superuser=True, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """Passwordless user identified by email. Logs in via magic link."""

    email = models.EmailField(unique=True)
    is_subscribed = models.BooleanField(default=True)
    timezone = models.CharField(max_length=64, default=settings.DEFAULT_USER_TIMEZONE)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=dj_timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class MagicLoginToken(models.Model):
    """
    A single-use, short-lived login link. Only the SHA-256 hash of the token is stored.
    Onboarding answers ride along so they survive opening the link in another browser.
    """

    email = models.EmailField(db_index=True)
    token_hash = models.CharField(max_length=64, unique=True)
    ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    onboarding = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=dj_timezone.now, db_index=True)

    def __str__(self):
        return f"Login link for {self.email} ({self.created_at:%Y-%m-%d %H:%M})"
