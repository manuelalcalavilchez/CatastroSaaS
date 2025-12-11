FROM python:3.11-slim

# Instalamos dependencias necesarias para compilar paquetes Python,
# Cairo para reportlab/rlPyCairo, y libpq para PostgreSQL.
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libcairo2 \
    libcairo2-dev \
    pkg-config \
    libfreetype6-dev \
    libffi-dev \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements primero para hacer mejor el caching de Docker
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código del proyecto
COPY . .

# Exponer el puerto donde corre FastAPI/Uvicorn/Gunicorn
EXPOSE 8001

# Comando de arranque (puedes ajustarlo si usas gunicorn+uvicorn)
CMD ["python", "main.py"]
