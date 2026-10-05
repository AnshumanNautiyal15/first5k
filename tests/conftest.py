import pytest


@pytest.fixture(autouse=True)
def _test_settings(settings):
    # Tests run over plain HTTP without collectstatic, whatever the env says.
    settings.SECURE_SSL_REDIRECT = False
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
