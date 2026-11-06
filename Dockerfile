# ---- imagen base: dependencias de producción -------------------------------
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---- pruebas: agrega pytest, cobertura y httpx ------------------------------
FROM base AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
CMD ["python", "-m", "pytest", "--cov=src", "--cov-report=term-missing"]

# ---- aplicación ------------------------------------------------------------
FROM base AS app
COPY src ./src
COPY datos ./datos
COPY scripts ./scripts
EXPOSE 8000
# PORT lo asignan Render/Railway; en local vale 8000.
CMD ["sh", "-c", "uvicorn src.api.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
