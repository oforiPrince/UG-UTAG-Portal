# Docker Deployment Guide

This document outlines how to deploy the UTAG UG portal using Docker on two separate hosts:

- **Application server** – runs Django (Gunicorn), Celery worker/beat, and Redis.
- **Database server** – runs PostgreSQL with persistent storage.

Follow the steps in order so that the database is available before the web stack is started.

## 1. Prerequisites

- Docker Engine 24+ and Docker Compose Plugin v2 installed on both hosts.
- A private network or VPN between both machines. The application server must be able to reach the database server on port `5432`.
- A domain name (or public IP) ready for the web server.
- SMTP credentials for email delivery.
- Optional: object storage or mounted volume if you want media files stored outside the container host.

## 2. Prepare Secrets

From the project root, copy the production sample env file and populate it with strong values:

```sh
cp .env.production.sample .env
cp .env.db.example .env.db
```

> For local development, you can instead copy `.env.local.sample` to `.env` and adjust values as needed.

Recommended values:

- `DJANGO_SECRET_KEY`: long random string (keep private).
- `DJANGO_DEBUG`: `0` for production.
- `DJANGO_ALLOWED_HOSTS`: comma-separated list of domains/IPs that may serve the site.
- `DATABASE_URL`: point to the Postgres host, e.g. `postgres://db_user:super-secret@10.0.0.5:5432/app_database`.
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`: leave as-is for internal Redis usage.
- Email fields: match your SMTP provider.
- Reverse proxy values: `NGINX_SERVER_NAME` (public domain), `CERTBOT_EMAIL` (LetsEncrypt contact), `WEB_SERVICE_HOST=web`, `WEB_SERVICE_PORT=8000`.
- `.env.db`: choose the database name, user, and password you will reference in `DATABASE_URL`.

> **Tip:** Store final environment files in a secure secret manager instead of source control.

## 3. Deploy the Database Server

1. Copy the following files to the database host:
   - `docker-compose.db.yml`
   - `.env.db`

2. On the database host, start the Postgres container (the compose file enforces SCRAM authentication and UTF-8 locales by default):

   ```sh
   docker compose --env-file .env.db -f docker-compose.db.yml up -d
   ```

3. Confirm Postgres is healthy:

   ```sh
   docker compose -f docker-compose.db.yml ps
   docker logs postgres_db_1   # container name may differ
   ```

4. Configure host-level firewall rules so that only the application server IP can reach port `5432`.

5. (Optional) Schedule regular volume snapshots or logical dumps from `postgres_data`.

## 4. Deploy the Application Server

1. Copy the full repository (or a release bundle) to the application host.
2. Ensure `.env` is present and that `DATABASE_URL` references the database host IP or DNS name.
3. Start the web stack (application services only):

   ```sh
   docker compose --env-file .env -f docker-compose.app.yml up -d --build
   ```

4. Check that all services are healthy:

   ```sh
   docker compose -f docker-compose.app.yml ps
   docker compose -f docker-compose.app.yml logs web
   ```

5. The web service listens on `WEB_PORT` (defaults to `8000`). Configure a reverse proxy (e.g. Nginx or Caddy) and TLS termination in front of the container.

6. Static files are collected into the `static_volume` volume. Media uploads persist in `media_volume`. Back up both volumes or mount them to durable storage.

## 5. Add the Reverse Proxy and TLS (optional but recommended)

> Requires DNS for `NGINX_SERVER_NAME` pointing at the application host and inbound ports `80`/`443` open.

1. Launch the proxy alongside the app stack:

   ```sh
   docker compose --env-file .env -f docker-compose.app.yml -f docker-compose.proxy.yml up -d nginx
   ```

   This publishes ports `80` and `443` and forwards traffic to the `web` service. A self-signed certificate is generated automatically until Let’s Encrypt issues the real one.

2. Obtain the initial certificate (replace domain/email if not using `.env` values):

   ```sh
   docker compose --env-file .env -f docker-compose.app.yml -f docker-compose.proxy.yml run --rm \
     certbot certonly --webroot -w /var/www/certbot \
     --email "$CERTBOT_EMAIL" --agree-tos --no-eff-email \
     -d "$NGINX_SERVER_NAME"
   ```

   After success, reload Nginx so it picks up the new certificate:

   ```sh
   docker compose -f docker-compose.app.yml -f docker-compose.proxy.yml exec nginx nginx -s reload
   ```

3. Enable automated renewals (optional):

   ```sh
   docker compose --env-file .env -f docker-compose.app.yml -f docker-compose.proxy.yml up -d --profile certbot certbot
   ```

   The certbot service will attempt renewal every `CERTBOT_RENEW_INTERVAL` seconds (default 12 hours). Schedule a monthly reload (cron) or periodically run `docker compose ... exec nginx nginx -s reload` so renewed certificates take effect.

## 6. Management Commands

- Apply migrations or create superusers via `docker compose run`:

  ```sh
  docker compose --env-file .env -f docker-compose.app.yml run --rm web python manage.py createsuperuser
  ```

- Tail logs for troubleshooting:

  ```sh
  docker compose -f docker-compose.app.yml logs -f web
  docker compose -f docker-compose.app.yml logs -f worker
  ```

- Update to a new release:
  1. Pull latest code on the application host.
  2. Rebuild and restart: `docker compose --env-file .env -f docker-compose.app.yml up -d --build`.

## 7. Operational Notes

- Set `RUN_MIGRATIONS=0` and `RUN_COLLECTSTATIC=0` for non-web services (already applied in `docker-compose.app.yml`).
- Use managed backups or scheduled `pg_dump` of the `postgres_data` volume.
- Monitor resource usage; adjust container CPU/memory limits if needed.
- For high availability, consider managed services for Postgres and Redis.

With both servers configured, the application should run using PostgreSQL on the dedicated database host and Django/Celery/Redis on the web host.
