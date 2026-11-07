FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend backend
COPY frontend/dist frontend/dist
COPY media media
COPY run.py .

# Banco e mídia ficam no disco persistente montado em /data.
ENV APP_HOST=0.0.0.0 APP_PORT=8000 COOKIE_SECURE=true \
    DATABASE_PATH=/data/app.db MEDIA_DIR=/data/media
EXPOSE 8000

CMD ["sh", "-c", "mkdir -p /data && { [ -d /data/media ] || cp -r media /data/media; } && exec python run.py"]
