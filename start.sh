#!/usr/bin/env bash
set -o errexit

python manage.py migrate --noinput
python manage.py collectstatic --noinput

gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers 4
