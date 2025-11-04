#!/bin/sh
set -e

# If running as root (during some builds or manual runs), ensure directories are writable
if [ "$(id -u)" = "0" ]; then
    # chown /app and static/media so the unprivileged user can write
    if [ -d /app ]; then
        chown -R app:app /app || true
    fi
    if [ -d /app/staticfiles ]; then
        chown -R app:app /app/staticfiles || true
    fi
    if [ -d /app/media ]; then
        chown -R app:app /app/media || true
    fi
fi

# Run migrations and collectstatic. These will run as the current user (container will usually run as 'app').
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    python manage.py migrate --noinput
fi

if [ "${RUN_COLLECTSTATIC:-1}" = "1" ]; then
    python manage.py collectstatic --noinput
fi

exec "$@"
