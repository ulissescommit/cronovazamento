FROM python:3.13-slim

WORKDIR /app

# psycopg2-binary não precisa de libpq-dev, mas gcc é útil caso o pip
# precise compilar alguma dependência transitiva
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY cronovazamento ./cronovazamento
RUN pip install --no-cache-dir ".[web]"

COPY webapp ./webapp
COPY data ./data

EXPOSE 8000

CMD ["uvicorn", "webapp.main:app", "--host", "0.0.0.0", "--port", "8000"]
