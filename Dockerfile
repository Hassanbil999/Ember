# One image serves the API and the web app on $PORT (Decision E). No database server, no keys needed.
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend backend
COPY config config
COPY scripts scripts
COPY run.py .
COPY data/raw data/raw
COPY data/seed.json data/seed.json
ENV PYTHONIOENCODING=utf-8 PYTHONWARNINGS=ignore
# The team's pipeline turns data/raw into the processed tables at build time (no network), then the
# adapter layer maps them to the SPEC §5 model and the seed fills only the gaps.
RUN python -m backend.ingest all
COPY --from=web /web/dist web/dist
EXPOSE 8000
CMD ["sh", "-c", "python -m uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
