# First5K

Your first 5K, 2 days at a time. A small Django app that gives total beginners only their next 2 days of running, adapted to how the last 2 felt.

Django 5.2 · Python 3.11 · vanilla JS · Tailwind (standalone CLI) · SQLite locally, Postgres in production.

## Local setup

```bash
make install            # creates .venv and installs requirements-dev.txt
cp .env.example .env    # then set SECRET_KEY (and SITE_URL if not on port 8000)
make migrate
make css                # first run downloads the Tailwind v3 standalone CLI into bin/
make run                # http://localhost:8000
```

Logging in locally: emails print to the runserver console, so copy the `/auth/verify/…` link from there.

### Demo data

```bash
.venv/bin/python manage.py seed_demo
```

This creates 7 demo users at different stages (new, mid-plan, waiting for unlock, next block ready, halfway, back after 8 days away, finished) and prints a one-time login link for each. It only runs when `DEBUG=True`. Re-run it for fresh links. On `/today/`, `?skip_wait=1` unlocks the next block immediately (DEBUG only). In the admin, the Blocks "Unlock now" action does the same.

Admin: `.venv/bin/python manage.py createsuperuser`, then `/admin/`. The funnel is at `/admin/stats/`.

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `DEBUG` | `False` | `True` locally only |
| `SECRET_KEY` | none | required when `DEBUG=False` |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | comma-separated |
| `CSRF_TRUSTED_ORIGINS` | empty | e.g. `https://first5k.app` |
| `SITE_URL` | `http://localhost:8000` | used in email links, share cards, OG tags |
| `DATABASE_URL` | SQLite file | e.g. `postgres://user:pass@host:5432/db` |
| `EMAIL_BACKEND` | console if DEBUG, else SMTP | |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | port 587, TLS on | any SMTP provider (Resend, Postmark, Brevo…) |
| `DEFAULT_FROM_EMAIL` | `First5K <hello@localhost>` | |
| `BLOCK_MIN_GAP_DAYS` | `2` | minimum days between block starts (55+ and under-18 get 3) |
| `PLAUSIBLE_DOMAIN` | empty | set to enable Plausible analytics |
| `CONTACT_EMAIL`, `OPERATOR_NAME` | placeholders | shown on privacy/terms pages |
| `SECURE_SSL_REDIRECT` | `True` | only applies when `DEBUG=False` |

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

Scheduled emails (next block ready, gentle nudge, final "door's open", weekly progress) are sent by:

```bash
.venv/bin/python manage.py send_scheduled_emails
```

It is idempotent (every send is recorded in `EmailLog`). It only emails people between 08:00 and 20:00 in their own timezone, and it also deletes login-link records older than 30 days. Run it **hourly**:

```cron
0 * * * * cd /path/to/app && .venv/bin/python manage.py send_scheduled_emails >> /var/log/first5k-email.log 2>&1
```

Every non-login email has a one-click unsubscribe link and `List-Unsubscribe` headers. Login links are always sent.

## Deployment

Every host needs the same four things:

1. **Build:** `pip install -r requirements.txt && python manage.py collectstatic --noinput`
2. **Release:** `python manage.py migrate --noinput`
3. **Web:** `gunicorn first5k.wsgi --workers 2 --bind 0.0.0.0:$PORT` (see `Procfile`)
4. **Hourly cron:** `python manage.py send_scheduled_emails`

Set `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SITE_URL`, `DATABASE_URL` and the `EMAIL_*` variables. Run `python manage.py check --deploy` to confirm. Static files are served by WhiteNoise with hashed, long-cached filenames.

- **Render (recommended):** `render.yaml` is a Blueprint (web service, hourly cron job, Postgres and a shared settings group). **Step-by-step guide: [docs/deploy-render.md](docs/deploy-render.md).**
- **Railway:** add a Postgres plugin and deploy the repo. The `Procfile` provides `web` and `release`. Set the build command above, and add a second service using the same repo with a cron schedule `0 * * * *` running `python manage.py send_scheduled_emails`.
- **Fly.io:** `fly launch` (choose Postgres), set secrets with `fly secrets set`, use `release_command = "python manage.py migrate --noinput"` in `fly.toml`, and run the email command hourly with a scheduled Machine (`fly machine run . --schedule hourly --command "python manage.py send_scheduled_emails"`).

After the first deploy, create an admin: `python manage.py createsuperuser`.
