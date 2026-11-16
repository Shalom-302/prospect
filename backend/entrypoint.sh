#!/bin/sh
# api    : applique les migrations Alembic puis lance l'API
# worker : worker Celery + beat (recherches du matin, file d'envoi, lecture IMAP)
set -e
case "$1" in
  api)
    alembic upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"
    ;;
  worker)
    exec celery -A app.worker worker -B --loglevel=info --concurrency=1 -s /tmp/celerybeat-schedule
    ;;
  *)
    exec "$@"
    ;;
esac
