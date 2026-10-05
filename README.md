# First5K

Your first 5K, 2 days at a time. A small Django app that gives total beginners only their next 2 days of running, adapted to how the last 2 felt.

## Local setup

Requires Python 3.11+.

```bash
make install            # creates .venv and installs requirements-dev.txt
cp .env.example .env    # then set SECRET_KEY
make migrate
make css                # first run downloads the Tailwind v3 standalone CLI into bin/
make run
```

## CSS

Tailwind v3 via the standalone CLI (no Node). Source: `static/src/input.css`, config: `tailwind.config.js`.
`make css` builds the minified `static/css/app.css`, which is committed so deploys don't need the CLI.
`make css-watch` rebuilds on change. Rebuild and commit after changing templates or classes.

## Tests

```bash
make test                                   # whole suite
.venv/bin/pytest tests/test_engine.py       # one file
.venv/bin/pytest -k too_hard                # by name
```

## Emails

In development (`DEBUG=True`, empty `EMAIL_BACKEND`) emails print to the runserver console, including login links.
In production set the `EMAIL_*` variables in `.env.example` to any SMTP provider (Resend, Postmark, Brevo…).

Scheduled emails (next block ready, gentle nudge, final "door's open", weekly progress) are sent by:

```bash
.venv/bin/python manage.py send_scheduled_emails
```

It is idempotent (every send is recorded in `EmailLog`) and only emails people between 08:00 and 20:00 in their own timezone, so run it **hourly**:

```cron
0 * * * * cd /path/to/app && .venv/bin/python manage.py send_scheduled_emails >> /var/log/first5k-email.log 2>&1
```

Every non-login email has a one-click unsubscribe link and `List-Unsubscribe` headers. Login links are always sent.

_Deployment notes are added in Phase 5._
