FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/rubel0278-bot/quantus-app-store"
LABEL org.opencontainers.image.description="Quantus Node Dashboard - web UI for node monitoring"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY api.py .

EXPOSE 8080

CMD ["python", "server.py"]
