# ── Imagen SIPSA Pipeline ────────────────────────────────────────────────────
FROM python:3.13-slim

# Usuario no-root por seguridad
RUN useradd --create-home --shell /bin/bash sipsa

WORKDIR /app

# Dependencias primero para aprovechar caché de capas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código fuente y configuración
COPY pyproject.toml .
COPY app.py .
COPY conf/ conf/
COPY src/ src/
COPY templates/ templates/

# Registrar el paquete sipsa (deps ya instaladas arriba)
RUN pip install --no-cache-dir --no-deps -e .

# Directorios de datos y conf/local (Kedro los necesita en runtime)
RUN mkdir -p \
        data/01_raw \
        data/02_intermediate \
        data/03_primary \
        data/08_reporting \
        conf/local \
    && chown -R sipsa:sipsa /app

USER sipsa

EXPOSE 8000

# Montar estos directorios como volúmenes externos para persistir datos
VOLUME ["/app/data/01_raw", "/app/data/08_reporting"]

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
