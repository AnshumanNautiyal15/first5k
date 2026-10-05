# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

First5K: a Django web app that gets total beginners to their first 5K by showing only the next 2-day "block" at a time, adapting each new block to feedback. Built in phases (see git log); scope and out-of-scope list were set by the product brief: no payments, social, GPS, wearables, AI plans, native apps, i18n or push.

## Commands

```bash
make install          # .venv + requirements-dev.txt (Python 3.11)
make migrate
make run              # runserver; .claude/launch.json uses port 8001 (8000 is taken by another local project)
make test             # pytest (pytest-django, settings in pytest.ini)
.venv/bin/pytest tests/test_engine.py::test_too_hard_twice_goes_down_one   # single test
make css              # build static/css/app.css with the Tailwind v3 standalone CLI in bin/ (auto-downloaded)
make css-watch
.venv/bin/python manage.py send_scheduled_emails   # hourly via cron in production
```

After changing Tailwind classes in templates or JS, run `make css` and commit `static/css/app.css`; production never runs the CLI.

## Architecture

- `plans/engine.py` is the pure-Python progression engine (no Django imports). Levels are a data list (`LEVELS`); starting level, next level after feedback, gap rules, unlock timing, milestones and progress hints are plain functions. Change training rules here, as data where possible, and cover them in `tests/test_engine.py`. Block layout (`("run", "rest")`) is configurable per level via `BLOCK_LAYOUT_OVERRIDES`. Age groups (onboarding Q3) adjust the rules through `AGE_RULES` (start cap, max jump, min gap, earlier step-down). Gender is deliberately not collected.
- DB orchestration that applies engine rules belongs in `plans/services.py`, not in views. Compliments come from `plans/messages.py` (grouped, keyed `group:index`, never repeating `Journey.last_message_key`). All progression is decided server-side; JS only calls endpoints.
- Block lifecycle: `services.submit_feedback` closes the active block and creates the next one **locked** with `unlocks_at`; `services.refresh` (called on every `/today/` load) unlocks due blocks and applies gap rules, measured from `max(last_activity_at, unlocks_at)`. There is no background job; unlocking happens lazily on the next visit. `last_activity_at` only changes on real activity (completing a day or giving feedback), never on page views. `?skip_wait=1` (only when DEBUG is on) and the admin "Unlock now" action bypass the wait for testing.
- Run-day teaching and food content is pure data in `plans/learn.py` (a "Running word" per level; terms are always explained in plain language) and `plans/fuel.py` (optional ideas; keep the note about not needing fuel for easy runs). The progress chart is server-rendered SVG: geometry in `plans/charts.py`, markup in `templates/plans/_bar_chart.html`.
- Onboarding answers live in the anonymous session (`plans/onboarding.py`, key `"onboarding"`) until the user verifies a magic link. Each onboarding run also creates an `OnboardingStart` row for the admin funnel.
- Apps: `core` (landing, legal, stats), `accounts` (custom passwordless `User` with email as username; only staff have passwords, for /admin), `plans` (journey/blocks/onboarding), `notifications` (emails, `EmailLog`, scheduled-email command).
- Settings are a single env-driven `first5k/settings.py` (django-environ, `.env` locally; see `.env.example`). An empty `DATABASE_URL` falls back to SQLite. `BLOCK_MIN_GAP_DAYS` and `SITE_URL` are product settings.
- Auth (`accounts/magic_link.py`): only the SHA-256 of a token is stored; users are created on first *verified* login, not when the email is entered. `/auth/verify/<token>/` GET only shows a confirm button and POST redeems it, because mail scanners prefetch links. Onboarding answers are copied onto the token so opening the link in a different browser still works.
- Interactive endpoints (e.g. `plans:complete_day`) return JSON when the request sends `Accept: application/json` (see `static/js/api.js`), otherwise they redirect with a flash message (the no-JS fallback).
- Never name a template context variable `block`: Django reserves it inside `{% block %}` tags. Views pass the current block as `current`.
- Emails: `notifications/email.send_to_user` claims an `EmailLog` row (unique per user/kind/ref) *before* sending and deletes it if sending fails. That is what makes the hourly `send_scheduled_emails` command idempotent. Which email is due is decided in `notifications/scheduler.py` (local 08–20 window, 20h minimum spacing, "door's open" makes a user dormant until their next activity). Email charts are HTML table cells, never SVG or JS. Magic-link emails are transactional: never logged and sent even to unsubscribed users.
- `tests/conftest.py` forces non-manifest static storage, no SSL redirect and the locmem email backend, so tests pass whatever `DEBUG` is.

## Conventions

- Copy tone: warm, encouraging, no unexplained jargon, never guilt or judgment, no streaks. Skipping or coming back late is never failure. Run days always include the talk test and "walking is always allowed"; the safety note is `templates/partials/safety_note.html`.
- Frontend: server-rendered templates, vanilla JS modules in `static/js` (no frameworks, no JS build step). Every action must also work as a plain form POST without JS. Mobile-first, 48px minimum tap targets, 18px base text, `prefers-reduced-motion` respected.
- Brand colours are named in `tailwind.config.js` (`cream`, `ink`, `muted`, `accent`, `leaf`, `sand`); use those, not raw palette colours. Shared component classes (`.card`, `.btn-primary`, `.option`, `.tip`) live in `static/src/input.css`.
