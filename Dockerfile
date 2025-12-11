# ---------------------------
# STAGE 1: Builder
# ---------------------------
FROM python:3.11 as builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    pkg-config \
    libpq-dev \
    libcairo2-dev \
    libfreetype6-dev \
    libjpeg-dev \
    libpng-dev \
    libgdal-dev \
    gdal-bin \
    libproj-dev \
    proj-bin \
    libgeos-dev \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    cargo \
    cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels
COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel build && \
    pip wheel --no-deps --wheel-dir /wheels -r requirements.txt


# ---------------------------
# STAGE 2: Runtime
# ---------------------------
FROM python:3.11-slim

# Crear usuario no root
RUN groupadd -r app && useradd -r -g app -m app

# Dependencias *solo* de ejecución (ligeras)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libcairo2 \
    libfreetype6 \
    libjpeg62-turbo \
    libpng16-16 \
    gdal-bin \
    proj-bin \
    libgeos-c1v5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar las ruedas precompiladas
COPY --from=builder /wheels /wheels
COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --no-deps /wheels/* && \
    pip install --no-cache-dir -r requirements.txt || true

# Copiar el código
COPY . .

USER app

EXPOSE 8001

# Gunicorn + Uvicorn Workers apuntando a app.py
ENV GUNICORN_WORKERS=2

CMD ["sh", "-c", "exec gunicorn app:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8001 --workers ${GUNICORN_WORKERS} --log-level info --timeout 120"]

