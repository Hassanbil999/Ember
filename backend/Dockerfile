FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend backend
COPY config config
COPY run.py .
COPY data/raw data/raw
ENV PYTHONIOENCODING=utf-8 PYTHONWARNINGS=ignore
# build the fixture/indexes/models on first start if the volume is empty
CMD ["sh", "-c", "[ -f data/processed/tests.parquet ] || python run.py all; python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000"]
