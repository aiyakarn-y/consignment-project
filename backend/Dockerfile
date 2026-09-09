FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY resources ./resources
RUN useradd --uid 10001 --create-home appuser && mkdir /data && chown appuser:appuser /data
USER appuser
ENV CONSIGN_DATA_DIR=/data CONSIGN_TEMPLATE_PATH=/app/resources/templates/Consign_sample.xlsx CONSIGN_SAMPLE_DIR=/data/samples CONSIGN_STORAGE_DRIVER=local PORT=8100
EXPOSE 8100
CMD ["sh", "-c", "exec python -m uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8100}"]
