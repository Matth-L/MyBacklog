FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY backend/ backend/
COPY static/ static/

ENV BACKLOG_DATA_DIR=/app/data
ENV BACKLOG_BACKUP_DIR=/app/backup_backlog
ENV BACKLOG_COVER_ART_DIR=/app/cover_art
ENV BACKLOG_NO_BROWSER=1
ENV PORT=5000
RUN mkdir -p /app/data /app/backup_backlog /app/cover_art

EXPOSE 5000

CMD ["python3", "app.py"]
