FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (optional but helpful for SSL/CA + tz)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tzdata \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

# Create mount points (docker-compose will mount over these)
RUN mkdir -p /output /data /backups

EXPOSE 8000

# Gunicorn entrypoint
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "app.wsgi:app"]
