# Development Docker workflow

This repo ships with a production-oriented Compose file (`docker-compose.app.yml`).

That file:
- builds an image containing the code (no bind-mount)
- runs Gunicorn
- is great for “deploy-like” runs

…but it makes **development tasks** like `makemigrations` confusing, because migration files created inside the container are lost when you use `docker compose run --rm ...`.

## ✅ Recommended: use the dev overlay

A dev overlay is provided in `docker-compose.dev.yml`. It:
- bind-mounts the repo into `/app` so changes + migrations persist
- runs Django `runserver`
- keeps the DB/Redis from the app compose

### Start dev stack

```bash
docker compose -f docker-compose.app.yml -f docker-compose.dev.yml up --build
```

### Make migrations (they will be written to your host filesystem)

```bash
docker compose -f docker-compose.app.yml -f docker-compose.dev.yml run --rm web python manage.py makemigrations
```

### Apply migrations

```bash
docker compose -f docker-compose.app.yml -f docker-compose.dev.yml run --rm web python manage.py migrate
```

## Production-like run (no bind mount)

```bash
docker compose -f docker-compose.app.yml up --build -d
```

In this mode, if you change code you must rebuild:

```bash
docker compose -f docker-compose.app.yml build web worker beat
```
