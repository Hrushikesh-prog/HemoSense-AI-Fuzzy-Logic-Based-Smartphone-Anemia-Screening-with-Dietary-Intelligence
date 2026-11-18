# HemoSense API (ANFIS serving). Small image: numpy + OpenCV-headless + FastAPI, no TensorFlow.
# Build:  docker build -t hemosense-api .
# Run:    docker run -d -p 8000:8000 --restart unless-stopped --env-file api/.env hemosense-api
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2
WORKDIR /srv

COPY api/requirements-serve.txt /srv/api/requirements-serve.txt
RUN pip install --no-cache-dir -r /srv/api/requirements-serve.txt

COPY hemosense /srv/hemosense
COPY api /srv/api
# anfis.json + confidence.json, and rag_index.json when present (optional; RAG is off without it)
COPY models/*.json /srv/models/

RUN useradd -m app && chown -R app /srv
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
