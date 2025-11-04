FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create a non-root user to run the application
RUN addgroup --system app \
    && adduser --system --ingroup app --home /home/app app \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R app:app /app /app/staticfiles /app/media /entrypoint.sh

ENV DJANGO_SETTINGS_MODULE=utag_ug_archiver.settings

EXPOSE 8000

# USER app  # Removed to allow entrypoint to chown volumes as root before switching to app

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "utag_ug_archiver.wsgi:application", "--bind", "0.0.0.0:8000"]
