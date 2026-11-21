FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CLINIC_ENV=production \
    INSTANCE_DIR=/app/instance \
    PORT=8000

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser \
 && mkdir -p /app/instance \
 && chown -R appuser:appuser /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

USER appuser

# Database, encryption key file (development only) and outbox live here. Mount a persistent volume.
VOLUME ["/app/instance"]
EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--worker-class", "gthread", "--threads", "16", "app:create_app()"]