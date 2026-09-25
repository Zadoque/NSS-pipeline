FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY pytest.ini ./
COPY tests ./tests

ENTRYPOINT ["python", "-m", "app.pipeline.run"]