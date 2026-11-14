# One container for hosting (Hugging Face Spaces, Google Cloud Run, Render, ...).
# The Next.js app serves the public port and proxies /api to FastAPI, which listens only inside the container.
# Everything the site needs (canonical tables, search index, models, image results) is built into the image,
# so a fresh start serves pages in seconds and computes nothing on first visit.
#
#   docker build -t freefall-atlas .
#   docker run -p 7860:7860 freefall-atlas        ->  http://localhost:7860
#
# The port comes from $PORT (Cloud Run and Render set it); 7860 is the Hugging Face Spaces default.

# ---- web app build ---------------------------------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend ./
COPY config/theme.tokens.json /config/theme.tokens.json
ENV NEXT_TELEMETRY_DISABLED=1 API_URL=http://127.0.0.1:8000
RUN node scripts/tokens.mjs && npm run build && npm prune --omit=dev

# ---- runtime: Python API + data, plus the Node runtime for `next start` ------------------------------
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
COPY --from=web /usr/local/bin/node /usr/local/bin/node

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend backend
COPY config config
COPY scripts scripts
COPY run.py .
COPY data/raw data/raw
ENV PYTHONIOENCODING=utf-8 PYTHONWARNINGS=ignore PYTHONUNBUFFERED=1

# real NASA tables -> canonical tables, indexes, image results and models (same steps as `python run.py all`,
# minus regenerating the demo fixture, which the app no longer uses)
RUN python run.py ingest && python run.py train && python run.py ingest

COPY --from=web /web /web
COPY deploy/start.sh /start.sh
# hosts such as Hugging Face run the container as a non-root user: let it write caches and corrections
RUN chmod +x /start.sh && chmod -R a+rwX /app/data /web/.next

ENV PORT=7860 NEXT_TELEMETRY_DISABLED=1
EXPOSE 7860
CMD ["/start.sh"]
