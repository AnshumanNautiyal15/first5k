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
```

After changing Tailwind classes in templates or JS, run `make css` and commit `static/css/app.css`; production never runs the CLI.

## Architecture

- `plans/engine.py` is the pure-Python progression engine (no Django imports). Levels are a data list (`LEVELS`); starting level, next level after feedback, gap rules, unlock timing, milestones and progress hints are plain functions. Change training rules here, as data where possible, and cover them in `tests/test_engine.py`. Block layout (`("run", "rest")`) is configurable per level via `BLOCK_LAYOUT_OVERRIDES`.
- DB orchestration that applies engine rules belongs in `plans/services.py`, not in views. All progression is decided server-side; JS only calls endpoints.
- Onboarding answers live in the anonymous session (`plans/onboarding.py`, key `"onboarding"`) until the user verifies a magic link. Each onboarding run also creates an `OnboardingStart` row for the admin funnel.
- Apps: `core` (landing, legal, stats), `accounts` (custom passwordless `User` with email as username; only staff have passwords, for /admin), `plans` (journey/blocks/onboarding), `notifications` (emails, `EmailLog`, scheduled-email command).
- Settings are a single env-driven `first5k/settings.py` (django-environ, `.env` locally; see `.env.example`). An empty `DATABASE_URL` falls back to SQLite. `BLOCK_MIN_GAP_DAYS` and `SITE_URL` are product settings.
- `tests/conftest.py` forces non-manifest static storage, no SSL redirect and the locmem email backend, so tests pass whatever `DEBUG` is.

## Conventions

- Copy tone: warm, encouraging, no jargon, never guilt or judgment, no streaks. Skipping or coming back late is never failure. Run days always include the talk test and "walking is always allowed"; the safety note is `templates/partials/safety_note.html`.
- Frontend: server-rendered templates, vanilla JS modules in `static/js` (no frameworks, no JS build step). Every action must also work as a plain form POST without JS. Mobile-first, 48px minimum tap targets, 18px base text, `prefers-reduced-motion` respected.
- Brand colours are named in `tailwind.config.js` (`cream`, `ink`, `muted`, `accent`, `leaf`, `sand`); use those, not raw palette colours. Shared component classes (`.card`, `.btn-primary`, `.option`, `.tip`) live in `static/src/input.css`.
