release: python manage.py migrate --noinput
web: gunicorn first5k.wsgi --workers ${WEB_CONCURRENCY:-2} --bind 0.0.0.0:${PORT:-8000} --access-logfile - --log-file -
