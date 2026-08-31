FROM python:3.13-slim

WORKDIR /app

# gcc + freetds-dev: pymssql (conector SQL Server) precisa compilar contra o FreeTDS
RUN apt-get update && apt-get install -y --no-install-recommends gcc freetds-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY cronovazamento ./cronovazamento
RUN pip install --no-cache-dir ".[web,conectores]"

COPY webapp ./webapp
COPY data ./data

EXPOSE 8000

CMD ["uvicorn", "webapp.main:app", "--host", "0.0.0.0", "--port", "8000"]
