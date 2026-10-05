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
