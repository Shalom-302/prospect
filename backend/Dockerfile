# KORTEX Prospect API (FastAPI) + worker Celery — image de production.
# Construite par .github/workflows/build.yml -> ghcr.io/<owner>/<repo>, lancée par compose.image.yml.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STORAGE_DIR=/data/storage
RUN apt-get update && apt-get install -y --no-install-recommends fonts-liberation tzdata && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -r -u 1001 app && mkdir -p /data/storage && chown -R app:app /data /app && chmod +x /app/entrypoint.sh
USER app
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["api"]
