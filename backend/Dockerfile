FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend backend
COPY config config
COPY scripts scripts
COPY run.py .
COPY data/raw data/raw
ENV PYTHONIOENCODING=utf-8 PYTHONWARNINGS=ignore
# The team's pipeline turns data/raw into the processed tables at build time (no network needed).
RUN python -m backend.ingest all
CMD ["sh", "-c", "python -m uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
