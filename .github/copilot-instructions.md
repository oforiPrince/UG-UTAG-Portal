# UTAG-UG Archiver: Copilot Instructions

## Project Overview
UTAG-UG Archiver is a Django 4.2 web application for managing university events, documents, and communications. It uses **Django Channels** for WebSocket chat, **Celery** with Redis for async tasks, and **PostgreSQL** for data persistence.

## Architecture & Key Components

### Core Structure
- **Root app**: `utag_ug_archiver/` (Django project settings)
- **Key apps**: accounts (auth), dashboard (events), chat (WebSocket), adverts (announcements), gallery (media), website (frontend)
- **Custom user model**: `accounts.User` extending `AbstractBaseUser` with academic hierarchy (School → College → Department)

### Critical Integration Points

**Chat System (Real-time)**
- WebSocket consumers: `chat/consumers.py` → `ThreadChatConsumer`, `GroupChatConsumer`
- Routes: `chat/routing.py` defines `ws/chat/thread/<id>/` and `ws/chat/group/<id>/` endpoints
- Security pattern: ALL WebSocket connections validate user participation before connection (see `get_thread_and_validate_access()`)
- Message encryption: Uses `cryptography.fernet` for end-to-end encryption

**Async Tasks (Celery)**
- Task files: `accounts/tasks.py`, `dashboard/tasks.py`, `dashboard/tasks_bulk_import.py`
- Critical tasks: `update_event_statuses()`, `update_advert_statuses()` (scheduled via django-celery-beat)
- Email retry pattern: Uses `tenacity` with exponential backoff (see `accounts/signals.py:send_email_with_retry`)
- **Note**: Email credential sending is DISABLED; users authenticate with `staff_id` as temporary password

**Database Signals**
- User creation triggers in `accounts/signals.py` (password generation, email queuing - currently disabled)
- Password stored using Django's `make_password()` (don't hash manually)

### Data Flow
1. **User auth**: Custom User model validates via `accounts.managers.UserManager`
2. **Chat**: WebSocket → AsyncWebsocketConsumer → `database_sync_to_async` helpers → Models
3. **Events**: Admin creates → Celery task periodically updates status (upcoming→ongoing→completed)
4. **Bulk import**: Dashboard → `import_members_from_upload` Celery task → CSV processing

## Development Workflow

### Local Setup (Docker-based - recommended)
```bash
# Start full dev stack with bind-mount (code persists, migrations written to host)
docker compose -f docker-compose.app.yml -f docker-compose.dev.yml up --build

# Create migrations (written to host filesystem)
docker compose -f docker-compose.app.yml -f docker-compose.dev.yml run --rm web python manage.py makemigrations

# Apply migrations
docker compose -f docker-compose.app.yml -f docker-compose.dev.yml run --rm web python manage.py migrate
```

### Key Services
- **web**: Django runserver (port 8000, bind-mounted at dev)
- **db**: PostgreSQL (see docker-compose.app.yml for credentials)
- **redis**: Cache + Celery broker
- **worker**: Celery worker (picks up tasks)
- **beat**: Celery beat scheduler (runs periodic tasks)
- **proxy**: Nginx (reverse proxy for production-like testing)

### Running Tests
```bash
# From web container
docker compose run --rm web python manage.py test
```

## Project Conventions

### Settings Management
- Use environment variables with sensible defaults (see `utag_ug_archiver/settings.py`)
- Helper: `_env_bool()` for boolean env vars (default False)
- Helper: `_env_list()` for comma-separated lists
- **ALLOWED_HOSTS**: Supports `DJANGO_ALLOWED_HOSTS` or `ALLOWED_HOSTS` env vars

### Model Patterns
- QuerySets with custom managers (e.g., `ChatThreadManager.for_user()`)
- Foreign keys use `SET_NULL` or `CASCADE` based on relationship importance
- Encrypted fields: Use `cryptography.fernet` (chat messages use this)
- Timestamps: All models should have `created_at`, `updated_at`, `last_message_at` fields

### WebSocket Security
- **Always validate participant access** before accepting messages (pattern: see `get_thread_and_validate_access()`)
- Use `database_sync_to_async` decorator for sync DB calls in async consumers
- Error handling: Return `PermissionError` for auth failures, `Http404` for missing resources

### Async Task Patterns
- Decorate with `@shared_task` (Celery auto-discovery)
- Log failures with context (user/object IDs, not full objects)
- Retry logic: Use `tenacity` library for email/external API calls
- **Note**: Task retry in Celery uses `.retry(exc=exc)` with `max_retries`, `default_retry_delay`

### Static Files & Assets
- **Development**: `python manage.py runserver` serves static files automatically
- **Production**: WhiteNoise middleware handles compression + caching (manifest strict mode)
- **Gallery images**: Special 1-year cache header; gzip compression in Nginx
- Collect static: `python manage.py collectstatic --noinput` (production only)

### Encryption
- Password hashing: Always use Django's `make_password()` (don't use cryptography.fernet)
- Message encryption: Wrap plaintext with `Fernet(key).encrypt(data)`, retrieve with `.decrypt()`
- Keys: Generate with `Fernet.generate_key()`; store securely in env or Django settings

## Common Commands

| Task | Command |
|------|---------|
| Create migration | `docker compose ... run --rm web python manage.py makemigrations [app]` |
| Run migrations | `docker compose ... run --rm web python manage.py migrate` |
| Django shell | `docker compose ... run --rm web python manage.py shell` |
| Create superuser | `docker compose ... run --rm web python manage.py createsuperuser` |
| Reset DB | `docker compose ... down -v && docker compose ... up --build` |
| Rebuild containers | `docker compose ... build web worker beat` |
| View logs | `docker compose ... logs -f [service]` |
| Celery tasks | Check Redis with `redis-cli` or Django admin for task history |

## Files to Know

| File | Purpose |
|------|---------|
| [utag_ug_archiver/settings.py](utag_ug_archiver/settings.py) | Django config, env var handling |
| [utag_ug_archiver/celery.py](utag_ug_archiver/celery.py) | Celery app config |
| [chat/consumers.py](chat/consumers.py) | WebSocket logic + security validation |
| [chat/routing.py](chat/routing.py) | WebSocket URL patterns |
| [accounts/models.py](accounts/models.py) | Custom User model, School/College/Department hierarchy |
| [dashboard/models.py](dashboard/models.py) | Event, EventScheduleItem, EventSpeaker models |
| [dashboard/tasks.py](dashboard/tasks.py) | Event/advert status update tasks |
| [DEVELOPMENT_DOCKER.md](DEVELOPMENT_DOCKER.md) | Docker workflow guide |
| [PRODUCTION_OPTIMIZATIONS.md](PRODUCTION_OPTIMIZATIONS.md) | Nginx, caching, security headers |

## Testing & Debugging

- **Logs**: Check `docker compose logs -f web` or `worker` for task errors
- **Redis CLI**: `docker compose exec redis redis-cli` to inspect cache/queues
- **Django ORM**: Use `python manage.py shell` to test queries
- **Async**: Test WebSocket consumers with `AsyncClient` or `WebsocketCommunicator`
- **Email**: Currently disabled; stub in tests or use mock

## Production Notes
- All services run non-root (see Dockerfile: `USER app`)
- Gunicorn replaces Django runserver
- WhiteNoise serves static files (no separate web server needed for statics)
- Nginx proxy layer handles SSL, compression, caching headers
- Environment variables must include: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `ALLOWED_HOSTS`
