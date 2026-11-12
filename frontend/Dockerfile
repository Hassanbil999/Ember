FROM node:22-alpine
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend .
COPY config/theme.tokens.json /config/theme.tokens.json
ARG API_URL=http://api:8000
ENV API_URL=$API_URL NEXT_TELEMETRY_DISABLED=1
RUN node scripts/tokens.mjs && npm run build
CMD ["npm", "run", "start"]
