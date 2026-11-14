#!/bin/sh
# Start the private API, wait until it answers, then serve the site on $PORT.
set -e
PORT="${PORT:-7860}"

cd /app
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --log-level warning &

# the web app proxies /api to the API: do not open the public port before the API is up
i=0
until python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" 2>/dev/null; do
  i=$((i + 1))
  if [ "$i" -gt 120 ]; then echo "API did not start within 2 minutes" >&2; exit 1; fi
  sleep 1
done
echo "API ready; serving Freefall Atlas on port $PORT"

cd /web
exec node node_modules/next/dist/bin/next start -p "$PORT" -H 0.0.0.0
