# Deploying First5K on Render

This guide takes the app from your laptop to a live URL on [Render](https://render.com). The repo includes a **Blueprint** (`render.yaml`) that creates everything in one go:

| Resource | Name | What it does |
|---|---|---|
| Web service | `first5k` | Runs the site with gunicorn |
| Cron job | `first5k-emails` | Runs `send_scheduled_emails` every hour |
| Postgres | `first5k-db` | The database |
| Environment group | `first5k-settings` | Settings shared by the web service and the cron job |

Everything is placed in the **Singapore** region, which is closest to users in India. Change `region:` in `render.yaml` if your users are elsewhere.

> **Cost:** the Blueprint uses Render's paid **starter** plan for the web service and cron job, and the **free** Postgres plan. Free web services go to sleep when idle and don't support the pre-deploy migration step. Free databases expire, so upgrade the database before real users sign up. Check [render.com/pricing](https://render.com/pricing) for current prices.

---

## 1. Before you start

You need:

- A **GitHub** (or GitLab) account
- A **Render** account (sign up with GitHub to make step 3 easier)
- An **email provider** with SMTP access, e.g. [Resend](https://resend.com), [Brevo](https://www.brevo.com) or [Postmark](https://postmarkapp.com). Login links are sent by email, so the app doesn't work without one.
- Optional: your own **domain** (e.g. `yourdomain.com`)

Make sure the compiled CSS is up to date and the tests pass:

```bash
make css
```

```bash
make test
```

## 2. Push the code to GitHub

Create an **empty private** repository on GitHub (no README or .gitignore, since the project already has them), then:

```bash
git remote add origin https://github.com/YOUR-USERNAME/first5k.git
```

```bash
git push -u origin main
```

If your branch is called `master`, push that instead (`git branch` shows it).

`.gitignore` keeps your `.env`, local database, virtualenv and the Tailwind binary out of the repo. Before pushing, double-check that `git status` doesn't list `.env`.

## 3. Create the Blueprint on Render

1. In the Render dashboard, click **New → Blueprint**.
2. Connect your GitHub account if asked, and pick the `first5k` repository.
3. Render reads `render.yaml` and shows the web service, cron job, database and environment group it will create.
4. It then asks for every value marked `sync: false`. Fill them in as described below.
5. Click **Apply**. The first build takes a few minutes.

### Values to fill in

| Key | Example | Notes |
|---|---|---|
| `SITE_URL` | `https://first5k.onrender.com` | The public address, **no trailing slash**. Used in every email link. If you don't know the onrender.com name yet, enter your best guess and fix it after the first deploy (step 5). |
| `ALLOWED_HOSTS` | `yourdomain.com,www.yourdomain.com` | Only needed for a custom domain. The `*.onrender.com` hostname is trusted automatically. Leave empty otherwise. |
| `CSRF_TRUSTED_ORIGINS` | `https://yourdomain.com,https://www.yourdomain.com` | Same as above, with `https://`. Leave empty if you only use onrender.com. |
| `EMAIL_HOST` | `smtp.resend.com` / `smtp-relay.brevo.com` / `smtp.postmarkapp.com` | From your email provider's SMTP settings |
| `EMAIL_HOST_USER` | `resend` (Resend) or your SMTP login | |
| `EMAIL_HOST_PASSWORD` | your SMTP password / API key | Keep it secret. Never commit it. |
| `DEFAULT_FROM_EMAIL` | `First5K <hello@yourdomain.com>` | Must be an address on a domain verified with your email provider |
| `CONTACT_EMAIL` | `hello@yourdomain.com` | Shown on the privacy and terms pages |
| `OPERATOR_NAME` | your name or company | Shown on the privacy and terms pages |
| `PLAUSIBLE_DOMAIN` | `yourdomain.com` | Optional analytics. Leave empty to disable. |

You don't need to set these, because the Blueprint handles them:

- **`SECRET_KEY`:** generated once in the shared group, so the web service and cron job get the same value. They must match, otherwise unsubscribe links in emails stop working.
- **`DATABASE_URL`:** wired automatically from the Postgres database.
- **`DEBUG`:** set to `False`.
- **`PYTHON_VERSION`:** 3.11.6.
- **`EMAIL_PORT`:** 587.

You can change any of them later under **Dashboard → Env Groups → first5k-settings**. Saving there redeploys both services.

## 4. What happens on each deploy

For the web service:

1. **Build:** `pip install -r requirements.txt && python manage.py collectstatic --noinput`
2. **Pre-deploy:** `python manage.py migrate --noinput` (database migrations run before the new version goes live)
3. **Start:** `gunicorn first5k.wsgi --workers 2 --bind 0.0.0.0:$PORT`
4. **Health check:** Render requests `/robots.txt` and only switches traffic over once it responds

Every push to the connected branch deploys automatically.

The CSS isn't built on Render. `static/css/app.css` is committed, so **run `make css` and commit the result** whenever you change templates or Tailwind classes.

## 5. After the first deploy

### Check the address
Open the web service in the dashboard and copy its URL (e.g. `https://first5k.onrender.com`). If it differs from what you entered for `SITE_URL`, update `SITE_URL` in the **first5k-settings** group.

### Create your admin account
Open the **first5k** web service → **Shell** tab, then run:

```bash
python manage.py createsuperuser
```

Log in at `https://YOUR-SITE/admin/`. The funnel stats are at `/admin/stats/`.

### Send a test email
In the same Shell:

```bash
python manage.py sendtestemail you@example.com
```

If it doesn't arrive, see Troubleshooting below.

### Run the security check
```bash
python manage.py check --deploy
```

It should report no issues.

### Try the real flow
On your phone, go through the landing page → 3 questions → enter your email → tap the link in the email → mark a day complete.

## 6. Email deliverability (important)

Login links are useless if they land in spam. With your email provider:

1. **Verify your sending domain**, then add the **SPF** and **DKIM** DNS records they give you at your domain registrar.
2. Add a **DMARC** record, e.g. `v=DMARC1; p=none; rua=mailto:you@yourdomain.com`.
3. Use a `DEFAULT_FROM_EMAIL` on that verified domain.

The app already sends `List-Unsubscribe` and one-click unsubscribe headers, which Gmail and Yahoo require for bulk senders.

## 7. Custom domain (optional)

1. Web service → **Settings → Custom Domains → Add**, e.g. `yourdomain.com` and `www.yourdomain.com`.
2. Add the DNS records Render shows you. HTTPS certificates are issued automatically.
3. In the **first5k-settings** group, update:
   - `SITE_URL` = `https://yourdomain.com`
   - `ALLOWED_HOSTS` = `yourdomain.com,www.yourdomain.com`
   - `CSRF_TRUSTED_ORIGINS` = `https://yourdomain.com,https://www.yourdomain.com`

## 8. The hourly email job

The `first5k-emails` cron job runs every hour (`0 * * * *`, UTC). Each run:

- sends any due emails: next block ready, gentle nudge, "we'll leave the door open", and weekly progress
- only emails people between 08:00 and 20:00 in **their own** timezone
- never sends the same email twice, because every send is recorded in `EmailLog`
- deletes login-link records older than 30 days

Check it under **first5k-emails → Logs**. Each run prints a line like `Sent 3 email(s): next_block=2, nudge=1`, and **Trigger Run** runs it immediately. Sent emails are listed in the admin under **Email logs**.

## 9. Backups and upgrades

- **Upgrade the database** to a paid Postgres plan before launch. Free databases expire and have no backups.
- Paid Postgres plans include automatic backups. You can also take a manual export:
  ```bash
  pg_dump "$DATABASE_URL" > first5k-backup.sql
  ```
  Run it from the web service Shell, or locally with the database's **External Database URL**.
- To scale up, change the plan, or raise `--workers` in `render.yaml`. About 2 workers per CPU is a reasonable start.

## 10. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| **Bad Request (400)** | The hostname isn't trusted. Add your custom domain to `ALLOWED_HOSTS`. Logs show `DisallowedHost`. |
| **403 CSRF verification failed** on forms | Add `https://yourdomain.com` to `CSRF_TRUSTED_ORIGINS`. |
| Pages load **without styling** | Make sure `static/css/app.css` is committed and the build ran `collectstatic` (check the build log). |
| **Deploy fails at pre-deploy** | A migration failed. Read the deploy log. Note that `preDeployCommand` needs a paid instance type. |
| **Emails never arrive** | Run `python manage.py sendtestemail` in the Shell and read the error. Check `EMAIL_HOST`, user, password and port 587, and that `DEFAULT_FROM_EMAIL` uses a verified domain. |
| Emails land in **spam** | Finish SPF, DKIM and DMARC (section 6). |
| Email links point to the **wrong address** | Fix `SITE_URL` (no trailing slash). |
| **Unsubscribe links say "That link doesn't work"** | The web service and cron job have different `SECRET_KEY`s. Keep `SECRET_KEY` only in the shared **first5k-settings** group, never per service. |
| Users were **logged out** after a change | `SECRET_KEY` changed. Avoid regenerating it. |
| Health check fails | Open `/robots.txt` in a browser. It should return plain text. Check the logs for errors on startup. |

## Quick reference

| Task | Where / command |
|---|---|
| Logs | Dashboard → service → **Logs** |
| Run a command in production | Web service → **Shell** |
| Change settings | **Env Groups → first5k-settings** (redeploys both services) |
| Run the email job now | **first5k-emails → Trigger Run** |
| Deploy | `git push` to the connected branch |
| Roll back | Web service → **Events** → pick an earlier deploy → **Rollback** |
