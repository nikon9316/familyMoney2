FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# postgresql-client gives pg_dump and psql for backup/restore on Railway PostgreSQL
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client fonts-dejavu-core ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
