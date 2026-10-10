# Build context: the repository root (see docker-compose.yml), so the image
# can include the shared Python engine (/pyengine) and the seed challenges.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/backend

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY pyengine /srv/pyengine
COPY challenges /srv/challenges
COPY backend /srv/backend

ENV CHALLENGES_DIR=/srv/challenges

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
