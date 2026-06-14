FROM python:3.12-slim

# rclone (para subir a OneDrive/remotes y a carpetas locales) + utilidades.
# Se instala el binario oficial según la arquitectura del build (amd64/arm64).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip ca-certificates tzdata \
    && ARCH="$(dpkg --print-architecture)" \
    && curl -fsSL "https://downloads.rclone.org/rclone-current-linux-${ARCH}.zip" -o /tmp/rclone.zip \
    && unzip -q /tmp/rclone.zip -d /tmp/rclone \
    && cp /tmp/rclone/*/rclone /usr/local/bin/rclone \
    && chmod +x /usr/local/bin/rclone \
    && rm -rf /tmp/rclone* /var/lib/apt/lists/*

ENV TZ=America/Lima
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
