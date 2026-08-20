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
# The app defaults to binding 127.0.0.1 only (see app.py's __main__), which
# inside a container means it wouldn't be reachable through the published
# Docker port at all. The container's network namespace is already an
# isolation boundary, so it's safe to have Flask listen on every interface
# *inside the container* here — actual host exposure is controlled by the
# port mapping in docker-compose.yml (which defaults to 127.0.0.1 too; see
# that file's comment for how to intentionally expose this to your LAN).
ENV BACKLOG_ALLOW_LAN=1
RUN mkdir -p /app/data /app/backup_backlog /app/cover_art

EXPOSE 5000

CMD ["python3", "app.py"]
