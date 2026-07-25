FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

USER app
EXPOSE 8000

CMD ["uvicorn", "utag_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
