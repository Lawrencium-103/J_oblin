FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=7860
ENV DATA_DIR=/data
ENV JOBLIN_JWT_SECRET=huggingface-joblin-secret-2026
ENV JOBLIN_CRON_TOKEN=rSgdxzhCEZzTe5cVfXpBAVOEBeE6UpAWMP89AosAh4M

RUN mkdir -p /data/generated

EXPOSE 7860

CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
