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

_More (env vars, emails, deployment) is added in later phases._
